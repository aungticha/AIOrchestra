"""Explicit Editorial planning scope and role-local completion contracts."""
import copy

FULL='full'
PLANNING='planning-only'


def planning_graph(graph,reference_mode='original'):
    if graph.get('kind')!='editorial':raise ValueError('Planning-only is available for Editorial')
    if reference_mode not in ('original','reference-based'):raise ValueError('Invalid reference mode')
    value=copy.deepcopy(graph)
    position=next(i for i,g in enumerate(value['groups']) if any(n.get('gate')==1 and n['id'] in g for n in value['nodes']))
    value['groups']=value['groups'][:position+1]
    ids={key for group in value['groups'] for key in group}
    value['nodes']=[node for node in value['nodes'] if node['id'] in ids]
    value.update(scope=PLANNING,reference_mode=reference_mode)
    return value


def is_planning(record):
    return record['graph'].get('scope',FULL)==PLANNING


def requires_reference(record):
    return not is_planning(record) or record['graph'].get('reference_mode','original')=='reference-based'


def check_plan(record):
    writers=[node for node in record['graph']['nodes'] if node.get('agent')=='script-storyboard-writer' and node.get('enabled')]
    outputs=[record['outputs'].get(node['id'],{}) for node in writers]
    if not any(out.get('passed') and not out.get('blocked') and out.get('storyboard','').strip() and any(a['kind']=='plan' for a in out.get('artifacts',[])) for out in outputs):
        raise ValueError('Writer must deliver a real script/storyboard planning file before Accept 1')


def stage_contract(record,node):
    agent=node['agent']
    common='Stage-local result: passed=true means YOUR assigned deliverables are complete, not that the entire workflow is ready for acceptance. blocked=true only for a missing prerequisite that prevents YOUR current stage. Never block on deliverables owned by later agents or launch the next agent yourself. Report limitations honestly; do not turn a real current-stage blocker into success.'
    if node['phase']!='plan':
        contracts={'work':'Produce real requested media/preview only within the approved scope. Graphic/Audio own separate assets; Editor assembles without modifying their originals.', 'review':'QA must inspect actual preview/evidence and source traceability, not a timeline alone. Set replan_required=true for material factual/story changes needing renewed Accept 1, false for editing-only corrections.', 'export':'Export only after recorded Accept 2, using an available real tool. Return a real final file; otherwise blocked=true. CapCut draft scripts do not export by themselves.'}
        return common+'\n'+contracts[node['phase']]
    roles={
        'video-producer':'Producer: deliver the brief, constraints, proposed scope and handoff. A completed brief is passed=true even when Researcher has not chosen the story, Writer has not written the script/storyboard, or visual clips cannot be inspected yet. Record uninspected candidates and access limits for the Writer; do not require inspected visual references at this stage. Leave storyboard empty.',
        'content-researcher-story-producer':'Researcher: verify factual sources and deliver the sourced Story Plan with claim/source IDs. Do not block because Writer has not produced dialogue/storyboard or because video-style references are uninspected. Missing access to sources essential to your own claims remains a real blocker. Leave storyboard empty.',
        'script-storyboard-writer':'Writer: use the verified Story Plan, write scene-level spoken lines and an original timestamped storyboard, and save a real artifact of kind plan. Review source traceability and requested duration. The controller checks acceptance after your stage, not during Producer.'}
    mode='Planning-only: original presentation. No reference clip was requested: do not invent or require one. Factual source URLs still require verification. Do not require footage, audiovisual inspection, CapCut, preview, production or export. Your deliverable is the plan for future user filming.' if is_planning(record) and not requires_reference(record) else 'Reference-based: Writer must inspect the requested visual reference with real tools before claiming it inspected. Missing essential visual-reference access is a Writer blocker, not automatically a Producer/Researcher blocker.'
    return '\n'.join([common,roles.get(agent,'Complete only this assigned planning role.'),mode])


def install_instructions(workspace,team):
    """Update only managed handoff guidance; keep user profiles and run snapshots."""
    import library_manager
    import live_agents
    import team_paths
    folder=team_paths.team_dir(workspace,team)
    db=live_agents.connect(workspace)
    try:
        if db.execute("SELECT 1 FROM runs WHERE team=? AND status NOT IN ('done','failed','closed') LIMIT 1",(team,)).fetchone():raise library_manager.Locked('Stop active agent sessions before updating stage guidance')
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'").fetchone() and db.execute("SELECT 1 FROM workflows WHERE team=? AND state IN ('planning','designing','implementing','reviewing','testing','publishing','cancelling') LIMIT 1",(team,)).fetchone():raise library_manager.Locked('Stop active workers before updating stage guidance')
    finally:db.close()
    notes={
        'agents/video-producer.md':'Complete the brief and handoff, then set passed=true. Missing Researcher/Writer deliverables or uninspected visual candidates are not your stage blockers. Describe limitations and hand off through the controller. Leave storyboard empty.',
        'agents/content-researcher-story-producer.md':'Complete the verified, sourced Story Plan, then set passed=true. Do not block on future Writer dialogue/storyboard or visual-style inspection. Missing essential factual evidence for your own claims remains blocked=true.',
        'agents/script-storyboard-writer.md':'Deliver the sourced scene dialogue, timed storyboard and a real plan artifact. In original planning-only runs no style-reference clip, footage, preview or CapCut is required. Inspect real clips only when reference-based is explicitly selected.',
        'WORKFLOW.md':'Each stage reports completion of its own assignment, not readiness of the entire workflow. The controller checks Accept 1 after Writer. Full scope retains Accept 1 -> production/QA -> Accept 2 -> export. Explicit planning-only scope runs Producer -> Researcher -> Writer -> User Accept 1 -> completed; no production, QA preview, export or Git. Original planning does not require a visual-reference clip; factual sources still need verification. Reference-based planning requires real visual inspection. Scope reduction of an existing job is explicit, allowed only before acceptance/production with no active worker, and never retries or approves the job.'}
    begin='<!-- EDITORIAL-SCOPE:BEGIN -->';end='<!-- EDITORIAL-SCOPE:END -->'
    for relative,note in notes.items():
        path=library_manager.checked_file(folder,folder/relative)
        if not path.is_file():continue
        text=path.read_text(encoding='utf-8');block=begin+'\n## Stage Completion and Planning Scope\n'+note+'\n'+end
        if begin in text:
            if end not in text:raise ValueError('Incomplete scope guidance marker')
            text=text[:text.index(begin)]+block+text[text.index(end)+len(end):]
        else:text=text.rstrip()+'\n\n'+block+'\n'
        library_manager.write(path,text)
