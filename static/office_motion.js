/* Deterministic, testable ambient movement; never changes real run state. */
(function(root){
 const WIDTH=576,ROW=144;
 const home=index=>({x:128+(index%3)*160,y:136+Math.floor(index/3)*ROW});
 const hash=text=>[...text].reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0,0);
 function create(actor,index){const h=home(index);return {x:h.x+42,y:h.y+49,state:null,phase:0,path:[],hold:0,action:'rest',walking:false,seed:hash(actor.id),speed:42+hash(actor.id)%12}}
 function route(entity,target,index,height){
  const h=home(index),breakLane=height-102;
  const aisle=entity.x<288?28:548;
  const startLane=entity.y>h.y+88?breakLane:h.y+80;
  const targetLane=target.y>h.y+88?breakLane:h.y+80;
  return [{x:entity.x,y:startLane},{x:aisle,y:startLane},{x:aisle,y:targetLane},{x:target.x,y:targetLane},target];
 }
 function plan(entity,actor,index,height){
  const h=home(index);
  if(actor.state==='working'){
   entity.path=route(entity,{x:h.x,y:h.y+29},index,height);
   entity.destination=actor.activity==='writing'?'writing':'typing';entity.wait=Infinity;entity.travel='walking-desk';
  }else if(actor.state==='waiting'){
   const target={x:entity.phase%2?548:28,y:h.y+80};
   entity.path=route(entity,target,index,height);entity.destination='phone';entity.wait=.6;entity.travel='walking-phone';entity.phase++;
  }else if(actor.state==='idle'){
   const options=[{x:124,y:height-55,action:'coffee',hold:4},{x:532,y:height-58,action:'reading',hold:5},
    {x:235+(index%3)*48,y:height-58,action:'rest',hold:4},{x:h.x+42,y:h.y+49,action:'sleep',hold:5}];
   const target=options[(entity.phase+index)%options.length];entity.phase++;
   entity.path=route(entity,target,index,height);entity.destination=target.action;entity.wait=target.hold;
   entity.travel={'coffee':'walking-coffee',reading:'walking-books',rest:'walking-sofa',sleep:'walking-sofa'}[target.action];
  }else{entity.path=[];entity.destination=actor.state;entity.wait=Infinity;entity.travel=actor.state}
  entity.action=entity.path.length?entity.travel:entity.destination;
 }
 function advance(entity,actor,index,height,dt){
  if(entity.state!==actor.state||entity.activity!==actor.activity){entity.state=actor.state;entity.activity=actor.activity;entity.phase=0;entity.hold=0;plan(entity,actor,index,height)}
  if(!(dt>0)){entity.walking=false;return entity}
  if(!entity.path.length){
   entity.walking=false;entity.hold-=dt;
   if(entity.hold<=0&&['idle','waiting'].includes(actor.state))plan(entity,actor,index,height);
   else return entity;
  }
  let distance=entity.speed*dt;
  entity.walking=true;entity.action=entity.travel;
  while(entity.path.length&&distance>0){
   const target=entity.path[0],dx=target.x-entity.x,dy=target.y-entity.y,length=Math.hypot(dx,dy);
   if(length<=distance){entity.x=target.x;entity.y=target.y;distance-=length;entity.path.shift()}
   else{entity.x+=dx/length*distance;entity.y+=dy/length*distance;distance=0}
  }
  if(!entity.path.length){entity.walking=false;entity.action=entity.destination;entity.hold=entity.wait}
  return entity;
 }
 const api={home,create,advance};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OfficeMotion=api;
})(typeof globalThis!=='undefined'?globalThis:this);
