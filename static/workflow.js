/* Team workflow builder. Only the server advances stages and records approvals. */
let workflowSelected=null,workflowRecord=null,workflowBusy=false,workflowGeneration=0;
let workflowGraph=null,workflowDefault=null,workflowOptions=null,workflowDrag=null,workflowRuns=[];
let workflowConsolePage=false;
const workflowTerminalStates=['completed','cancelled'];
function navigateWorkflow(consolePage=false){if(!canLeave())return;toggleReviews(false);dirty=false;bindingsDirty=false;officePage=false;setupPage=false;settingsPage=false;teamId=null;workflowPage=true;workflowConsolePage=consolePage;workflowGeneration++;render()}
function wfCopy(value){return JSON.parse(JSON.stringify(value))}
function wfNode(id){return workflowGraph.nodes.find(n=>n.id===id)}
function wfTeam(){return data.teams.find(t=>t.id===$('#wfTeam')?.value)}
function wfError(error){const target=$('#wfConsoleError')||$('#wfError');if(target)target.textContent=error.message||String(error)}
function wfConnected(){return workflowOptions.engines.filter(e=>e.connected&&e.installed)}
function wfRecommended(team){return (team.recommendedModels||[]).map(f=>workflowOptions.families[f]).find(pair=>pair&&workflowOptions.engines.some(e=>e.id===pair[0]&&e.installed))||[workflowOptions.engines.find(e=>e.installed)?.id||'Codex','']}
function wfModelOptions(engine,current=''){
    const values=[...new Set(['',...(workflowOptions.engines.find(e=>e.id===engine)?.models||[]),current])];
    return values.map(model=>`<option value="${esc(model)}" ${model===current?'selected':''}>${esc(model||'CLI default')}</option>`).join('');
}
function wfAssignDefaults(){
    const pair=wfRecommended(wfTeam()),connected=wfConnected();
    workflowGraph.nodes.filter(n=>n.agent).forEach(n=>{n.engine=n.engine||pair[0];n.model=n.model??(n.engine===pair[0]?pair[1]:'');if(connected.length===1&&n.engine!==connected[0].id){n.engine=connected[0].id;n.model=''}});
}
async function wfLoadTeam(){
    const team=wfTeam(),generation=++workflowGeneration;
    workflowGraph=null;if($('#wfStart'))$('#wfStart').disabled=true;
    if(!team)return;
    try{
        const template=await api('/api/workflows/template?team='+encodeURIComponent(team.id));
        if(generation!==workflowGeneration||!workflowPage||workflowConsolePage)return;
        workflowGraph=template.graph;workflowDefault=template.default;wfAssignDefaults();wfPaintBuilder();
        $('#wfScopeField').hidden=workflowGraph.kind!=='editorial';$('#wfScope').value=workflowGraph.scope||'full';
        $('#wfReferenceMode').hidden=$('#wfScope').value!=='planning-only';wfPaintBuilder();
        $('#wfGitOptions').hidden=workflowGraph.kind!=='development';
        $('#wfReferenceField').hidden=workflowGraph.kind!=='editorial';
        $('#wfProjectHelp').textContent=workflowGraph.kind==='development'?'Git root ที่มี initial commit และไม่มีงานค้าง · ทำใน worktree แยก':'โฟลเดอร์โปรเจค/สื่อในเครื่อง · แต่ละงานใช้โฟลเดอร์ผลลัพธ์แยก';
        $('#wfStart').disabled=!workflowOptions.engines.some(e=>e.installed);
        $('#wfError').textContent=wfConnected().length===1?'Auto provider: '+wfConnected()[0].id+' · ทุก Agent ใช้ CLI ที่ Connected อยู่':'';
    }catch(error){workflowGraph=null;$('#wfBuilder').innerHTML='';$('#wfStart').disabled=true;wfError(error)}
}
function wfPaintBuilder(){
    if(!workflowGraph||!$('#wfBuilder'))return;
    const team=wfTeam();
    $('#wfKind').textContent=workflowGraph.kind;
    $('#wfBuilder').innerHTML=workflowGraph.groups.map((group,index)=>($('#wfScope')?.value==='planning-only'&&index>workflowGraph.groups.findIndex(g=>g.some(id=>wfNode(id).gate===1)))?'':`<section class="wf-group" data-group="${index}"><div class="wf-group-title">${index+1} ${group.length>1?'∥ Parallel':'→ Sequential'} <small>ลากลงพื้นที่นี้ = ทำขนานกัน</small></div><div class="wf-group-cards">${group.map(id=>wfCard(wfNode(id),index,team)).join('')}</div></section>`).join('');
    $('#wfBuilder').querySelectorAll('[data-node]').forEach(card=>{
        const node=wfNode(card.dataset.node);
        card.ondragstart=event=>{if(event.target.closest('select,input,button')){event.preventDefault();return}workflowDrag=node.id;event.dataTransfer.setData('text/plain',node.id)};
        card.querySelector('[data-enabled]')?.addEventListener('change',event=>{node.enabled=event.target.checked;card.classList.toggle('disabled',!node.enabled)});
        card.querySelector('[data-agent]')?.addEventListener('change',event=>{node.agent=event.target.value});
        card.querySelector('[data-engine]')?.addEventListener('change',event=>{node.engine=event.target.value;node.model='';card.querySelector('[data-model]').innerHTML=wfModelOptions(node.engine)});
        card.querySelector('[data-model]')?.addEventListener('change',event=>{node.model=event.target.value});
        card.querySelectorAll('[data-move]').forEach(button=>button.onclick=()=>wfMove(node.id,button.dataset.move));
    });
    $('#wfBuilder').querySelectorAll('[data-group]').forEach(group=>{
        group.ondragover=event=>{event.preventDefault();group.classList.add('drop-target')};
        group.ondragleave=()=>group.classList.remove('drop-target');
        group.ondrop=event=>{event.preventDefault();const id=workflowDrag||event.dataTransfer.getData('text/plain');workflowDrag=null;wfPlace(id,Number(group.dataset.group))};
    });
}
function wfCard(node,index,team){
    const gate=node.gate||node.publish;
    const heading=node.gate?'User Accept '+node.gate:node.publish?'Commit / Push':(team.agents.find(a=>a.id===node.agent)?.displayName||node.agent)+(node.id==='assemble'?' · รวมงาน':node.phase==='export'?' · Export':'');
    return `<article class="wf-node ${node.enabled?'':'disabled'} ${gate?'wf-gate-node':''}" data-node="${esc(node.id)}" draggable="${!gate}"><header><strong>${esc(heading)}</strong>${!gate?`<label class="wf-enable"><input type="checkbox" data-enabled ${node.enabled?'checked':''}> ใช้</label>`:''}</header>${!gate?`<small>${esc(node.phase)} · ${esc(node.id)}</small><label>Agent<select data-agent>${team.agents.map(a=>`<option value="${esc(a.id)}" ${a.id===node.agent?'selected':''}>${esc(a.displayName||a.id)} · ${esc(a.role||a.id)}</option>`).join('')}</select></label><label>CLI<select data-engine>${workflowOptions.engines.map(e=>`<option value="${e.id}" ${e.id===node.engine?'selected':''} ${e.installed&&!(wfConnected().length===1&&!e.connected)?'':'disabled'}>${e.id}${e.connected?' · Connected':e.installed?'':' · ไม่พบ CLI'}</option>`).join('')}</select></label><label>Model ID<select data-model>${wfModelOptions(node.engine,node.model)}</select></label><div class="wf-node-tools"><button type="button" data-move="up" aria-label="ย้ายขั้นก่อนหน้า">↑</button><button type="button" data-move="down" aria-label="ย้ายขั้นถัดไป">↓</button><button type="button" data-move="parallel" title="รวมกลุ่มกับขั้นก่อนหน้า">∥</button><button type="button" data-move="split" title="แยกเป็นขั้นตอนเดี่ยว">↳</button></div>`:'<small>ต้องอนุมัติโดยผู้ใช้ · ปิดไม่ได้</small>'}</article>`;
}
function wfPlace(id,target){
    const node=wfNode(id),group=workflowGraph.groups[target];
    if(!node||node.gate||node.publish||group.some(key=>wfNode(key).gate||wfNode(key).publish))return wfError(new Error('Accept/Publish เป็นขั้นตอนเดี่ยว กรุณาย้ายด้วย ↑ ↓'));
    workflowGraph.groups.forEach(g=>{const position=g.indexOf(id);if(position>=0)g.splice(position,1)});
    group.push(id);workflowGraph.groups=workflowGraph.groups.filter(g=>g.length);wfPaintBuilder();
}
function wfMove(id,direction){
    const groups=workflowGraph.groups,index=groups.findIndex(g=>g.includes(id));
    if(direction==='parallel'){if(index>0)wfPlace(id,index-1);return}
    if(direction==='split'){if(groups[index].length>1){groups[index]=groups[index].filter(k=>k!==id);groups.splice(index+1,0,[id])}wfPaintBuilder();return}
    const next=index+(direction==='up'?-1:1);if(next<0||next>=groups.length)return;
    if(groups[index].length===1)[groups[index],groups[next]]=[groups[next],groups[index]];
    else{groups[index]=groups[index].filter(k=>k!==id);groups.splice(direction==='up'?index:index+1,0,[id])}
    wfPaintBuilder();
}
async function renderWorkflow(){
    const generation=++workflowGeneration;
    $('#content').innerHTML=`<div class="eyebrow">TEAM WORKFLOWS</div><div class="section-head"><h1>Workflow</h1></div><p>Agent ตามทีม · ลากเรียงขั้นตอน / ลากข้างกันเพื่อ Parallel · User Accept สองจุด</p><div class="wf-workspace"><section class="workflow-create"><h2>เริ่มงานใหม่</h2><form id="workflowForm"><label>ทีม<select id="wfTeam">${data.teams.map(t=>`<option value="${esc(t.id)}">${esc(title(t))}</option>`).join('')}</select></label><label id="wfScopeField">ขอบเขตงาน (เฉพาะงานนี้)<select id="wfScope"><option value="full">ผลิตเต็มรูปแบบ · Accept 1 และ 2</option><option value="planning-only">วางแผนเท่านั้น · จบหลัง Accept 1</option></select></label><label id="wfReferenceMode" hidden>แนวทางภาพ<select id="wfReferenceModeValue"><option value="original">ออกแบบเอง · ไม่บังคับคลิปอ้างอิง</option><option value="reference-based">อิงคลิปตัวอย่าง · ต้องตรวจคลิปจริง</option></select></label><label>Project folder<input id="wfProject" required placeholder="/Users/you/project หรือ C:\\projects\\video"></label><p class="muted" id="wfProjectHelp"></p><label>โจทย์<textarea id="wfTask" required maxlength="8000"></textarea></label><label id="wfReferenceField">Reference URL / file URL (ไม่มีก็ให้ทีมค้นหาก่อน Accept 1)<textarea id="wfReferences" placeholder="https://… หนึ่งรายการต่อบรรทัด"></textarea></label><div id="wfGitOptions"><label class="workflow-check"><input type="checkbox" id="wfPush"> Push หลัง Accept 2</label><label>Remote<input id="wfRemote" value="origin"></label></div><p class="muted">ใช้ CLI และบัญชีที่ login ในเครื่อง · ดู log และยกเลิกงานได้ที่เมนู งานที่รัน / Console</p><button class="primary" id="wfStart" disabled>เริ่ม Workflow</button><p id="wfError" role="alert"></p></form><h2>งานทั้งหมด</h2><div id="workflowList"></div></section><section class="wf-main"><div class="section-head"><h2>Workflow Builder <small id="wfKind"></small></h2><div class="wf-actions"><button class="secondary" id="wfSave">บันทึกของทีม</button><button class="secondary" id="wfReset">Reset default</button></div></div><p class="muted">การแก้/Reset มีผลกับงานใหม่เท่านั้น · ขั้นที่ปิดจะไม่เรียก CLI · ระบบตรวจลำดับก่อนเริ่ม</p><details id="wfBuilderPanel" open><summary>จัดลำดับ / แก้ไข Workflow</summary><div id="wfBuilder"></div></details><section id="workflowDetail" class="workflow-detail"><p>เลือกงานเพื่อดูสถานะและผลลัพธ์</p></section></section></div>`;
    $('#workflowNav').classList.add('active');
    workflowOptions=await api('/api/terminal/options').catch(error=>{wfError(error);return null});
    if(generation!==workflowGeneration||!workflowPage||!workflowOptions)return;
    $('#wfTeam').value=(data.teams.find(t=>t.id==='editor')||data.teams.find(t=>t.id==='developer')||data.teams[0])?.id||'';
    $('#wfProject').value=localStorage.getItem('aiorchestra-project')||workflowOptions.defaultProject;
    $('#wfTeam').onchange=wfLoadTeam;
    $('#wfScope').onchange=()=>{$('#wfReferenceMode').hidden=$('#wfScope').value!=='planning-only';wfPaintBuilder()};
    $('#wfReset').onclick=()=>{if(!workflowDefault)return;workflowGraph=wfCopy(workflowDefault);wfAssignDefaults();wfPaintBuilder();$('#wfError').textContent='Reset แล้ว · บันทึกของทีมหากต้องการเก็บค่า default นี้'};
    $('#wfSave').onclick=async()=>{try{await api('/api/workflows/template',{team:wfTeam().id,graph:workflowGraph});$('#wfError').textContent='บันทึก workflow ของทีมแล้ว'}catch(error){wfError(error)}};
    $('#workflowForm').onsubmit=wfStart;
    await wfLoadTeam();await refreshWorkflows();
}
async function wfStart(event){
    event.preventDefault();if(!workflowGraph)return;$('#wfStart').disabled=true;$('#wfError').textContent='';
    try{
        const roles={};workflowGraph.nodes.filter(n=>n.agent).forEach(n=>{roles[n.id]={agent:n.agent,engine:n.engine,model:n.model||''}});
        const run=await api('/api/workflows/create',{team:wfTeam().id,graph:workflowGraph,scope:workflowGraph.kind==='editorial'?$('#wfScope').value:'full',reference_mode:$('#wfReferenceModeValue').value,roles,project:$('#wfProject').value.trim(),task:$('#wfTask').value,references:$('#wfReferences').value.split('\n').map(s=>s.trim()).filter(Boolean),push:workflowGraph.kind==='development'&&$('#wfPush').checked,remote:$('#wfRemote').value.trim()});
        workflowSelected=run.id;workflowRecord=null;if($('#wfBuilderPanel'))$('#wfBuilderPanel').open=false;await refreshWorkflows();refreshLive();
    }catch(error){wfError(error)}finally{if($('#wfStart'))$('#wfStart').disabled=false}
}
function workflowResult(role,result,run){
    return `<details class="workflow-result" open><summary>${esc(role)} · ${result.passed?'✓':'ต้องแก้'} ${esc(result.summary)}</summary><pre>${esc(result.details)}</pre>${result.storyboard?`<h4>Storyboard</h4><pre>${esc(result.storyboard)}</pre>`:''}${(result.references||[]).map(ref=>`<p>${wfReferenceLink(ref)} · ${ref.inspected?'ตรวจคลิปแล้ว':'ยังไม่ตรวจคลิป'}<br>${esc(ref.evidence)}</p>`).join('')}${(result.findings||[]).length?'<h4>Findings</h4><ul>'+result.findings.map(f=>`<li>${esc(f)}</li>`).join('')+'</ul>':''}${(result.tests||[]).length?'<h4>Checks / Evidence</h4><ul>'+result.tests.map(f=>`<li>${esc(f)}</li>`).join('')+'</ul>':''}${(result.artifacts||[]).map(a=>wfArtifact(run,a)).join('')}</details>`;
}
function wfArtifact(run,item){
    const url='/api/workflows/artifact?id='+encodeURIComponent(run.id)+'&path='+encodeURIComponent(item.path);
    const video=['preview','final'].includes(item.kind)&&/\.(mp4|mov|webm|m4v)$/i.test(item.path);
    return `<p>${esc(item.kind)}: <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">เปิดผลลัพธ์</a> <code>${esc(item.path)}</code></p>${video?`<video class="wf-preview" controls preload="metadata" src="${esc(url)}"></video>`:''}`;
}
function wfReferenceLink(ref){
    if(!/^https?:\/\//i.test(ref.url))return `<code>${esc(ref.url)}</code>`;
    return `<a href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.title||ref.url)}</a>`;
}
function wfRoute(run){
    if(!run.graph)return 'Tech Lead → UI/UX → Accept 1 → Frontend ∥ Backend → Review → QA → Accept 2 → Commit/Push';
    const nodes=Object.fromEntries(run.graph.nodes.map(n=>[n.id,n]));
    return run.graph.groups.map(g=>g.filter(id=>nodes[id].enabled).map(id=>nodes[id].gate?'Accept '+nodes[id].gate:nodes[id].publish?'Commit/Push':nodes[id].agent+(nodes[id].phase==='export'?' (Export)':'')).join(' ∥ ')).filter(Boolean).join(' → ');
}
function paintWorkflow(run){
    const panel=$('#workflowDetail');if(!panel)return;
    if(panel.contains(document.activeElement)&&workflowRecord?.id===run.id)return;
    const draft=workflowRecord?.id===run.id?($('#wfFeedback')?.value||''):'';
    workflowRecord=run;const gate=['awaiting_plan','awaiting_delivery'].includes(run.state),stage=run.state==='awaiting_plan'?1:2;
    const editorial=run.graph?.kind==='editorial',planning=run.graph?.scope==='planning-only',needsReference=editorial&&(!planning||run.graph.reference_mode==='reference-based');
    panel.innerHTML=`<div class="section-head"><h2>${esc(run.label)}</h2><span>${esc(run.id.slice(0,8))}</span></div><p class="workflow-task">${esc(run.task)}</p><div class="workflow-route">${esc(wfRoute(run))}</div><p class="muted">${esc(run.project)} · ${esc(run.state)} · รอบแก้ ${run.round}/${run.max_rounds}</p>${run.error?`<p class="workflow-error" role="alert">${esc(run.error)}</p>`:''}${run.output_root?`<p class="muted">ผลลัพธ์: <code>${esc(run.output_root)}</code></p>`:''}${run.worktrees?.candidate?`<p class="muted">Candidate: <code>${esc(run.worktrees.candidate)}</code></p>`:''}<div class="workflow-steps">${(run.steps||[]).map(s=>`<div><strong>${esc(s.agent||s.role)}</strong><small>${esc(s.engine)} · ${esc(s.model||'CLI default')} · ${esc(s.state)}</small></div>`).join('')}</div>${Object.entries(run.outputs||{}).map(([role,result])=>workflowResult(role,result,run)).join('')}${run.diff?`<details><summary>Candidate diff</summary><pre>${esc(run.diff)}</pre></details>`:''}${gate?`<section class="workflow-gate"><h3>User Accept ${stage}</h3><p>${stage===1?(planning?'ตรวจข่าว / บท / Storyboard / แผนถ่าย · Accept แล้วจบงานวางแผน':'ตรวจ reference / Storyboard / แผนที่แสดง ก่อนเริ่มงาน'):editorial?'ตรวจ Preview และ QA ก่อน Export ไฟล์สุดท้าย':'ตรวจผล Review/QA ก่อนส่งมอบหรือ Commit'}</p>${needsReference&&stage===1?`<label>Reference ที่อนุมัติ<select id="wfSelectedReference"><option value="">เลือก reference ที่มี Storyboard</option>${(run.reference_candidates||[]).filter((ref,i,all)=>all.findIndex(r=>r.url===ref.url)===i).map(ref=>`<option value="${esc(ref.url)}" ${ref.inspected?'':'disabled'}>${esc(ref.title||ref.url)}${ref.inspected?'':' · ยังไม่ได้ตรวจคลิป'}</option>`).join('')}</select></label>`:''}${stage===1&&run.graph?(run.graph.nodes.filter(n=>n.optional).map(n=>`<label class="workflow-check"><input type="checkbox" data-gate-optional="${esc(n.id)}" ${n.enabled?'checked':''}> ${esc(n.agent)} · ใช้เมื่อจำเป็น</label>`).join('')):''}<label>ความคิดเห็น / ขอแก้<textarea id="wfFeedback" maxlength="4000"></textarea></label><div class="review-actions"><button class="primary" data-wf-action="approve">Accept ${stage}</button><button class="secondary" data-wf-action="revise">ขอแก้ไข</button></div></section>`:''}${run.kind==='graph'&&['failed','interrupted'].includes(run.state)?`<section class="workflow-gate"><h3>ส่งข้อมูลเพิ่ม / วางแผนใหม่</h3>${editorial&&!planning&&!(run.approvals||[]).length?'<label>รูปแบบแผน<select id="wfExistingReferenceMode"><option value="original">ออกแบบเอง · ไม่บังคับคลิปอ้างอิง</option><option value="reference-based">อิงคลิปตัวอย่าง · ต้องตรวจคลิปจริง</option></select></label><button class="secondary" data-wf-action="set_scope">ปรับเป็นวางแผนเท่านั้น (ยังไม่ Retry)</button>':''}<label>ข้อมูลที่เพิ่มหรือสิ่งที่ต้องแก้<textarea id="wfFeedback" maxlength="4000"></textarea></label><label>Reference URL / file URL<textarea id="wfReviseReferences">${esc((run.references||[]).join('\n'))}</textarea></label><button class="secondary" data-wf-action="revise">ส่งข้อมูลและวางแผนใหม่</button></section>`:''}<div class="review-actions">${['failed','interrupted'].includes(run.state)?'<button class="primary" data-wf-action="retry">Retry ขั้นที่ค้าง</button>':''}<button class="secondary danger" id="wfCloseRun">${workflowTerminalStates.includes(run.state)?'ปิดรายการ':'ปิด / ยกเลิกงาน'}</button></div>${run.commit?`<p>Commit: <code>${esc(run.commit)}</code> · ${run.pushed?'Push แล้ว':'ยังไม่ Push'}</p>`:''}<p id="wfActionError" role="alert"></p>`;
    if($('#wfFeedback'))$('#wfFeedback').value=draft;
    panel.querySelectorAll('[data-wf-action]').forEach(button=>button.onclick=()=>wfAction(run,button.dataset.wfAction,{scope:'planning-only',reference_mode:$('#wfExistingReferenceMode')?.value||'original',feedback:$('#wfFeedback')?.value||'',selected_reference:$('#wfSelectedReference')?.value||'',references:$('#wfReviseReferences')?$('#wfReviseReferences').value.split('\n').map(s=>s.trim()).filter(Boolean):(run.references||[]),optional_nodes:Object.fromEntries([...panel.querySelectorAll('[data-gate-optional]')].map(el=>[el.dataset.gateOptional,el.checked]))}));
    $('#wfCloseRun').onclick=()=>wfClose(run.id);
}
async function wfAction(run,action,extra={}){
    try{const latest=await api('/api/workflows/action',{id:run.id,revision:run.revision,action,...extra});workflowRecord=null;paintWorkflow(latest);await refreshWorkflows();refreshLive();return latest}
    catch(error){if($('#wfActionError'))$('#wfActionError').textContent=error.message;else wfError(error);return null}
}
async function wfClose(id){
    try{
        let run=await api('/api/workflows/run?id='+encodeURIComponent(id));
        if(!workflowTerminalStates.includes(run.state))run=await api('/api/workflows/action',{id:run.id,revision:run.revision,action:'cancel'});
        await api('/api/workflows/action',{id:run.id,revision:run.revision,action:'dismiss'});
        if(workflowSelected===id){workflowSelected=null;workflowRecord=null;if($('#workflowDetail'))$('#workflowDetail').innerHTML='<p>ปิดรายการแล้ว</p>'}
        await refreshWorkflows();refreshLive();
    }catch(error){wfError(error)}
}
function renderWorkflowConsole(){
    workflowGeneration++;
    $('#content').innerHTML=`<div class="eyebrow">WORKFLOW MONITOR</div><h1>งานที่รัน / Console</h1><p>ดูสถานะและ CLI log ของแต่ละ Workflow · กด × เพื่อยกเลิกงานและปิด console · งานที่ Error ก็ปิดได้</p><p id="wfConsoleError" role="alert"></p><div id="wfConsoleSummary" class="wf-console-summary"></div><div id="wfConsoleJobs" class="wf-console-jobs"></div><h2>Single Agents</h2><div id="agentConsoleJobs" class="wf-console-jobs"></div>`;
    refreshWorkflows();
}
function wfPaintConsole(){
    const container=$('#wfConsoleJobs');if(!container)return;
    const previous=new Map([...container.querySelectorAll('[data-log-id]')].map(el=>[el.dataset.logId,{open:el.open,scroll:el.querySelector('pre')?.scrollTop||0,bottom:!el.querySelector('pre')||el.querySelector('pre').scrollHeight-el.querySelector('pre').scrollTop-el.querySelector('pre').clientHeight<40}]));
    const active=workflowRuns.filter(r=>!['completed','cancelled','failed','interrupted'].includes(r.state)).length;
    $('#wfConsoleSummary').textContent=`กำลังทำงาน / รออนุมัติ ${active} · Error / หยุดค้าง ${workflowRuns.filter(r=>['failed','interrupted'].includes(r.state)).length} · ทั้งหมด ${workflowRuns.length}`;
    container.innerHTML=workflowRuns.map(run=>`<details class="wf-job-console" data-log-id="${esc(run.id)}" ${previous.get(run.id)?.open===false?'':'open'}><summary><span><strong>${esc(run.task.slice(0,100))}</strong><small>${esc(run.team)} · ${esc(run.label)} · ${esc(run.id.slice(0,8))}</small></span><span class="wf-job-state ${['failed','interrupted'].includes(run.state)?'error':''}">${esc(run.state)}</span></summary><div class="wf-job-actions"><button class="secondary" data-console-select="${run.id}">ดูรายละเอียด / Accept</button><button class="secondary danger" data-console-close="${run.id}" aria-label="ปิด Console ${esc(run.id.slice(0,8))}">× ${workflowTerminalStates.includes(run.state)?'ปิด Console':'ปิด Console / ยกเลิกงาน'}</button></div><p class="muted">${esc(run.project)}</p>${run.error?`<p class="workflow-error">${esc(run.error)}</p>`:''}<pre>${esc((run.steps||[]).map(step=>'['+(step.agent||step.role)+' · '+step.engine+' · '+(step.model||'CLI default')+' · '+step.state+']\n'+(step.log||step.error||'รอ CLI output…')).join('\n\n')||'ยังไม่มี CLI output')}</pre></details>`).join('')||'<div class="workflow-detail"><p>ยังไม่มี Workflow ที่เปิดอยู่ · เริ่มงานได้จากเมนู Workflow</p></div>';
    container.querySelectorAll('[data-log-id]').forEach(el=>{const pre=el.querySelector('pre'),old=previous.get(el.dataset.logId);pre.scrollTop=old?.bottom===false?old.scroll:pre.scrollHeight});
    container.querySelectorAll('[data-console-close]').forEach(button=>button.onclick=async()=>{button.disabled=true;await wfClose(button.dataset.consoleClose)});
    container.querySelectorAll('[data-console-select]').forEach(button=>button.onclick=()=>{workflowSelected=button.dataset.consoleSelect;workflowRecord=null;navigateWorkflow(false)});
}
async function refreshWorkflowBadge(){
    if(workflowPage)return;
    try{const result=await api('/api/workflows');if($('#wfRunningCount'))$('#wfRunningCount').textContent=result.workflows.filter(r=>!workflowTerminalStates.includes(r.state)).length}catch{}
}
async function refreshWorkflows(){
    if(workflowBusy||!workflowPage)return;
    const consolePage=workflowConsolePage,generation=workflowGeneration;
    if(consolePage?!$('#wfConsoleJobs'):!$('#workflowList'))return;
    workflowBusy=true;
    try{
        const result=await api('/api/workflows');
        if(!workflowPage||generation!==workflowGeneration)return;
        $('#wfRunningCount').textContent=result.workflows.filter(r=>!workflowTerminalStates.includes(r.state)).length;
        if(!consolePage){
            $('#workflowList').innerHTML=result.workflows.map(run=>`<button class="workflow-list-item ${run.id===workflowSelected?'selected':''}" data-wf-id="${run.id}"><strong>${esc(run.task.slice(0,65))}</strong><small>${esc(run.team)} · ${esc(run.label)}</small></button>`).join('')||'<p class="muted">ยังไม่มี Workflow</p>';
            document.querySelectorAll('[data-wf-id]').forEach(button=>button.onclick=()=>{workflowSelected=button.dataset.wfId;workflowRecord=null;refreshWorkflows()});
            if(!workflowSelected&&result.workflows.length)workflowSelected=result.workflows[0].id;
        }
        const needed=result.workflows.filter(r=>consolePage||r.id===workflowSelected);
        const details=await Promise.all(needed.map(r=>api('/api/workflows/run?id='+encodeURIComponent(r.id))));
        if(!workflowPage||generation!==workflowGeneration)return;
        workflowRuns=details;
        if(consolePage){wfPaintConsole();await refreshAgentConsoles()}
        else{const selected=details.find(r=>r.id===workflowSelected);if(selected&&(!workflowRecord||workflowRecord.revision!==selected.revision))paintWorkflow(selected)}
    }catch(error){wfError(error)}finally{workflowBusy=false}
}
$('#workflowNav').onclick=()=>navigateWorkflow(false);
$('#workflowConsoleNav').onclick=()=>navigateWorkflow(true);
setInterval(()=>{refreshWorkflows();refreshWorkflowBadge()},2000);
refreshWorkflowBadge();

async function refreshAgentConsoles(){
 const panel=$('#agentConsoleJobs');if(!panel)return;
 try{const result=await api('/api/agents/jobs');if($('#agentConsoleJobs')!==panel)return;
 const opened=new Map([...panel.querySelectorAll('details')].map(e=>[e.dataset.agentJob,e.open]));
 panel.innerHTML=result.jobs.filter(j=>!j.dismissed).map(j=>`<details class="wf-job-console" data-agent-job="${esc(j.id)}" ${opened.get(j.id)===false?'':'open'}><summary><strong>${esc(j.agent)} · ${esc(j.task.slice(0,90))}</strong><span>${esc(j.state)}</span></summary><p>${esc(j.team)} · ${esc(j.engine)} · ${esc(j.model||'CLI default')} · ${esc(j.access)}</p><p>${esc(j.project)}</p><button class="secondary danger" data-agent-close="${esc(j.id)}">× ${j.state==='running'?'ยกเลิกงาน / ปิด':'ปิด'}</button>${j.error?`<p role="alert">${esc(j.error)}</p>`:''}<pre>${esc(j.log||'รอ CLI output…')}</pre>${j.result?`<p>${esc(j.result.summary)}</p><pre>${esc(j.result.details)}</pre>`:''}</details>`).join('')||'<p class="muted">ยังไม่มีงาน Agent เดี่ยว</p>';
 panel.querySelectorAll('[data-agent-close]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await api('/api/agents/cancel',{id:button.dataset.agentClose});await refreshAgentConsoles()}catch(e){wfError(e);button.disabled=false}});
 }catch(e){wfError(e)}
}
