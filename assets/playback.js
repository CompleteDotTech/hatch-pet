// Embedded into each export. All state transitions use this same bounded consumer.
const character=document.querySelector('#character'), selector=document.querySelector('#state'), still=document.querySelector('#still');
const contract=metadata.playback||{}, rules=contract.events||{}, queue=[];
let selected=metadata.states[0], frameIndex=0, timer=null, deadline=0, remaining=0, priority=0, paused=false, completed=false;
const clock=()=>performance.now();
const mode=()=>selected.playback?.mode||'loop';
const stop=()=>{if(timer!==null)clearTimeout(timer);timer=null};
character.width=metadata.layout.cell_width;character.height=metadata.layout.cell_height;
const reduced=matchMedia('(prefers-reduced-motion: reduce)');still.checked=reduced.matches;
document.querySelector('#origin').textContent=metadata.fixture?'Deterministic fixture / no production acceptance':metadata.source||'';
for(const state of metadata.states){const option=document.createElement('option');option.value=state.id;option.textContent=state.id;selector.append(option)}
// Decode ahead of playback. Browser timer and display refresh limits still apply.
const preloaded=metadata.states.flatMap(s=>s.frames.map(f=>{const img=new Image();img.src=f.path;return img}));
function render(){
  const index=still.checked?selected.static_frame:frameIndex, frame=selected.frames[index];
  character.src=still.checked?selected.static:frame.path;character.alt=selected.purpose;
  character.style.imageRendering=selected.alignment?.resampling==='nearest'?'pixelated':'auto';
  character.dataset.state=selected.id;character.dataset.frameIndex=String(index);character.dataset.durationMs=String(frame.duration_ms);
  document.querySelector('#status').textContent=selected.id+' / '+index+' / '+frame.duration_ms+' ms'+(completed?' / complete':'');
}
function schedule(){
  stop();
  if(still.checked||paused||document.hidden||mode()==='hold'||completed)return;
  timer=setTimeout(tick,Math.max(0,deadline-clock()));
}
function drain(){
  queue.sort((a,b)=>b.rule.priority-a.rule.priority);
  while(queue.length){const item=queue.shift();if(!item.rule.from||item.rule.from.includes(selected.id)){start(item.rule.target,item.rule.priority);return true}}
  return false;
}
function advance(){
  if(frameIndex+1<selected.frames.length){frameIndex++;return true}
  if(mode()==='loop'){frameIndex=0;return true}
  completed=true;
  if(selected.playback?.completion)start(selected.playback.completion,0);
  drain();
  return false;
}
function tick(){
  timer=null;let now=clock(), steps=0;
  // Absolute deadlines avoid accumulating callback lateness. Bound catch-up work.
  while(now>=deadline&&steps++<256&&!completed){
    if(!advance()){render();schedule();return}
    deadline+=selected.frames[frameIndex].duration_ms;
  }
  if(steps>=256)deadline=now+selected.frames[frameIndex].duration_ms;
  render();schedule();
}
function start(id, nextPriority=0){
  const state=metadata.states.find(s=>s.id===id);if(!state)return false;
  stop();selected=state;priority=nextPriority;selector.value=id;completed=false;paused=false;
  frameIndex=still.checked?state.static_frame:(state.playback?.mode==='hold'?(state.playback.hold_frame||0):0);
  remaining=state.frames[frameIndex].duration_ms;deadline=clock()+remaining;render();schedule();return true;
}
function selectState(id){queue.length=0;return start(id)}
function dispatchLocalEvent(name){
  const target=metadata.events[name];if(!target)return false;
  const rule={target,priority:0,interrupt:'always',restart:!rules[name],...rules[name]};
  if(rule.from&&!rule.from.includes(selected.id))return false;
  if(target===selected.id&&!rule.restart)return true;
  const canInterrupt=completed||((selected.playback?.interruptible!==false)&&(rule.interrupt==='always'||(rule.interrupt==='higher'&&rule.priority>priority)));
  if(canInterrupt){return start(target,rule.priority)}
  const existing=queue.findIndex(e=>e.name===name);if(existing>=0)queue.splice(existing,1);
  if(queue.length>=(contract.queue_limit??8))return false;
  queue.push({name,rule});return true;
}
function pause(value=true){
  if(value&&!paused)remaining=Math.max(0,deadline-clock());
  paused=value;if(!value)deadline=clock()+(remaining||selected.frames[frameIndex].duration_ms);
  render();schedule();
}
function step(amount=1){
  if(!Number.isInteger(amount)||Math.abs(amount)>64)return false;
  pause(true);completed=false;frameIndex=((frameIndex+amount)%selected.frames.length+selected.frames.length)%selected.frames.length;
  remaining=selected.frames[frameIndex].duration_ms;render();return true;
}
function cancel(){queue.length=0;return start(contract.cancel_state||metadata.static_state)}
selector.onchange=()=>selectState(selector.value);
still.onchange=()=>{queue.length=0;start(selected.id,priority)};
reduced.addEventListener('change',e=>{still.checked=e.matches;queue.length=0;start(selected.id,priority)});
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){remaining=Math.max(0,deadline-clock());stop()}
  else{deadline=clock()+(remaining||selected.frames[frameIndex].duration_ms);schedule()}
});
window.hatchPet={selectState,dispatchLocalEvent,pause,step,cancel,metadata,get playback(){return {state:selected.id,index:frameIndex,reducedMotion:still.checked,paused,completed,priority,queued:queue.map(x=>x.name),deadline}}};
window.addEventListener('hatch-pet-event',e=>dispatchLocalEvent(e.detail));
window.addEventListener('message',e=>{if(e.source===window.parent&&e.data?.type==='hatch-select')selectState(e.data.state)});
let eventIndex=0;document.querySelector('#event').onclick=()=>{const names=Object.keys(metadata.events);if(names.length)dispatchLocalEvent(names[eventIndex++%names.length])};
document.querySelector('#pause').onclick=()=>pause(!paused);
document.querySelector('#previous').onclick=()=>step(-1);document.querySelector('#next').onclick=()=>step(1);
document.querySelector('#cancel').onclick=cancel;
document.querySelector('#background').onchange=e=>document.querySelector('#viewport').dataset.background=e.target.value;
const params=new URLSearchParams(location.search);if(params.get('overlay')==='1')document.body.classList.add('overlay');
start(params.get('state')||contract.initial||metadata.static_state);
