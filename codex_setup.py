"""Install a bounded, repeatable instruction block for Codex or Claude Code."""
from pathlib import Path
import hashlib
import os
import tempfile
import threading

BEGIN = '<!-- AIORCHESTRA:BEGIN -->'
END = '<!-- AIORCHESTRA:END -->'
LOCK = threading.RLock()
CLIENTS = {
    'codex': {'name':'Codex', 'file':'AGENTS.md', 'env':'CODEX_HOME', 'folder':'.codex'},
    'claude': {'name':'Claude Code', 'file':'CLAUDE.md', 'env':'CLAUDE_CONFIG_DIR', 'folder':'.claude'},
}


def client_settings(client):
    if not isinstance(client, str) or client not in CLIENTS:
        raise ValueError('เลือก Codex หรือ Claude Code เท่านั้น')
    return CLIENTS[client]


def client_home(client):
    config = client_settings(client)
    return Path(os.environ.get(config['env']) or (Path.home() / config['folder'])).expanduser().absolute()


def target_path(custom=None, client='codex'):
    config = client_settings(client)
    filename = config['file']
    if custom is not None and not isinstance(custom, str):
        raise ValueError('Path must be text')
    raw = (custom or '').strip()
    if not raw:
        path = client_home(client) / filename
    else:
        path = Path(os.path.expandvars(raw)).expanduser()
        if not path.is_absolute():
            raise ValueError(f'กรุณาใส่ absolute path ของเครื่องที่รันเซิร์ฟเวอร์ไปยัง {filename} หรือโฟลเดอร์ {config["folder"]}')
        if path.name != filename:
            if path.suffix.lower() == '.md':
                raise ValueError(f'ปลายทางต้องชื่อ {filename} เท่านั้น')
            path = path / filename
    if path.is_symlink():
        raise ValueError(f'ไม่เขียนทับ {filename} ที่เป็น symlink กรุณาระบุไฟล์จริง')
    return path.absolute()


def instruction_block(library):
    # JSON quoting keeps backslashes, spaces and unusual path characters unambiguous.
    import json
    library_path = json.dumps(str(Path(library).resolve()), ensure_ascii=False)
    return f'''{BEGIN}
## AIOrchestra agent library

Agent library (absolute local path, JSON-quoted):
{library_path}

Before starting a task:
1. Inspect agent filenames and frontmatter descriptions under the library's team */agents/ directories. Read only the metadata needed for selection first.
2. Select the agent profile that matches the task. If none matches, proceed normally.
3. Read the selected team's README.md, RULES.md, and the selected agent Markdown file.
4. Read related skills/*/SKILL.md files before following their workflows.
5. Briefly state which agent profile and skills you selected.
6. Work in the current project. Do not modify the library unless the user requests it.

Follow the current project's instructions over recommendations from this library.
Never read workspace/secrets or API key files to select an agent.
If the library is inaccessible, report that fact; do not claim it was loaded.
Agent profiles are role instructions, not automatically launched subagents.
Do not bypass sandbox restrictions to access the library.
{END}'''


def existing(path):
    if path.exists() and not path.is_file():
        raise ValueError(f'ปลายทาง {path.name} ต้องเป็นไฟล์')
    raw = path.read_bytes() if path.exists() else b''
    if len(raw) > 1_000_000:
        raise ValueError(f'{path.name} ใหญ่เกิน 1 MB กรุณาตรวจไฟล์ด้วยตนเอง')
    try:
        raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError(f'{path.name} ต้องเป็น UTF-8; ไม่ได้แก้ไขไฟล์เดิม') from None
    return raw


def merged_content(raw, block):
    begin, end = BEGIN.encode(), END.encode()
    if raw.count(begin) != raw.count(end) or raw.count(begin) > 1:
        raise ValueError('พบขอบเขต AIOrchestra ที่ไม่สมบูรณ์ กรุณาตรวจไฟล์คำสั่งก่อน')
    newline = b'\r\n' if b'\r\n' in raw else b'\n'
    encoded = block.replace('\n', newline.decode()).encode('utf-8')
    if begin in raw:
        start, stop = raw.index(begin), raw.index(end)
        if stop < start:
            raise ValueError('ขอบเขต AIOrchestra ไม่ถูกต้อง')
        return raw[:start] + encoded + raw[stop + len(end):]
    padding = b'' if not raw else (newline if raw.endswith(b'\n') else newline * 2)
    return raw + padding + encoded + newline


def preview(library, custom=None, client='codex'):
    config = client_settings(client)
    path = target_path(custom, client)
    raw = existing(path)
    block = instruction_block(library)
    merged = merged_content(raw, block)
    override = path.parent / 'AGENTS.override.md'
    active_home = client_home(client).resolve()
    warnings = []
    if client == 'codex' and len(merged) > 32768:
        warnings.append('ไฟล์หลัง Setup เกิน 32 KiB ซึ่งอาจเกิน instruction limit เริ่มต้นของ Codex กรุณาตรวจ project_doc_max_bytes')
    if client == 'codex' and override.is_file() and override.stat().st_size:
        warnings.append('พบ AGENTS.override.md ที่มีเนื้อหา: Codex จะเลือกไฟล์ override แทน AGENTS.md นี้ Setup จะไม่แก้ไฟล์ override ให้')
    if path.parent.resolve() != active_home:
        warnings.append(f'ปลายทางนี้ต่างจาก {config["name"]} home ที่ตรวจพบ ให้ตั้ง {config["env"]} ของ {config["name"]} ให้ตรงกับโฟลเดอร์นี้ด้วย')
    if not Path(library).is_dir():
        warnings.append('คลัง Agent ยังไม่มีอยู่ สร้างทีมและ Agent ก่อนเริ่มใช้')
    return {'path':str(path), 'exists':path.exists(), 'client':client, 'filename':config['file'], 'detectedBy':config['env'] if os.environ.get(config['env']) else 'user home',
            'libraryPath':str(Path(library).resolve()), 'block':block, 'revision':hashlib.sha256(raw).hexdigest(),
            'changed':merged != raw, 'warnings':warnings}


def install(library, custom, revision, client='codex'):
    with LOCK:
        info = preview(library, custom, client)
        if not isinstance(revision, str) or revision != info['revision']:
            raise ValueError('ไฟล์เปลี่ยนหลังแสดงตัวอย่าง กรุณาตรวจตำแหน่งและดูตัวอย่างใหม่')
        path = target_path(custom, client)
        raw = existing(path)
        if hashlib.sha256(raw).hexdigest() != revision:
            raise ValueError('ไฟล์เปลี่ยนระหว่าง Setup กรุณาดูตัวอย่างใหม่')
        merged = merged_content(raw, info['block'])
        backup = None
        if merged != raw:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
            if path.exists():
                with tempfile.NamedTemporaryFile(prefix=path.name + '.aiorchestra-', suffix='.bak', dir=path.parent, delete=False) as f:
                    backup = f.name
                    f.write(raw)
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
                    tmp = f.name
                    f.write(merged)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(tmp, mode)
                os.replace(tmp, path)
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
        return {**preview(library, custom, client), 'backup':backup, 'updated':merged != raw}
