/* Pure state mapping shared by the office UI and its tests. */
(function(root){
 const priorities={working:0,waiting:1,unknown:2,failed:3,done:4,closed:4};
 function build(team,runs,connected){
  return team.agents.map(agent=>{
   const sessions=runs.filter(run=>run.team===team.id&&run.agent===agent.id).slice().sort((a,b)=>(priorities[a.status]??2)-(priorities[b.status]??2)||b.updated_at-a.updated_at);
   const current=sessions[0];
   const state=!connected?'unknown':!current?'idle':current.status==='working'?'working':current.status==='waiting'?'waiting':current.status==='failed'?'failed':['done','closed'].includes(current.status)?'idle':'unknown';
   const activeSessions=sessions.filter(run=>['working','waiting','unknown'].includes(run.status));
   const projects=[...new Set(activeSessions.map(run=>run.project))];
   const writing=['writing','research','analysis'].includes(team.workType)||/writer|editor|content|research/i.test(agent.id+' '+(agent.role||''));
   return {stats:agent.stats||{coins:0,rating:0,rank:{name:'Rookie',badge:'◇',level:1}},appearance:agent.appearance||{},id:agent.id,displayName:agent.displayName||agent.id,role:agent.role||'',state,activity:writing?'writing':'computer',project:projects.join(' / ')||null,projects,
    engine:current?.engine||null,updatedAt:current?.updated_at||null,sessions,
    skills:agent.skills||[],skillMode:agent.skillMode||'shared',
    label:{working:'กำลังทำงาน',waiting:'รอผู้ใช้ / รองาน',idle:'พัก · ไม่มีงานค้าง',unknown:'ไม่ทราบสถานะ',failed:'งานมีข้อผิดพลาด'}[state],
    note:!current?'ยังไม่มีรายงานเซสชัน':state==='idle'?'เซสชันล่าสุดจบแล้ว':null};
  });
 }
 const api={build};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.OfficeState=api;
})(typeof globalThis!=='undefined'?globalThis:this);
