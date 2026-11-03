"""Portable team defaults and validated sequential/parallel workflow graphs."""
import copy
import editorial_scope
import json
import re
from pathlib import Path
import agent_skills
import library_manager
import team_paths

ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
EDITORIAL = ['video-producer', 'script-storyboard-writer', 'video-editor', 'motion-graphic-designer', 'audio-editor', 'video-qa-reviewer']
DEVELOPMENT = ['tech-lead-architect', 'ui-ux-designer', 'frontend-developer', 'backend-developer', 'code-reviewer', 'qa-test-engineer']

def node(identifier, agent=None, phase='work', enabled=True, **extra):
    return {'id': identifier, 'agent': agent or identifier, 'phase': phase, 'enabled': enabled, **extra}

def gate(number):
    return {'id': 'accept-'+str(number), 'gate': number, 'enabled': True}

def defaults(workspace, team):
    folder = team_paths.team_dir(workspace, team)
    agents = {p.stem for p in (folder/'agents').glob('*.md')}
    if not agents:
        raise ValueError('ทีมนี้ยังไม่มี Agent')
    if set(EDITORIAL).issubset(agents):
        nodes = [node(EDITORIAL[0], phase='plan'), node(EDITORIAL[1], phase='plan'), gate(1), node(EDITORIAL[2]), node(EDITORIAL[3], enabled=False, optional=True), node(EDITORIAL[4], enabled=False, optional=True), node('assemble', EDITORIAL[2]), node(EDITORIAL[5], phase='review'), gate(2), node('export', EDITORIAL[2], 'export')]
        groups = [[EDITORIAL[0]], [EDITORIAL[1]], ['accept-1'], EDITORIAL[2:5], ['assemble'], [EDITORIAL[5]], ['accept-2'], ['export']]
        kind = 'editorial'
    elif set(DEVELOPMENT).issubset(agents):
        nodes = [node(DEVELOPMENT[0], phase='plan'), node(DEVELOPMENT[1], phase='plan', enabled=False), gate(1), node(DEVELOPMENT[2]), node(DEVELOPMENT[3]), node(DEVELOPMENT[4], phase='review'), node(DEVELOPMENT[5], phase='review'), gate(2), {'id':'publish','publish':True,'enabled':True}]
        groups = [[DEVELOPMENT[0]], [DEVELOPMENT[1]], ['accept-1'], DEVELOPMENT[2:4], [DEVELOPMENT[4]], [DEVELOPMENT[5]], ['accept-2'], ['publish']]
        kind = 'development'
    else:
        ordered = sorted(agents)
        nodes = [node('plan', ordered[0], 'plan'), gate(1)] + [node(a) for a in ordered] + [node('review', ordered[0], 'review'), gate(2)]
        groups = [[n['id']] for n in nodes]
        kind = 'general'
    graph={'version': 1, 'kind': kind, 'nodes': nodes, 'groups': groups}
    if kind=='editorial':
        import editorial_story
        if editorial_story.AGENT in agents:graph=editorial_story.insert_stage(graph)
    return graph

