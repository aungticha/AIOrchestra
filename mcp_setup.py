"""Preview and install one MCP entry while preserving all other client settings."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tomllib
import library_manager

ROOT=Path(__file__).resolve().parent
BEGIN='# AIORCHESTRA:MCP:BEGIN'
END='# AIORCHESTRA:MCP:END'
LOCK=threading.RLock()


def python_path():
    candidate=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    return str(candidate if candidate.is_file() else Path(sys.executable))


def target(client,custom=None):
    if client not in ('codex','claude','claude-desktop'):raise ValueError('Unknown MCP client')
    if custom:
        if not isinstance(custom,str):raise ValueError('Config path must be text')
        path=Path(custom).expanduser()
        if not path.is_absolute():raise ValueError('Use an absolute config file path')
    elif client=='codex':path=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'config.toml'
    elif client=='claude':path=Path.home()/'.claude.json'
    elif sys.platform=='darwin':path=Path.home()/'Library/Application Support/Claude/claude_desktop_config.json'
    elif os.name=='nt':path=Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))/'Claude/claude_desktop_config.json'
    else:path=Path.home()/'.config/Claude/claude_desktop_config.json'
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('MCP config cannot use symlink paths')
    return path


def merged(workspace,client,raw):
    entry={'command':python_path(),'args':[str(ROOT/'orchestra_mcp.py'),'--workspace',str(Path(workspace).resolve())],'env':{'AIORCHESTRA_MCP_MANAGED':'1'}}
    text=raw.decode('utf-8-sig')
    if client=='codex':
        parsed=tomllib.loads(text)
        existing=parsed.get('mcp_servers',{}).get('aiorchestra')
        if existing and existing.get('env',{}).get('AIORCHESTRA_MCP_MANAGED')!='1':raise ValueError('Existing user MCP entry aiorchestra is not managed; rename it before Setup')
        block=BEGIN+'\n[mcp_servers.aiorchestra]\ncommand = '+json.dumps(entry['command'])+'\nargs = '+json.dumps(entry['args'])+'\n[mcp_servers.aiorchestra.env]\nAIORCHESTRA_MCP_MANAGED = "1"\n'+END
        if BEGIN in text:
            if text.count(BEGIN)!=1 or text.count(END)!=1 or text.index(END)<text.index(BEGIN):raise ValueError('Invalid managed MCP markers')
            updated=text[:text.index(BEGIN)]+block+text[text.index(END)+len(END):]
        else:
            if existing:raise ValueError('Managed MCP entry missing markers; review config manually')
            updated=text.rstrip()+'\n\n'+block+'\n'
        tomllib.loads(updated)
    else:
        parsed=json.loads(text) if text.strip() else {}
        if not isinstance(parsed,dict) or not isinstance(parsed.get('mcpServers',{}),dict):raise ValueError('Invalid MCP JSON config')
        servers=parsed.setdefault('mcpServers',{});existing=servers.get('aiorchestra')
        if existing and (not isinstance(existing,dict) or existing.get('env',{}).get('AIORCHESTRA_MCP_MANAGED')!='1'):raise ValueError('Existing user MCP entry aiorchestra is not managed')
        servers['aiorchestra']=entry;updated=json.dumps(parsed,ensure_ascii=False,indent=2)+'\n'
    return updated.encode('utf-8'),entry


def preview(workspace,client='codex',custom=None):
    path=target(client,custom)
    if path.exists() and (not path.is_file() or path.stat().st_size>2_000_000):raise ValueError('Invalid or oversized client config')
    raw=path.read_bytes() if path.exists() else b''
    content,entry=merged(workspace,client,raw)
    revision=hashlib.sha256(str(path).encode()+raw+content).hexdigest()
    snippet=content.decode() if client=='codex' else json.dumps({'mcpServers':{'aiorchestra':entry}},ensure_ascii=False,indent=2)
    if client=='codex':snippet=snippet[snippet.index(BEGIN):snippet.index(END)+len(END)]
    return dict(client=client,path=str(path),revision=revision,changed=raw!=content,entry=entry,snippet=snippet,transport='stdio')


def install(workspace,client='codex',custom=None,revision=None):
    with LOCK:
        info=preview(workspace,client,custom)
        if revision!=info['revision']:raise ValueError('Config changed; preview again before installing')
        path=Path(info['path']);raw=path.read_bytes() if path.exists() else b'';content,_=merged(workspace,client,raw)
        backup=None
        if raw!=content:
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                import tempfile
                with tempfile.NamedTemporaryFile(dir=path.parent,prefix=path.name+'.',suffix='.bak',delete=False) as f:f.write(raw);backup=f.name
            library_manager.write(path,content.decode('utf-8'));os.chmod(path,0o600)
        return {**preview(workspace,client,custom),'updated':raw!=content,'backup':backup}


def test(workspace):
    command=[python_path(),str(ROOT/'mcp_probe.py'),'--workspace',str(Path(workspace).resolve())]
    try:result=subprocess.run(command,capture_output=True,text=True,timeout=25)
    except (OSError,subprocess.TimeoutExpired):raise ValueError('MCP test could not start or timed out; verify Python, dependencies and server') from None
    if result.returncode:raise ValueError('MCP test failed: '+(result.stderr or result.stdout)[-2000:])
    return json.loads(result.stdout)
