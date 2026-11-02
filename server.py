"""AI Orchestra: loopback-only Markdown workspace with owned CLI terminals."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import argparse, io, json, re, zipfile, tempfile, os, signal
import token_store
import codex_setup
import quota
import live_agents
import team_paths
import task_templates
import agent_skills
import library_manager
import team_description
import agent_appearance
import terminal_runtime
import rewards
import team_resources
from urllib.parse import urlsplit,parse_qs,quote

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'workspace'
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
KINDS = {'rules': 'RULES.md', 'overview': 'README.md'}

def slug(value):
    if not isinstance(value, str) or len(value) > 64 or not SLUG.fullmatch(value):
        raise ValueError('ID ต้องใช้ a-z, 0-9 และขีดกลาง ความยาวไม่เกิน 64 ตัว')
    return value

def safe(path):
    path = path.resolve()
    if not path.is_relative_to(DATA.resolve()):
        raise ValueError('Path outside workspace')
    return path

def write(path, content):
    path = safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        f.write(content)
        tmp = f.name
    os.replace(tmp, path)

def teamdir(team):
    return safe(team_paths.team_dir(DATA, team))

def document(team, kind, name=''):
    base = teamdir(team)
    if kind in KINDS:
        return safe(base / KINDS[kind])
    if kind == 'skill':
        return safe(base / 'skills' / slug(name) / 'SKILL.md')
    if kind == 'agent':
        return safe(base / 'agents' / (slug(name) + '.md'))
    raise ValueError('Unknown document type')

def read(path):
    return safe(path).read_text(encoding='utf-8')

def frontmatter(name, description, body):
    return f'---\nname: {json.dumps(name, ensure_ascii=False)}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n{body}\n'

def validate(content, kind, name):
    if not isinstance(content, str) or not content.strip() or len(content.encode()) > 200_000:
        raise ValueError('เนื้อหาต้องไม่ว่าง และไม่เกิน 200 KB')
    if kind in ('skill', 'agent'):
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', content, re.S)
        if not match:
            raise ValueError('ต้องมี YAML frontmatter: name และ description')
        if kind == 'agent': agent_appearance.get(content)
        metadata = {}
        for line in match[1].splitlines():
            key, sep, value = line.partition(':')
            if sep:
                metadata[key.strip()] = value.strip().strip('\"\'')
        if metadata.get('name') != name or not metadata.get('description', '').strip():
            raise ValueError('name ต้องตรงกับ ID และต้องมี description บรรทัดเดียว')

def state():
    teams = []
    base = DATA / 'teams'
    if base.exists():
        for folder in sorted(base.iterdir()):
            if not (team_paths.LEGACY.fullmatch(folder.name) or team_paths.ENCODED.fullmatch(folder.name)) or not folder.is_dir() or folder.is_symlink():
                continue
            metadata=json.loads(read(folder/'TEAM.json')) if (folder/'TEAM.json').is_file() else {'id':folder.name}
            if not isinstance(metadata,dict) or 'id' not in metadata:
                raise ValueError('TEAM.json ต้องมี id ของทีม')
            identity=team_paths.team_id(metadata['id'])
            if teamdir(identity) != folder.resolve():
                continue
            routing=task_templates.defaults(metadata.get('workType','general'), metadata.get('routingMode','recommended'))
            teams.append({'id':identity, 'folder':folder.name, **routing, 'description':team_description.get(read(folder/'README.md')), 'overview': read(folder/'README.md'), 'rules': read(folder/'RULES.md'),
                'skills': [{'id': p.parent.name, 'content': read(p)} for p in sorted((folder/'skills').glob('*/SKILL.md'))],
                'agents': [{'id': p.stem, **agent_skills.identity(read(p),p.stem), 'appearance':agent_appearance.get(read(p)), 'content': read(p), 'skills':agent_skills.effective(read(p),[s.parent.name for s in (folder/'skills').glob('*/SKILL.md')]), 'skillMode':'shared' if agent_skills.assigned(read(p)) is None else 'assigned'} for p in sorted((folder/'agents').glob('*.md'))]})
    locks=set(live_agents.snapshot(DATA)['lockedTeams'])
    for item in teams: item['locked']=item['id'] in locks
    return {'teams': teams, 'catalog':task_templates.catalog()}

def create_team(name, title, description, category='general', mode='recommended'):
    name=team_paths.team_id(name)
    routing=task_templates.defaults(category,mode)
    folder = teamdir(name)
    if folder.exists():
        raise ValueError('ทีมนี้มีอยู่แล้ว')
    if not isinstance(title, str) or not title.strip() or not isinstance(description, str):
        raise ValueError('ระบุชื่อและรายละเอียดทีม')
    description=team_description.validate(description)
    write(folder/'TEAM.json',json.dumps({'id':name, 'description':description, **routing},ensure_ascii=False,indent=2)+'\n')
    write(folder/'README.md', f'# {title}\n\n{team_description.BEGIN}\n{description}\n{team_description.END}\n\n## เป้าหมาย\n- ระบุผลลัพธ์ของทีม\n\n## การส่งต่องาน\n- ระบุผู้รับงานและเกณฑ์การตรวจรับ\n\n' + task_templates.markdown(category,mode))
    write(folder/'RULES.md', '# กฎส่วนกลาง\n\n- อ่านโจทย์และตรวจสอบข้อมูลก่อนเริ่มงาน\n- ห้ามแต่งข้อเท็จจริงหรือแหล่งอ้างอิง\n- ส่งงานพร้อมรายการสิ่งที่ตรวจสอบและข้อจำกัด\n')

def export_files(team, target, agent=None):
    folder = teamdir(team)
    overview, rules = read(folder/'README.md'), read(folder/'RULES.md')
    agents = {p.stem: read(p) for p in sorted((folder/'agents').glob('*.md'))}
    skills = {p.parent.name: read(p) for p in sorted((folder/'skills').glob('*/SKILL.md'))}
    if agent and agent not in agents:
        raise ValueError('Agent not found')
    context = overview + '\n' + rules
    if agent:
        context += '\n## Active agent\n' + agents[agent]
    files = {}
    if target == 'codex':
        files['AGENTS.md'] = context + '\n## Team profiles\nProfiles are role instructions, not automatically launched subagents. Read the requested profile under team-agents/.\n'
        files.update({f'.agents/skills/{n}/SKILL.md': c for n,c in skills.items()})
        files.update({f'team-agents/{n}.md': c for n,c in agents.items()})
    elif target == 'claude':
        files['CLAUDE.md'] = context
        files.update({f'.claude/skills/{n}/SKILL.md': c for n,c in skills.items()})
        # Inline shared context because Claude subagents do not inherit the parent prompt.
        for name, content in agents.items():
            files[f'.claude/agents/{name}.md'] = content + '\n## Shared team instructions\n' + context + '\n## Assigned skills\n' + '\n'.join(skills[n] for n in agent_skills.effective(content,skills) if n in skills)
    elif target == 'portable':
        files['CONTEXT.md'] = context + '\n## Agent profiles\n' + '\n'.join(agents.values()) + '\n## Skills\n' + '\n'.join(skills.values())
    else:
        raise ValueError('Unknown export target')
    files['ORCHESTRA-README.md'] = '# AI Orchestra export\n\nGenerated snapshot. Edit originals in AI Orchestra and export again.\n\nExtract into your project after reviewing files. Do not overwrite existing AGENTS.md or CLAUDE.md without merging.\nCodex: open the project in a local Codex client. Profiles in team-agents/ are instructions, not native subagent configuration.\nClaude Code: open the project; .claude/agents contains native agent definitions.\nPortable UI: attach CONTEXT.md or paste its contents into your chat. Web chat does not automatically read your local filesystem.\nNo models are invoked by this dashboard.\n'
    return files

class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        payload = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict,list)) else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def trusted(self):
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') not in (expected, f'localhost:{self.server.server_port}'):
            return False
        origin = self.headers.get('Origin')
        return origin is None or origin in (f'http://{expected}', f'http://localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.trusted():
            return self.respond(403, {'error':'Local requests only'})
        if self.path.startswith('/api/resources') or self.path == '/api/rewards':
            try:
                url=urlsplit(self.path);query=parse_qs(url.query)
                if url.path=='/api/rewards': return self.respond(200,rewards.snapshot(DATA))
                if url.path=='/api/resources': return self.respond(200,team_resources.listing(DATA,query.get('team',[''])[0]))
                if url.path=='/api/resources/file':
                    item,path=team_resources.fetch(DATA,query.get('id',[''])[0]);content=path.read_bytes()
                    inline=item['mime'].startswith('image/') and query.get('preview')==['1']
                    self.send_response(200);self.send_header('Content-Type',item['mime'] if inline else 'application/octet-stream')
                    self.send_header('Content-Disposition',('inline' if inline else 'attachment')+"; filename*=UTF-8''"+quote(item['name'],safe=''))
                    self.send_header('Content-Length',str(len(content)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'none'; sandbox");self.end_headers();self.wfile.write(content);return
                return self.respond(404,{'error':'Not found'})
            except (ValueError,OSError) as e: return self.respond(400,{'error':str(e)})
        if self.path == '/api/terminal/options':
            return self.respond(200,terminal_runtime.options())
        if self.path == '/api/terminal/list':
            return self.respond(200,{'sessions':terminal_runtime.manager.list(DATA)})
        if self.path == '/api/live':
            try:
                return self.respond(200, live_agents.snapshot(DATA))
            except (OSError, ValueError, live_agents.sqlite3.Error):
                return self.respond(400, {'error':'อ่าน Live Agents ไม่สำเร็จ กรุณาตรวจสิทธิ์ runtime storage'})
        if self.path == '/api/quota':
            return self.respond(200, {'codex':quota.cached_codex(), 'claude':quota.claude_status(DATA)})
        if self.path == '/api/quota/claude-bridge':
            try:
                return self.respond(200, quota.bridge_preview(DATA))
            except (OSError, ValueError) as e:
                return self.respond(400, {'error':str(e)})
        if self.path == '/api/setup':
            try:
                return self.respond(200, codex_setup.preview(DATA / 'teams'))
            except (ValueError, OSError) as e:
                return self.respond(400, {'error':str(e)})
        if self.path == '/api/credentials':
            try:
                return self.respond(200, token_store.status(DATA))
            except (ValueError, OSError):
                return self.respond(400, {'error': 'อ่านไฟล์ API keys กลางไม่สำเร็จ กรุณาตรวจรูปแบบและสิทธิ์ไฟล์'})
        if self.path == '/api/state':
            try:
                return self.respond(200, state())
            except (ValueError, OSError) as e:
                return self.respond(400, {'error':str(e)})
        paths = {'/':'index.html', '/app.js':'app.js', '/office_state.js':'office_state.js', '/pixel_office.js':'pixel_office.js', '/office_motion.js':'office_motion.js', '/style.css':'style.css'}
        paths['/community.js']='community.js'
        paths.update({'/terminal.js':'terminal.js',**{'/vendor/'+name:'vendor/'+name for name in ('xterm.js','xterm.css','addon-fit.js')}})
        if self.path not in paths:
            return self.respond(404, {'error':'Not found'})
        path = ROOT/'static'/paths[self.path]
        types = {'.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8'}
        self.respond(200, path.read_bytes(), types[path.suffix])

    def do_POST(self):
        if not self.trusted() or self.headers.get('Content-Type') != 'application/json':
            return self.respond(403, {'error':'Local JSON requests only'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            maximum=14_100_000 if self.path=='/api/resources/upload' else 250_000
            if not 0 < size <= maximum:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Request must be an object')
            if self.path == '/api/resources/upload': return self.respond(200,team_resources.upload(DATA,data))
            if self.path == '/api/resources/delete': return self.respond(200,team_resources.delete(DATA,data))
            if self.path == '/api/rewards/review': return self.respond(200,rewards.review(DATA,data))
            if self.path.startswith('/api/terminal/'):
                action=self.path.rsplit('/',1)[-1]
                if action=='start': return self.respond(200,terminal_runtime.manager.start(DATA,data))
                item=terminal_runtime.manager.get(DATA,data.get('session'))
                if action=='read': return self.respond(200,item.read(data.get('cursor',0)))
                if action=='input': item.input(data.get('text'))
                elif action=='resize': item.resize(data.get('cols'),data.get('rows'))
                elif action=='close': item.close()
                else: raise ValueError('Unknown terminal action')
                return self.respond(200,item.info())
            if self.path == '/api/library/manage':
                result=library_manager.manage(DATA,data)
                return self.respond(200, {'state':state(), 'result':result})
            if self.path == '/api/live/close':
                live_agents.close_run(DATA,data.get('engine'),data.get('session'))
                return self.respond(200,live_agents.snapshot(DATA))
            if self.path == '/api/quota/refresh':
                return self.respond(200, {'codex':quota.codex_status(), 'claude':quota.claude_status(DATA)})
            if self.path == '/api/quota/claude-bridge':
                return self.respond(200, quota.install_bridge(DATA, data.get('revision')))
            if self.path == '/api/setup/preview':
                return self.respond(200, codex_setup.preview(DATA / 'teams', data.get('path'), data.get('client', 'codex')))
            if self.path == '/api/setup/install':
                return self.respond(200, codex_setup.install(DATA / 'teams', data.get('path'), data.get('revision'), data.get('client', 'codex')))
            if self.path == '/api/credentials':
                try:
                    values = token_store.parse_file(data['fileContent']) if 'fileContent' in data else data.get('keys')
                    return self.respond(200, token_store.save(DATA, values))
                except OSError:
                    return self.respond(400, {'error': 'บันทึก API keys ไม่สำเร็จ กรุณาตรวจสิทธิ์ไฟล์'})
            if self.path == '/api/teams':
                create_team(data['id'], data['title'], data.get('description',''), data.get('workType','general'), data.get('routingMode','recommended'))
            elif self.path in ('/api/save', '/api/create'):
                path = document(data['team'], data['kind'], data.get('id',''))
                if not teamdir(data['team']).is_dir():
                    raise ValueError('Team not found')
                if self.path == '/api/create' and path.exists():
                    raise ValueError('ID นี้มีอยู่แล้ว')
                validate(data['content'], data['kind'], data.get('id',''))
                db=live_agents.connect(DATA)
                try:
                    with db:
                        db.execute('BEGIN IMMEDIATE')
                        if self.path == '/api/save': library_manager.assert_unlocked(db,team_paths.team_id(data['team']))
                        if data['kind']=='agent': library_manager.validate_bindings(teamdir(data['team']),data['content'])
                        if self.path == '/api/create' and path.exists(): raise ValueError('ID นี้มีอยู่แล้ว')
                        write(path, data['content'])
                finally:
                    db.close()
            elif self.path == '/api/export':
                files = export_files(data['team'], data['target'], data.get('agent') or None)
                out = io.BytesIO()
                with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
                    for name, content in files.items():
                        z.writestr(name, content)
                return self.respond(200, out.getvalue(), 'application/zip')
            else:
                return self.respond(404, {'error':'Not found'})
            self.respond(200, state())
        except library_manager.Locked as e:
            self.respond(409, {'error':str(e)})
        except (ValueError, KeyError, TypeError, OSError, EOFError) as e:
            self.respond(400, {'error':str(e)})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4310)
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    print(f'AI Orchestra -> http://127.0.0.1:{args.port}', flush=True)
    def stop_server(_signal, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop_server)
    try:
        ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
    finally:
        terminal_runtime.manager.shutdown()