def validate(workspace, team, graph):
    if not isinstance(graph, dict) or graph.get('version') != 1 or graph.get('kind') not in ('development','editorial','general'):
        raise ValueError('Invalid workflow definition')
    nodes, groups = graph.get('nodes'), graph.get('groups')
    if not isinstance(nodes,list) or not 1 <= len(nodes) <= 40 or not isinstance(groups,list) or not 1 <= len(groups) <= 40:
        raise ValueError('Workflow ต้องมี 1–40 ขั้นตอน')
    by_id = {}
    for item in nodes:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not ID.fullmatch(item['id']) or item['id'] in by_id:
            raise ValueError('Invalid/duplicate node ID')
        if type(item.get('enabled')) is not bool:
            raise ValueError('Invalid enabled flag')
        if sum(('gate' in item, bool(item.get('publish')), 'agent' in item))!=1:
            raise ValueError('Node ต้องเป็น Agent, Accept หรือ Publish เพียงชนิดเดียว')
        if 'gate' in item:
            if type(item['gate']) is not int or item['gate'] not in (1,2) or not item['enabled']:
                raise ValueError('ห้ามปิด User Accept')
        elif item.get('publish'):
            if graph['kind'] != 'development' or item.get('enabled') is not True:
                raise ValueError('Invalid publish step')
        else:
            if item.get('phase') not in ('plan','work','review','export'):
                raise ValueError('Invalid node phase')
            library_manager.checked_file(team_paths.team_dir(workspace,team), team_paths.team_dir(workspace,team)/'agents'/(library_manager.live_agents.identifier(item.get('agent'))+'.md'))
            if not (team_paths.team_dir(workspace,team)/'agents'/(item['agent']+'.md')).is_file():
                raise ValueError('ไม่พบ Agent ในทีมที่เลือก: '+item['agent'])
        by_id[item['id']] = item
    flat = []
    for group in groups:
        if not isinstance(group,list) or not 1 <= len(group) <= 8 or any(not isinstance(key,str) or key not in by_id for key in group):
            raise ValueError('Invalid parallel group')
        if len(group)>1 and any('gate' in by_id[key] or by_id[key].get('publish') for key in group):
            raise ValueError('Accept/Publish ต้องเป็นขั้นตอนเดี่ยว')
        flat.extend(group)
    if len(flat)!=len(set(flat)) or set(flat)!=set(by_id):
        raise ValueError('แต่ละขั้นตอนต้องอยู่ใน workflow เพียงครั้งเดียว')
    active = [by_id[key] for key in flat if by_id[key]['enabled']]
    gates = [n['gate'] for n in active if 'gate' in n]
    scope=graph.get('scope','full')
    if scope not in ('full','planning-only'):raise ValueError('Invalid workflow scope')
    if scope=='planning-only':
        if graph['kind']!='editorial' or graph.get('reference_mode','original') not in ('original','reference-based'):raise ValueError('Invalid planning-only graph')
        if gates!=[1] or active[-1].get('gate')!=1 or len(active)<2 or any(n.get('phase')!='plan' for n in active[:-1]):raise ValueError('Planning-only must contain planning agents then one final Accept 1')
        if any(n.get('phase') not in (None,'plan') or n.get('gate')==2 or n.get('publish') for n in nodes):raise ValueError('Planning-only cannot contain production/export steps, even disabled')
        if not any(n.get('agent')=='script-storyboard-writer' for n in active):raise ValueError('Planning-only requires the Writer')
        return copy.deepcopy(graph)
    if gates != [1,2]:
        raise ValueError('ต้องมี User Accept 1 และ 2 ตามลำดับ')
    first = next(i for i,n in enumerate(active) if n.get('gate')==1)
    second = next(i for i,n in enumerate(active) if n.get('gate')==2)
    if not first or not any(n.get('phase')=='work' for n in active[first+1:second]) or not any(n.get('phase')=='review' for n in active[first+1:second]):
        raise ValueError('ต้องมีแผนก่อน Accept 1 และงาน/QA ก่อน Accept 2')
    if any(n.get('phase')!='plan' for n in active[:first]) or any(n.get('phase') not in ('work','review') for n in active[first+1:second]):
        raise ValueError('แผนต้องอยู่ก่อน Accept 1; งานและ QA อยู่ระหว่าง Accept')
    if active[second-1].get('phase')!='review':
        raise ValueError('ขั้นตอนก่อน Accept 2 ต้องเป็น Review/QA')
    if any(n.get('phase')!='export' and not n.get('publish') for n in active[second+1:]):
        raise ValueError('หลัง Accept 2 ทำได้เฉพาะ Export/Publish')
    if graph['kind']=='editorial' and not any(n.get('phase')=='export' for n in active[second+1:]):
        raise ValueError('Editorial ต้องมี Export หลัง Accept 2')
    if graph['kind']=='development' and (len([n for n in active if n.get('publish')])!=1 or not active[-1].get('publish')):
        raise ValueError('Development ต้องจบด้วย Commit/Publish')
    # A review must run after all writers, never beside a writer in the same group.
    for group in groups:
        phases = {by_id[key].get('phase') for key in group if by_id[key]['enabled']}
        if 'review' in phases and len(phases)>1:
            raise ValueError('Review/QA ห้ามรันขนานกับงานที่กำลังแก้')
    return copy.deepcopy(graph)

