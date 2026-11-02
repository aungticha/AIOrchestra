"""Publish the running local server endpoint without embedding machine paths."""
import json
import os
from pathlib import Path
import tempfile

def write(workspace,port,instance):
    folder=Path(workspace).resolve()/'runtime';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'server.json'
    if folder.is_symlink() or path.is_symlink():raise ValueError('Server discovery cannot be a symlink')
    content=json.dumps({'url':'http://127.0.0.1:'+str(port),'pid':os.getpid(),'instance':instance})
    with tempfile.NamedTemporaryFile(dir=folder,mode='w',encoding='utf-8',delete=False) as output:output.write(content);temporary=output.name
    os.chmod(temporary,0o600);os.replace(temporary,path)

def remove(workspace,instance):
    path=Path(workspace).resolve()/'runtime'/'server.json'
    if path.is_file() and not path.is_symlink():
        try:
            if json.loads(path.read_text())['instance']==instance:path.unlink()
        except (OSError,ValueError,KeyError):pass
