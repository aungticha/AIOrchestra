"""Install the storytelling role without replacing existing team customizations."""
import copy
import json
from pathlib import Path
import agent_skills
import library_manager
import team_paths

AGENT='content-researcher-story-producer'

def install(workspace, team):
    folder=team_paths.team_dir(workspace,team)
    source=Path(__file__).resolve().parent/'integrations'/'editorial'
    for relative in ['skills/story-research/SKILL.md','agents/'+AGENT+'.md']:
        target=library_manager.checked_file(folder,folder/relative)
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            library_manager.write(target,(source/relative).read_text(encoding='utf-8'))
    notes={
        'video-producer':'Pass the brief to Content Researcher / Story Producer when factual research or narrative planning is needed; then hand its Story Plan to the Writer. Keep visual-reference discovery separate from factual content evidence.',
        'script-storyboard-writer':'Read the researched Story Plan first. Write dialogue per scene with claim/source IDs, then combine it with visual-reference analysis. Accept 1 covers content sources, narrative, script and storyboard.',
        'video-qa-reviewer':'Use story-research to check facts, quotations, chronology and context against cited sources, as well as preview quality. Return material factual/story changes to planning and renewed Accept 1.'}
    for name,note in notes.items():
        path=library_manager.checked_file(folder,folder/'agents'/(name+'.md'))
        text=path.read_text(encoding='utf-8')
        if name in ('script-storyboard-writer','video-qa-reviewer'):
            assigned=agent_skills.assigned(text)
            if assigned is not None and 'story-research' not in assigned:text=agent_skills.set_assigned(text,[*assigned,'story-research'])
        begin='<!-- STORY-RESEARCH:BEGIN -->';end='<!-- STORY-RESEARCH:END -->'
        block=begin+'\n## Story Research Handoff\n'+note+'\n'+end
        if begin in text:
            if end not in text:raise ValueError('Incomplete story handoff marker: '+name)
            text=text[:text.index(begin)]+block+text[text.index(end)+len(end):]
        else:text=text.rstrip()+'\n\n'+block+'\n'
        library_manager.write(path,text)
    path=library_manager.checked_file(folder,folder/'WORKFLOW.json')
    if path.exists():
        graph=json.loads(path.read_text(encoding='utf-8'))
        graph=insert_stage(graph)
        library_manager.write(path,json.dumps(graph,ensure_ascii=False,indent=2)+'\n')

def insert_stage(graph):
    graph=copy.deepcopy(graph)
    if any(n['id']==AGENT for n in graph['nodes']):return graph
    writers=[n for n in graph['nodes'] if n.get('agent')=='script-storyboard-writer' and n.get('phase')=='plan']
    if graph.get('kind')!='editorial' or not writers:return graph
    writer=writers[0]
    entry={'id':AGENT,'agent':AGENT,'phase':'plan','enabled':True}
    for key in ('engine','model'):
        if key in writer:entry[key]=writer[key]
    graph['nodes'].insert(graph['nodes'].index(writer),entry)
    position=next(i for i,group in enumerate(graph['groups']) if writer['id'] in group)
    graph['groups'].insert(position,[AGENT])
    return graph
