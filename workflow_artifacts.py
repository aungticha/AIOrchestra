"""Serve only files recorded as deliverables of a workflow, with video range support."""
import mimetypes
from pathlib import Path
import re
import workflow_media
import workflow_store


def serve(handler, workspace, query):
    record=workflow_store.get(workspace,query.get('id',[''])[0])
    root=Path(record.get('output_root','')).resolve()
    supplied=query.get('path',[''])[0]
    path=Path(supplied)
    path=(path if path.is_absolute() else root/path).resolve()
    if str(path) not in record.get('artifacts',{}):raise ValueError('ไม่พบไฟล์ผลลัพธ์นี้ใน Workflow')
    item={'path':supplied,'kind':record['artifacts'][str(path)]['kind']}
    # Validate the raw path and all parents before opening it (no arbitrary file endpoint).
    workflow_media.artifacts(root,[item],hash_content=False)
    size=path.stat().st_size;start=0;end=size-1;status=200
    header=handler.headers.get('Range')
    if header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        if not match or not any(match.groups()):return handler.respond(416,{'error':'Invalid byte range'})
        if match[1]:
            start=int(match[1]);end=min(int(match[2]),end) if match[2] else end
        else:start=max(0,size-int(match[2]))
        if start>end or start>=size:return handler.respond(416,{'error':'Range outside file'})
        status=206
    mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    inline=mime.startswith(('video/','audio/','image/')) and mime!='image/svg+xml'
    handler.send_response(status)
    handler.send_header('Content-Type',mime if inline else 'application/octet-stream')
    handler.send_header('Content-Length',str(max(0,end-start+1)))
    handler.send_header('Accept-Ranges','bytes')
    handler.send_header('Content-Disposition','inline' if inline else 'attachment')
    handler.send_header('X-Content-Type-Options','nosniff')
    handler.send_header('Cache-Control','no-store')
    handler.send_header('Content-Security-Policy',"default-src 'none'; sandbox")
    if status==206:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers()
    try:
        with path.open('rb') as stream:
            stream.seek(start);remaining=end-start+1
            while remaining>0:
                chunk=stream.read(min(256*1024,remaining))
                if not chunk:break
                handler.wfile.write(chunk);remaining-=len(chunk)
    except (BrokenPipeError,ConnectionResetError):pass
