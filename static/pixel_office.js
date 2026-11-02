/* Hand-drawn, code-native pixel office. No network assets or model calls. */
(function(){
 let canvas,ctx,actors=[],height=300,frame=null,paused=false,started=0,root,selected=null,lastSignature='',lastFrame=0,elapsed=0,motions=new Map();
 const WIDTH=576,COLS=3,CELL=160,ROW=144;
 const palette=['#aa91e5','#6ccbb9','#e8b475','#91b7ee','#df8caa','#a9c977'];
 const hash=s=>[...s].reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0,0);
 const box=(x,y,w,h,color)=>{ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),w,h)};
 function outline(x,y,w,h,fill,edge='#293043'){box(x-2,y-2,w+4,h+4,edge);box(x,y,w,h,fill)}
 // Only floor coordinates are projected. Height always stays vertical on screen.
 function project(x,y,z=0){return {x:.92*x-100/height*y+64,y:.12*x+.78*y+35-z}}
 function viewHeight(){return Math.ceil(.78*height+74)}
 function polygon(points,color){ctx.fillStyle=color;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fill()}
 function shade(hex,factor){const value=parseInt(hex.slice(1),16);return '#'+[16,8,0].map(shift=>Math.max(0,Math.min(255,Math.round(((value>>shift)&255)*factor))).toString(16).padStart(2,'0')).join('')}
 function cube(x,y,z,w,d,h,color){
  const a=project(x-w/2,y-d/2,z),b=project(x+w/2,y-d/2,z),c=project(x+w/2,y+d/2,z),e=project(x-w/2,y+d/2,z);
  const top=p=>({x:p.x,y:p.y-h}),at=top(a),bt=top(b),ct=top(c),et=top(e);
  polygon([e,c,ct,et],shade(color,.78));polygon([b,c,ct,bt],shade(color,.57));polygon([a,b,bt,at],shade(color,.69));polygon([a,e,et,at],shade(color,.87));polygon([at,bt,ct,et],shade(color,1.18));
 }
 function floorRect(x,y,w,d,color){polygon([project(x,y),project(x+w,y),project(x+w,y+d),project(x,y+d)],color)}
 function line(points,color,width=1,glow=0){ctx.save();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.shadowColor=color;ctx.shadowBlur=glow;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();ctx.restore()}
 function shadow(x,y,w,d){ctx.save();ctx.globalAlpha=.3;floorRect(x-w/2,y-d/2,w,d,'#050d16');ctx.restore()}
 function plant(x,y){
  shadow(x+4,y+4,23,20);cube(x,y,0,15,15,14,'#a07870');cube(x,y,12,19,18,4,'#c69b88');cube(x,y,15,4,4,15,'#488762');
  cube(x-5,y,24,13,12,13,'#5ba881');cube(x+5,y-3,29,12,11,15,'#76ba88');cube(x,y-5,38,12,12,12,'#8ac99a');
 }
 function background(){
  // The whole viewport is room floor: no rotated black matte around the room.
  const gradient=ctx.createLinearGradient(0,0,WIDTH,viewHeight());gradient.addColorStop(0,'#203b51');gradient.addColorStop(1,'#142c40');ctx.fillStyle=gradient;ctx.fillRect(0,0,WIDTH,viewHeight());
  for(let y=-120;y<height+180;y+=20)line([project(-180,y),project(800,y)],'#315166');
  for(let x=-200;x<850;x+=20)line([project(x,-150),project(x,height+180)],'#29495d');
  const left=project(-90,0),right=project(750,0);
  polygon([{x:0,y:0},{x:WIDTH,y:0},right,left],'#25344f');
  line([left,right],'#618099',3);line([project(-100,12),project(760,12)],'#65ddec',2,8);
  const rows=Math.max(1,Math.ceil(actors.length/COLS));
  for(let row=0;row<rows;row++){
   const y=80+row*ROW,color=['#edaa7d','#afda9c','#ada1ea'][row%3];
   floorRect(44,y,488,116,'#284257');
   for(let yy=y;yy<y+117;yy+=20)line([project(44,yy),project(532,yy)],'#365569');
   for(let x=44;x<=532;x+=24)line([project(x,y),project(x,y+116)],'#304d60');
   line([project(44,y),project(532,y),project(532,y+116),project(44,y+116),project(44,y)],color,1.5,5);
  }
 }
 function desk(x,y,writing,t){
  shadow(x+7,y+14,102,55);
  for(const dx of [-40,40])for(const dy of [-12,15])cube(x+dx,y+dy,0,5,5,30,'#66778d');
  cube(x,y,29,98,40,5,'#97b7cf');cube(x+34,y+3,1,18,23,27,'#516982');
  if(writing){cube(x-10,y,35,34,24,2,'#f0e5c9');const p=project(x-25,y-8,38);box(p.x,p.y,27,1,'#b8aa91');box(p.x,p.y+5,20,1,'#b8aa91');cube(x+22,y+1,35,21,3,2,'#eac878')}
  else{
   cube(x,y-7,35,10,9,7,'#4e637a');cube(x,y-10,42,46,6,27,'#34465e');
   const p=project(x-20,y-6,65);polygon([{x:p.x,y:p.y},{x:p.x+37,y:p.y+4.8},{x:p.x+37,y:p.y+23},{x:p.x,y:p.y+18.2}],'#7dd4d3');
   line([{x:p.x+4,y:p.y+5},{x:p.x+20,y:p.y+7}],'#d3fff4',2);line([{x:p.x+4,y:p.y+10},{x:p.x+31,y:p.y+13}],'#418a9b',2);
   if(t)line([{x:p.x+4,y:p.y+15},{x:p.x+16+Math.floor(t*2)%2*10,y:p.y+17}],'#c3f4d9',1);
   cube(x-4,y+10,35,36,10,2,'#d9dece');for(let i=0;i<6;i++)cube(x-17+i*5,y+10,37,2,5,1,'#7b8f9d');
  }
  cube(x+35,y+6,35,7,8,9,'#d0ece4');cube(x-36,y-7,35,7,7,6,'#6e9c7c');cube(x-36,y-7,41,8,8,8,'#9bc895');
 }
 function chair(x,y,color='#7b8d9c'){
  shadow(x+3,y+5,30,25);cube(x,y,0,5,5,12,'#44566a');cube(x,y,11,27,23,6,color);cube(x,y+10,17,28,5,19,color);
  cube(x-14,y+1,14,4,21,9,shade(color,.85));cube(x+14,y+1,14,4,21,9,shade(color,.85));
 }
 function coffee(x,y){
  shadow(x+5,y+6,90,40);cube(x,y,0,82,28,29,'#536e87');cube(x,y,29,89,34,5,'#a7cad3');
  cube(x-23,y-3,34,23,20,24,'#344960');const p=project(x-31,y+8,55);box(p.x,p.y,13,9,'#81e7d7');cube(x+9,y+2,34,9,9,10,'#d9ede9');cube(x+25,y-4,34,12,12,7,'#77b7b2');
 }
 function sofa(x,y){
  shadow(x+4,y+7,181,39);cube(x,y,0,177,33,14,'#535a88');cube(x,y+13,14,178,7,23,'#7978ad');
  for(let i=0;i<3;i++)cube(x-54+i*54,y-2,14,49,25,9,'#9d98ca');cube(x-89,y,13,8,38,17,'#8585b6');cube(x+89,y,13,8,38,17,'#8585b6');
 }
 function bookshelf(x,y){
  shadow(x+5,y+6,77,30);cube(x,y,0,76,19,61,'#485c7c');
  for(let row=0;row<3;row++){cube(x,y+10,4+row*19,70,3,3,'#8a9cba');for(let i=0;i<10;i++)cube(x-29+i*6,y+12,7+row*19,4,4,10+i%3*2,palette[(i+row)%palette.length])}
 }
 function person(x,y,color,state,seed,t,pose,appearance){
  const a={gender:'neutral',hairStyle:'short',hairColor:'#493749',shirtColor:color,skinTone:'#e2b99b',outfit:'shirt',...appearance};
  const walking=pose.walking,sitting=!walking&&['typing','writing','rest','sleep'].includes(pose.action),lift=sitting?10:0;
  shadow(x+3,y+4,24,18);
  const step=walking?Math.sin(t*8)*3:0;
  for(const [dx,offset] of [[-5,step],[5,-step]]){cube(x+dx,y+offset,lift,7,11,5,'#28384f');cube(x+dx,y+offset,5+lift,6,7,sitting?6:12,'#46516d')}
  const bodyZ=16+lift;cube(x,y,bodyZ,19,11,17,a.shirtColor);
  if(a.outfit==='hoodie')cube(x,y,bodyZ+15,23,13,5,a.shirtColor);
  const hand=walking?Math.sin(t*8)*3:state==='working'?Math.sin(t*7)*2:0;
  cube(x-13,y+hand,bodyZ+2,5,7,12,a.skinTone);cube(x+13,y-hand,bodyZ+2,5,7,12,a.skinTone);
  const headZ=bodyZ+19;cube(x,y,headZ,19,15,19,a.skinTone);
  if(a.hairStyle!=='bald'){cube(x,y,headZ+15,21,17,6,a.hairColor);cube(x-9,y,headZ+(a.hairStyle==='short'?6:-8),4,16,a.hairStyle==='short'?11:a.hairStyle==='bob'?21:29,a.hairColor);if(a.hairStyle!=='short')cube(x+9,y-2,headZ-6,4,11,a.hairStyle==='long'?26:19,a.hairColor)}
  const face=project(x,y+8,headZ+9);
  if(pose.action==='sleep'){box(face.x-5,face.y,3,1,'#483947');box(face.x+3,face.y+1,3,1,'#483947');ctx.font='9px monospace';ctx.fillStyle='#d7eeff';ctx.fillText('z Z',face.x+15,face.y-12-Math.sin(t)*3)}
  else{box(face.x-5,face.y,2,2,'#3b3446');box(face.x+4,face.y+1,2,2,'#3b3446');box(face.x,face.y+6,3,1,'#b27877')}
  const shirt=project(x,y+6,bodyZ+12);if(a.outfit==='shirt'){box(shirt.x,shirt.y,1,11,'#e1eaf3');box(shirt.x-3,shirt.y,7,2,'#e1eaf3')}if(a.outfit==='hoodie'){box(shirt.x-3,shirt.y,1,5,'#e1eaf3');box(shirt.x+3,shirt.y,1,5,'#e1eaf3')}
  if(state==='waiting')cube(x+15,y,bodyZ+13,5,3,13,'#364a66');
  if(pose.action==='coffee'||pose.action==='rest')cube(x+17,y+4,bodyZ+3,8,8,8,'#f0e0b9');
  if(pose.action==='reading'||pose.action==='writing')cube(x,y+10,bodyZ+4,22,12,2,'#efdfb5');
  if(state==='unknown'||state==='failed'){const p=project(x+19,y,headZ+20);ctx.font='bold 10px monospace';ctx.fillStyle='#f3c3a0';ctx.fillText(state==='failed'?'!':'?',p.x,p.y)}
 }
 function positions(index){return {x:128+(index%COLS)*CELL,y:136+Math.floor(index/COLS)*ROW}}
 function draw(timestamp){
  if(!ctx)return;if(timestamp-lastFrame<80){frame=requestAnimationFrame(draw);return}
  const dt=lastFrame?Math.min((timestamp-lastFrame)/1000,.25):.08;lastFrame=timestamp;
  if(!paused)elapsed+=dt;const t=elapsed;
  ctx.setTransform(1,0,0,1,0,0);ctx.imageSmoothingEnabled=false;background();
  const items=[];
  items.push({y:68,draw:()=>plant(46,68)},{y:68,draw:()=>plant(535,68)});
  items.push({y:height-57,draw:()=>coffee(78,height-57)},{y:height-38,draw:()=>plant(143,height-38)},
   {y:height-48,draw:()=>sofa(288,height-48)},{y:height-44,draw:()=>bookshelf(478,height-44)});
  actors.forEach((actor,index)=>{const {x,y}=positions(index);items.push({y:y+16,draw:()=>desk(x,y,actor.activity==='writing',actor.state==='working'?t:0)});items.push({y:y+60,draw:()=>chair(x+42,y+50)});
   if(actor.state==='working')items.push({y:y+28,draw:()=>chair(x,y+29,'#8d7da5')});
  });
  const sprites=actors.map((actor,index)=>{
   if(!motions.has(actor.id))motions.set(actor.id,OfficeMotion.create(actor,index));
   const pose=motions.get(actor.id);if(pose.slot!==index){pose.slot=index;pose.state=null}OfficeMotion.advance(pose,actor,index,height,paused?0:dt);
   return {actor,pose,index};
  }).sort((a,b)=>a.pose.y-b.pose.y);
  sprites.forEach(({actor,pose})=>items.push({y:pose.y,draw:()=>{
   const seed=hash(actor.id);if(selected===actor.id)line([project(pose.x-14,pose.y+9),project(pose.x+14,pose.y+9)],'#d8c6ff',2,4);
   person(pose.x,pose.y,palette[seed%palette.length],actor.state,seed%100,t,pose,actor.appearance);
   if((actor.stats?.rank?.level||1)>1){const p=project(pose.x,pose.y,78),color=['#94a6bd','#c98958','#d2e1f2','#ffdd70','#79f5ef'][actor.stats.rank.level-1];for(let i=0;i<Math.min(5,actor.stats.rank.level);i++)box(p.x-8+i*4,p.y,3,3,color)}
  }}));
  items.sort((a,b)=>a.y-b.y).forEach(item=>item.draw());
  const occupied=[];
  sprites.forEach(({actor,pose})=>{const label=root.querySelector(`[data-office-label="${actor.id}"]`);if(!label)return;
   const projected=project(pose.x,pose.y);const x=Math.max(8,Math.min(WIDTH-122,projected.x-58));let y=Math.max(45,projected.y-111);
   while(occupied.some(other=>x<other.x+116&&x+116>other.x&&y<other.y+44&&y+44>other.y)&&y>75)y=Math.max(75,y-46);
   occupied.push({x,y});label.style.left=(x/WIDTH*100)+'%';label.style.top=(y/viewHeight()*100)+'%';
   const activity=paused?'ภาพหยุดอยู่':actionLabel(pose.action);const text=activity+(actor.state==='working'&&actor.project?' · '+actor.project:'');label.querySelector('.office-current-action').textContent=text;label.title=actor.label+' · '+text;label.setAttribute('aria-label',(actor.displayName||actor.id)+': '+actor.label+', '+text);
  });
  frame=requestAnimationFrame(draw);
 }
 const actionLabel=action=>({
  'walking-coffee':'เดินไปมุมกาแฟ','walking-books':'เดินไปชั้นหนังสือ','walking-sofa':'เดินไปพักผ่อน','walking-desk':'เดินไปโต๊ะทำงาน',
  'walking-phone':'เดินคุยโทรศัพท์',phone:'คุยโทรศัพท์',coffee:'ดื่มกาแฟ',reading:'อ่านหนังสือ',rest:'นั่งพักบนโซฟา',sleep:'กำลังหลับ',typing:'ทำงานหน้าคอม',writing:'เขียนหนังสือ',unknown:'รอสัญญาณสถานะ',failed:'รอแก้ไขข้อผิดพลาด'
 }[action]||'พักผ่อน');
 function update(next){
  actors=next;const ids=new Set(next.map(actor=>actor.id));for(const id of motions.keys())if(!ids.has(id))motions.delete(id);
  const signature=JSON.stringify(next.map(a=>({stats:a.stats,appearance:a.appearance,id:a.id,displayName:a.displayName,role:a.role,state:a.state,project:a.project,engine:a.engine,label:a.label})));
  if(signature===lastSignature)return;lastSignature=signature;
  const previousHeight=height;
  height=132+Math.max(1,Math.ceil(actors.length/COLS))*ROW+76;
  if(height!==previousHeight)for(const pose of motions.values()){pose.y=Math.min(pose.y,height-43);pose.state=null}
  canvas.height=viewHeight();canvas.width=WIDTH;root.style.aspectRatio=WIDTH+'/'+viewHeight();
  const labels=root.querySelector('.office-labels');labels.replaceChildren();
  actors.forEach((actor,index)=>{const {x,y}=positions(index);const button=document.createElement('button');button.type='button';button.dataset.officeLabel=actor.id;button.className='office-actor-label office-state-'+actor.state;button.style.left=((x-65)/WIDTH*100)+'%';button.style.top=((y-110)/viewHeight()*100)+'%';button.style.width=(116/WIDTH*100)+'%';button.setAttribute('aria-label',`${actor.displayName||actor.id}: ${actor.label}, ${actor.project||'ไม่มีโปรเจคที่กำลังทำ'}`);
   const name=document.createElement('strong');name.textContent=actor.displayName||actor.id;name.title=(actor.displayName||actor.id)+(actor.role?' · '+actor.role:'')+' · ID: '+actor.id;button.append(name);const dot=document.createElement('i');dot.className='office-status-dot';dot.setAttribute('aria-hidden','true');button.append(dot);const activity=document.createElement('small');activity.className='office-current-action';activity.textContent=actor.state==='working'?'กำลังทำงาน':'พักผ่อน';button.append(activity);button.title=actor.label+(actor.project?' · '+actor.project:'');button.onclick=()=>{selected=actor.id;root.dispatchEvent(new CustomEvent('office-select',{detail:actor.id,bubbles:true}))};labels.append(button)});
 }
 function mount(element,next){destroy();root=element;root.innerHTML='<canvas class="pixel-office-canvas" aria-hidden="true"></canvas><div class="office-labels"></div>';canvas=root.querySelector('canvas');ctx=canvas.getContext('2d');canvas.onclick=event=>{const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width*WIDTH,y=(event.clientY-rect.top)/rect.height*viewHeight();let closest=null,distance=Infinity;for(const actor of actors){const pose=motions.get(actor.id);if(!pose)continue;const foot=project(pose.x,pose.y),point=project(pose.x,pose.y,34),d=Math.hypot(point.x-x,point.y-y);if(Math.abs(x-foot.x)<=25&&y>=foot.y-82&&y<=foot.y+9&&d<distance){distance=d;closest=actor.id}}if(closest)root.dispatchEvent(new CustomEvent('office-select',{detail:closest,bubbles:true}))};started=performance.now();elapsed=0;lastFrame=0;motions=new Map();lastSignature='';selected=null;update(next);frame=requestAnimationFrame(draw)}
 function preview(target,appearance){
  const previous=ctx,previewContext=target.getContext('2d');if(!previewContext)return;
  ctx=previewContext;
  try{
   ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,target.width,target.height);ctx.imageSmoothingEnabled=false;
   ctx.save();ctx.translate(target.width/2,target.height-30);ctx.scale(2.8,2.8);ctx.translate(-64,-35);
   person(0,0,'#a995ef','idle',0,0,{walking:false,action:'standing'},appearance);
   ctx.restore();
  }finally{ctx=previous}
 }
 function destroy(){motions.clear();if(frame!==null)cancelAnimationFrame(frame);frame=null;ctx=null;canvas=null;root=null;lastSignature=''}
 function pause(value){paused=Boolean(value)}
 window.PixelOffice={mount,update,destroy,pause,actionLabel,preview,select:id=>{selected=id}};
})();
