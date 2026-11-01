"""Project-wide API key storage. Never expose values in dashboard responses."""
import json
import os
import re
from pathlib import Path
import tempfile
import threading

KEYS = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY')
LOCK = threading.RLock()


def location(workspace):
    root = Path(workspace).resolve()
    folder = root / 'secrets'
    path = folder / 'api-tokens.json'
    if folder.is_symlink() or path.is_symlink():
        raise ValueError('ไม่รองรับ symlink สำหรับไฟล์ API keys')
    return path


def validate(values):
    if not isinstance(values, dict) or not values or len(values) > 100:
        raise ValueError('ต้องมีคีย์ 1–100 รายการ')
    if any(not isinstance(key, str) or not re.fullmatch(r'[A-Z_][A-Z0-9_]{0,63}', key) for key in values):
        raise ValueError('ชื่อคีย์ต้องใช้ A–Z, 0–9 และ _ โดยห้ามขึ้นต้นด้วยตัวเลข และยาวไม่เกิน 64 ตัว')
    for value in values.values():
        if not isinstance(value, str) or not value or len(value) > 8192 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('API key ต้องเป็นข้อความที่ไม่ว่าง ไม่มีช่องว่าง และยาวไม่เกิน 8192 ตัว')
    if len((json.dumps(values, ensure_ascii=False, indent=2) + '\n').encode('utf-8')) > 24000:
        raise ValueError('คีย์ทั้งหมดรวมกันต้องมีขนาดไม่เกิน 24 KB')
    return values


def parse_file(content):
    if not isinstance(content, str) or len(content.encode('utf-8')) > 24000:
        raise ValueError('ไฟล์ token ต้องเป็น UTF-8 และขนาดไม่เกิน 24 KB')
    content = content.lstrip('\ufeff').strip()
    if content.startswith('{'):
        try:
            values = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError('รูปแบบ JSON ไม่ถูกต้อง') from None
    else:
        values = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:].strip()
            key, sep, value = line.partition('=')
            key, value = key.strip(), value.strip()
            if not sep or key in values:
                raise ValueError('รูปแบบ .env ไม่ถูกต้องหรือมีชื่อคีย์ซ้ำ')
            if value.startswith(('\"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError('เครื่องหมายคำพูดใน .env ไม่ครบ')
                value = value[1:-1]
            values[key] = value
    return validate(values)


def load(workspace):
    with LOCK:
        path = location(workspace)
        if not path.exists():
            return {}
        try:
            if path.stat().st_size > 24000:
                raise ValueError()
            return validate(json.loads(path.read_text(encoding='utf-8')))
        except (ValueError, OSError):
            raise ValueError('อ่านไฟล์ API keys กลางไม่สำเร็จ กรุณาตรวจรูปแบบและสิทธิ์ไฟล์') from None


def status(workspace):
    values = load(workspace)
    return {'providers': {key: {'configured': key in values} for key in sorted(set(KEYS) | set(values))},
            'path': 'workspace/secrets/api-tokens.json', 'scope': 'global', 'verified': False}


def save(workspace, values):
    validate(values)
    with LOCK:
        merged = validate({**load(workspace), **values})
        path = location(workspace)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
                tmp = f.name
                os.chmod(f.name, 0o600)
                json.dump(merged, f, ensure_ascii=False, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        return status(workspace)