def options(workspace, team):
    default = defaults(workspace,team)
    folder=team_paths.team_dir(workspace,team)
    path=library_manager.checked_file(folder,folder/'WORKFLOW.json')
    saved = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default
    return {'default':default,'graph':validate(workspace,team,saved)}

def save(workspace, team, graph):
    value = validate(workspace,team,graph)
    folder = team_paths.team_dir(workspace,team)
    library_manager.write(library_manager.checked_file(folder,folder/'WORKFLOW.json'),json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    return value

def install_editorial(workspace, team):
    """Install requested assets explicitly; never overwrite unrelated profile metadata."""
    folder=team_paths.team_dir(workspace,team)
    if not set(EDITORIAL).issubset({p.stem for p in (folder/'agents').glob('*.md')}):
        raise ValueError('ต้องมี Agent วิดีโอทั้ง 6 บทบาทก่อนติดตั้ง')
    from live_agents import connect
    db=connect(workspace)
    try:library_manager.assert_unlocked(db,team)
    finally:db.close()
    source=Path(__file__).resolve().parent/'integrations'/'editorial'
    skill=folder/'skills'/'reference-video-analysis'/'SKILL.md'
    library_manager.checked_file(folder,skill)
    content=(source/'skills'/'reference-video-analysis'/'SKILL.md').read_text(encoding='utf-8')
    if skill.exists() and skill.read_text(encoding='utf-8')!=content:
        raise ValueError('มี reference-video-analysis ที่แก้ไขเองแล้ว ไม่เขียนทับ')
    skill.parent.mkdir(parents=True,exist_ok=True)
    library_manager.write(skill,content)
    notes={
        'video-producer':'Complete the brief and handoff, then return passed=true. Do not block because later Researcher/Writer deliverables or visual inspection are pending. Discover visual references only when the brief requests them; report access limits honestly.',
        'script-storyboard-writer':'Write sourced scene dialogue and an original timestamped storyboard in a real plan file. Inspect visual references only when required by the run scope. Original planning-only work needs no reference clip, footage or CapCut. Present the plan for Accept 1; do not produce media before approval.',
        'video-editor':'Follow the approved reference/storyboard. Use separate outputs from Graphic/Audio, assemble after their parallel group, and deliver a real preview for QA. Final export waits for Accept 2.',
        'motion-graphic-designer':'Create only the approved graphics needed by the storyboard in your separate output folder; never write the shared CapCut draft.',
        'audio-editor':'Prepare the approved audio work in your separate output folder; never write the shared CapCut draft. Hand tracks and timing to the Editor.',
        'video-qa-reviewer':'Inspect the actual preview against the accepted storyboard/reference and report timestamped findings. Return fixes to production; QA cannot approve on behalf of the user.'}
    for name,note in notes.items():
        path=library_manager.checked_file(folder,folder/'agents'/(name+'.md'))
        text=path.read_text(encoding='utf-8')
        if name in ('video-producer','script-storyboard-writer'):
            assigned=agent_skills.assigned(text)
            if assigned is None:assigned=[p.parent.name for p in (folder/'skills').glob('*/SKILL.md') if p.parent.name!='reference-video-analysis']
            if 'reference-video-analysis' not in assigned:assigned.append('reference-video-analysis')
            text=agent_skills.set_assigned(text,assigned)
        begin='<!-- EDITORIAL-WORKFLOW:BEGIN -->';end='<!-- EDITORIAL-WORKFLOW:END -->'
        block=begin+'\n## Executable Editorial Workflow\n'+note+'\nRead WORKFLOW.md and follow the controller snapshot for this run. Only the controller routes agents and records acceptance.\n'+end
        if begin in text:
            if end not in text:raise ValueError('Incomplete workflow marker: '+name)
            text=text[:text.index(begin)]+block+text[text.index(end)+len(end):]
        else:text=text.rstrip()+'\n\n'+block+'\n'
        library_manager.write(path,text)
    import editorial_story
    editorial_story.install(workspace,team)
    library_manager.write(folder/'WORKFLOW.md',(source/'WORKFLOW.md').read_text(encoding='utf-8'))
    editorial_scope.install_instructions(workspace,team)
    if not (folder/'WORKFLOW.json').exists():save(workspace,team,defaults(workspace,team))
    return {'installed':True,'team':team,'skill':'reference-video-analysis'}
