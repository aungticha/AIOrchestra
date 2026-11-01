"""Subscription quota adapters. No model calls, secret-file parsing, or billing estimates."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import codex_setup

LOCK = threading.RLock()
CACHE = None
CACHE_AT = 0
ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def window(label, used, reset=None):
    if not number(used) or not 0 <= used <= 100:
        return None
    return {'label':label, 'usedPercent':used, 'remainingPercent':round(100-used,2),
            'resetsAt':reset if number(reset) and reset > 0 else None}


def codex_windows(result):
    buckets=result.get('rateLimitsByLimitId')
    buckets=buckets if isinstance(buckets,dict) and buckets else {'codex':result.get('rateLimits')}
    out=[]
    for name, bucket in buckets.items():
        if not isinstance(bucket,dict): continue
        for key in ('primary','secondary'):
            item=bucket.get(key)
            if not isinstance(item,dict): continue
            mins=item.get('windowDurationMins')
            label=f'{name} · {mins} min' if number(mins) else f'{name} · {key}'
            value=window(label,item.get('usedPercent'),item.get('resetsAt'))
            if value: out.append(value)
    return out


def find_codex():
    found=shutil.which('codex')
    if found: return found
    candidates=[Path('/Applications/Codex.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'),
                Path.home()/'Applications/Codex.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex']
    return next((str(p) for p in candidates if p.is_file()),None)


class Rpc:
    def __init__(self, executable):
        self.process=subprocess.Popen([executable,'app-server','--stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.messages=queue.Queue(maxsize=500)
        self.deadline=time.monotonic()+18
        self.reader=threading.Thread(target=self._read,daemon=True)
        self.reader.start()
        self.serial=0

    def _read(self):
        try:
            for line in self.process.stdout:
                try: self.messages.put_nowait(json.loads(line))
                except (ValueError,queue.Full): pass
        finally:
            try: self.messages.put_nowait(None)
            except queue.Full: pass

    def send(self, data):
        self.process.stdin.write(json.dumps(data)+'\n');self.process.stdin.flush()

    def call(self, method, params=None):
        self.serial+=1
        current=self.serial
        self.send({'id':current,'method':method,'params':params or {}})
        while True:
            remaining=self.deadline-time.monotonic()
            if remaining<=0: raise TimeoutError()
            try: item=self.messages.get(timeout=remaining)
            except queue.Empty: raise TimeoutError() from None
            if item is None: raise RuntimeError('CLI stopped')
            if not isinstance(item,dict) or item.get('id')!=current: continue
            if 'error' in item: raise RuntimeError('CLI request failed')
            return item.get('result',{})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: self.process.kill();self.process.wait(timeout=2)
        self.process.stdin.close()
        self.reader.join(timeout=2)
        self.process.stdout.close()


def fetch_codex():
    base={'source':'Codex App Server','windows':[], 'updatedAt':None, 'checkedAt':now(), 'action':'login'}
    executable=find_codex()
    if not executable:
        return {**base,'status':'missing_cli','message':'ไม่พบ Codex CLI ใน PATH หรือโฟลเดอร์แอป ให้ติดตั้ง/เพิ่ม PATH แล้วเริ่ม server ใหม่'}
    rpc=None
    try:
        rpc=Rpc(executable)
        rpc.call('initialize',{'clientInfo':{'name':'aiorchestra','title':'AI Orchestra Quota','version':'0.1.0'}})
        rpc.send({'method':'initialized'})
        account=rpc.call('account/read',{'refreshToken':False}).get('account')
        if not isinstance(account,dict):
            return {**base,'status':'login_required','message':'กรุณาล็อกอิน Codex CLI ด้วย codex login แล้วกดอัปเดต'}
        if account.get('type')=='apiKey':
            return {**base,'status':'api_mode','action':'keys','message':'Codex ใช้ API key: โควตาสมาชิกใช้ไม่ได้กับโหมดนี้ รายงาน API usage/cost ยังไม่ได้เชื่อมต่อ'}
        values=codex_windows(rpc.call('account/rateLimits/read'))
        return {**base,'status':'ok' if values else 'unavailable','action':None,'windows':values,
                'updatedAt':now() if values else None,'message':'โควตาสมาชิก ไม่ใช่ยอด API credits' if values else 'บัญชีนี้ยังไม่ส่งข้อมูลโควตาที่รองรับ'}
    except TimeoutError:
        return {**base,'status':'timeout','message':'อ่านโควตาไม่ทันภายใน 18 วินาที กดอัปเดตเพื่อลองใหม่'}
    except (OSError,RuntimeError,ValueError,AttributeError):
        return {**base,'status':'unavailable','message':'อ่านโควตาไม่ได้ ตรวจการล็อกอิน เครือข่าย และเวอร์ชัน Codex CLI'}
    finally:
        if rpc: rpc.close()


def codex_status():
    global CACHE,CACHE_AT
    with LOCK:
        if CACHE is None or time.monotonic()-CACHE_AT>=60:
            CACHE=fetch_codex();CACHE_AT=time.monotonic()
        return CACHE


def cached_codex():
    if CACHE is None:
        return {'status':'not_checked','windows':[],'updatedAt':None,'message':'กดอัปเดตเพื่ออ่านโควตาจาก Codex CLI','action':None}
    result=dict(CACHE)
    if result.get('status')=='ok':
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(result['updatedAt'])).total_seconds()
            expired=any(w.get('resetsAt') is not None and w['resetsAt']<=time.time() for w in result.get('windows',[]))
            if age>300 or age<0 or expired:
                result.update(status='stale',message='ข้อมูล Codex เก่าหรือถึงเวลารีเซ็ตแล้ว กดอัปเดตเพื่ออ่านค่าล่าสุด')
        except (ValueError,TypeError,KeyError):
            result.update(status='stale',message='ไม่ทราบเวลาข้อมูล Codex ล่าสุด กรุณากดอัปเดต')
    return result


def snapshot_path(workspace):
    root=Path(workspace).resolve()
    folder=root/'usage'
    if folder.is_symlink() or (folder/'claude.json').is_symlink():
        raise ValueError('Usage snapshot cannot be a symlink')
    return folder/'claude.json'


def write_claude_snapshot(workspace, payload):
    if not isinstance(payload,dict): raise ValueError('Invalid status line data')
    rates=payload.get('rate_limits')
    rates=rates if isinstance(rates,dict) else {}
    windows=[]
    for name,label in (('five_hour','5 hours'),('seven_day','7 days')):
        item=rates.get(name)
        if isinstance(item,dict):
            value=window(label,item.get('used_percentage'),item.get('resets_at'))
            if value: windows.append(value)
    # Only allowlisted quota numbers are persisted; never save prompts, transcript paths or auth data.
    result={'source':'Claude Code status line','status':'ok' if windows else 'unavailable',
        'windows':windows,'updatedAt':now(),'message':'โควตาสมาชิกจาก CLI' if windows else 'CLI ยังไม่ส่งโควตาสมาชิก อาจเป็นโหมด API หรือบัญชี/เวอร์ชันที่ไม่รองรับ','action':None}
    path=snapshot_path(workspace)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
            tmp=f.name;json.dump(result,f,ensure_ascii=False)
        os.replace(tmp,path)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)
    return result


def claude_status(workspace):
    default={'source':'Claude Code status line','status':'bridge_required','windows':[], 'updatedAt':None,
        'message':'ติดตั้งตัวเชื่อม จากนั้นเปิด Claude Code CLI และส่งข้อความเพื่อให้ CLI ส่งข้อมูลโควตา','action':'bridge'}
    try:
        path=snapshot_path(workspace)
        if not path.exists(): return default
        if path.stat().st_size>10000: raise ValueError()
        saved=json.loads(path.read_text(encoding='utf-8'))
        # Revalidate snapshots instead of trusting arbitrary cached strings.
        windows=[window(str(i.get('label',''))[:40],i.get('usedPercent'),i.get('resetsAt')) for i in saved.get('windows',[]) if isinstance(i,dict)]
        windows=[i for i in windows if i]
        stamp=saved.get('updatedAt')
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds()
        stale=age>300 or age<0 or any(w['resetsAt'] is not None and w['resetsAt']<=time.time() for w in windows)
        return {**default,'windows':windows,'updatedAt':stamp,'status':'stale' if stale else ('ok' if windows else 'unavailable'),
                'action':None,'message':'ข้อมูลล่าสุดจาก CLI เกิน 5 นาที อาจเปลี่ยนแล้ว เปิด Claude CLI เพื่ออัปเดต' if stale else ('โควตาสมาชิกจาก CLI' if windows else 'CLI ยังไม่ส่งโควตาสมาชิก อาจเป็นโหมด API หรือบัญชี/เวอร์ชันที่ไม่รองรับ')}
    except (OSError,ValueError,TypeError,AttributeError):
        return {**default,'status':'unavailable','message':'อ่านข้อมูลโควตา Claude ไม่สำเร็จ กรุณาตรวจ/ติดตั้งตัวเชื่อม'}


def bridge_command(workspace):
    args=[sys.executable,str(ROOT/'claude_quota_bridge.py'),'--workspace',str(Path(workspace).resolve())]
    if os.name=='nt':
        script='& '+' '.join("'"+arg.replace("'","''")+"'" for arg in args)
        return 'powershell -NoProfile -EncodedCommand '+base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return shlex.join(args)


def bridge_preview(workspace):
    path=codex_setup.client_home('claude')/'settings.json'
    if path.is_symlink(): raise ValueError('ไม่แก้ settings.json ที่เป็น symlink')
    raw=path.read_bytes() if path.exists() else b''
    if len(raw)>1_000_000: raise ValueError('settings.json ใหญ่เกิน 1 MB')
    try: settings=json.loads(raw.decode('utf-8-sig')) if raw else {}
    except ValueError: raise ValueError('settings.json ไม่ใช่ JSON ที่ถูกต้อง ไม่ได้แก้ไฟล์เดิม') from None
    if not isinstance(settings,dict): raise ValueError('settings.json ต้องเป็น JSON object')
    target={'type':'command','command':bridge_command(workspace)}
    current=settings.get('statusLine')
    compatible=current is None or current==target
    return {'path':str(path),'revision':hashlib.sha256(raw).hexdigest(),'statusLine':target,'installed':current==target,
            'canInstall':compatible,'message':'พร้อมติดตั้งตัวเชื่อม โดยสำรองและคง settings อื่นไว้' if compatible else 'มี statusLine เดิมอยู่แล้ว ไม่เขียนทับ กรุณารวมตัวเชื่อมด้วยตนเองตาม README'}


def install_bridge(workspace, revision):
    with LOCK:
        info=bridge_preview(workspace)
        if info['revision']!=revision: raise ValueError('settings.json เปลี่ยนแล้ว กรุณาดูตัวอย่างใหม่')
        if not info['canInstall']: raise ValueError(info['message'])
        if info['installed']: return {**info,'backup':None}
        path=Path(info['path']);raw=path.read_bytes() if path.exists() else b''
        if hashlib.sha256(raw).hexdigest()!=revision: raise ValueError('settings.json เปลี่ยนระหว่างติดตั้ง')
        settings=json.loads(raw.decode('utf-8-sig')) if raw else {}
        settings['statusLine']=info['statusLine']
        path.parent.mkdir(parents=True,exist_ok=True)
        backup=None
        if path.exists():
            with tempfile.NamedTemporaryFile(prefix='settings.json.aiorchestra-',suffix='.bak',dir=path.parent,delete=False) as f:
                backup=f.name;f.write(raw)
        tmp=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
                tmp=f.name;json.dump(settings,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
            os.chmod(tmp,0o600);os.replace(tmp,path)
        finally:
            if tmp and os.path.exists(tmp): os.unlink(tmp)
        return {**bridge_preview(workspace),'backup':backup}
