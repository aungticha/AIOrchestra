const assert=require('node:assert/strict');
const motion=require('../static/office_motion.js');
const idle={id:'idle-engineer',state:'idle',activity:'computer'},height=352;
const entity=motion.create(idle,0),start={x:entity.x,y:entity.y};
for(let i=0;i<25;i++)motion.advance(entity,idle,0,height,.08);
assert.ok(Math.hypot(entity.x-start.x,entity.y-start.y)>50,'Idle actor must visibly travel rather than sit in place');
const actions=new Set();
for(let i=0;i<3000;i++){motion.advance(entity,idle,0,height,.08);actions.add(entity.action);assert.ok(entity.x>=20&&entity.x<=550);assert.ok(entity.y>=70&&entity.y<height-30)}
for(const action of ['coffee','reading','rest','sleep'])assert.ok(actions.has(action),'Missing idle activity: '+action);
const frozen={x:entity.x,y:entity.y,phase:entity.phase};
for(let i=0;i<100;i++)motion.advance(entity,idle,0,height,0);
assert.equal(entity.x,frozen.x);assert.equal(entity.y,frozen.y);assert.equal(entity.phase,frozen.phase);
const working={...idle,state:'working'};
for(let i=0;i<1000;i++)motion.advance(entity,working,0,height,.08);
assert.equal(entity.x,motion.home(0).x);assert.equal(entity.y,motion.home(0).y+29);assert.equal(entity.action,'typing');
const same={x:entity.x,y:entity.y};
for(let i=0;i<100;i++)motion.advance(entity,{...working},0,height,.08);
assert.deepEqual({x:entity.x,y:entity.y},same,'Polling same state must not reset route');
const waiting={...idle,state:'waiting'},caller=motion.create(waiting,0);let min=Infinity,max=-Infinity;
for(let i=0;i<1000;i++){motion.advance(caller,waiting,0,height,.08);min=Math.min(min,caller.x);max=Math.max(max,caller.x)}
assert.ok(max-min>400,'Waiting actor must walk around the office');
const unknown={...idle,state:'unknown'},lost=motion.create(unknown,0),original={x:lost.x,y:lost.y};
for(let i=0;i<100;i++)motion.advance(lost,unknown,0,height,.08);
assert.deepEqual({x:lost.x,y:lost.y},original);assert.equal(lost.action,'unknown');
console.log('Office movement checks passed: roaming, coffee, reading, rest, sleep, phone, desk, pause, stable polling');
