// Embedded into each export. No blending, interpolation, or external event adapter.
// The same bounded consumer drives ordinary previews, review UI, and local overlays.
const character=document.querySelector('#character'), selector=document.querySelector('#state'), still=document.querySelector('#still');
const contract=metadata.playback||{}, rules=contract.events||{}, queue=[], suspended=[];
const states=new Map(metadata.states.map(state=>[state.id,state]));
const MAX_SUSPENDED=32, MAX_QUEUE_BYPASSES=4;
let selected=metadata.states[0], frameIndex=0, timer=null, deadline=0, remaining=0;
let priority=0, paused=false, completed=false, arrival=0, interruptions=0, protectedTurn=false;
const clock=()=>performance.now();
const mode=()=>selected.playback?.mode||'loop';
const staticIndex=()=>selected.playback?.reduced_motion_frame??selected.static_frame;
const visibleIndex=()=>still.checked?staticIndex():frameIndex;
const stop=()=>{if(timer!==null)clearTimeout(timer);timer=null};
const legal=(rule,id=selected.id)=>!rule.from||rule.from.includes(id);
const canTick=()=>!still.checked&&!paused&&!document.hidden&&!completed&&(mode()!=='hold'||queue.length>0);
character.width=metadata.layout.cell_width;character.height=metadata.layout.cell_height;
const reduced=matchMedia('(prefers-reduced-motion: reduce)');still.checked=reduced.matches;
document.querySelector('#origin').textContent=metadata.fixture?'Deterministic fixture / no production acceptance':metadata.source||'';
for(const state of metadata.states){const option=document.createElement('option');option.value=state.id;option.textContent=state.id;selector.append(option)}
// Decode ahead of playback. Browser timer and display refresh limits still apply.
const preloaded=metadata.states.flatMap(s=>s.frames.map(f=>{const img=new Image();img.src=f.path;return img}));

function render(){
  const index=visibleIndex(), frame=selected.frames[index];
  character.src=still.checked&&index===selected.static_frame?selected.static:frame.path;
  character.alt=selected.purpose;
  character.style.imageRendering=selected.alignment?.resampling==='nearest'?'pixelated':'auto';
  character.dataset.state=selected.id;character.dataset.frameIndex=String(index);character.dataset.durationMs=String(frame.duration_ms);
  document.querySelector('#status').textContent=selected.id+' / '+index+' / '+frame.duration_ms+' ms'+(completed?' / complete':'')+(paused?' / paused':'');
}

function schedule(){
  stop();
  if(canTick())timer=setTimeout(tick,Math.max(0,deadline-clock()));
}

function refresh(){render();schedule()}

// Freeze only an actually running deadline. Repeated visibility/pause changes
// must not subtract hidden time from the already-saved remaining duration.
function freeze(){
  if(timer!==null)remaining=Math.max(0,deadline-clock());
  stop();
}

function install(id,nextPriority=0,at=clock(),protect=false){
  const state=states.get(id);if(!state)return false;
  stop();selected=state;priority=nextPriority;selector.value=id;completed=false;protectedTurn=protect;
  frameIndex=state.playback?.mode==='hold'?(state.playback.hold_frame??0):0;
  remaining=state.frames[frameIndex].duration_ms;deadline=at+remaining;
  return true;
}

function snapshot(at){
  return {id:selected.id,index:frameIndex,priority,completed,protectedTurn,
    remaining:canTick()?Math.max(0,deadline-at):remaining};
}

function restore(saved,at){
  stop();selected=states.get(saved.id);selector.value=selected.id;
  frameIndex=saved.index;priority=saved.priority;completed=saved.completed;protectedTurn=saved.protectedTurn;
  remaining=saved.remaining;deadline=at+remaining;
}

function activate(item,at=clock(),protect=false){
  if(item.rule.resume&&!still.checked){
    // A completed one-shot has nothing to suspend. Preserve its prior return
    // stack so queued resumable notifications can finish before restoring work.
    if(!completed){
      if(suspended.length>=MAX_SUSPENDED)return false;
      suspended.push(snapshot(at));
    }
  }else suspended.length=0;
  return install(item.rule.target,item.rule.priority,at,protect);
}

function drain(at){
  // Check legality in the state that reached the boundary, before applying its
  // default completion. Coalescing never changes a waiting event's age/order.
  for(let i=queue.length-1;i>=0;i--){
    const item=queue[i];
    if(!legal(item.rule)||(item.rule.target===selected.id&&!item.rule.restart))queue.splice(i,1);
  }
  if(!queue.length)return false;
  const overdue=queue.filter(item=>item.bypasses>=MAX_QUEUE_BYPASSES);
  const candidate=overdue.length?
    overdue.reduce((a,b)=>a.order<b.order?a:b):
    queue.reduce((a,b)=>a.rule.priority>b.rule.priority||(a.rule.priority===b.rule.priority&&a.order<b.order)?a:b);
  queue.splice(queue.indexOf(candidate),1);
  for(const item of queue)item.bypasses++;
  interruptions=0;
  // Promotion includes one complete turn: a new flood must not immediately
  // cut the overdue performance before the browser has a chance to show it.
  return activate(candidate,at,overdue.length>0);
}

function boundary(at){
  const previousMode=mode(), completion=selected.playback?.completion;
  completed=previousMode==='once';
  if(completed)remaining=0;
  interruptions=0;protectedTurn=false;
  if(drain(at))return;
  if(previousMode==='once'){
    if(suspended.length)restore(suspended.pop(),at);
    else if(completion)install(completion,0,at);
    // Otherwise retain the last frame, with no timer, until an event/selection.
  }else if(previousMode==='loop'){
    frameIndex=0;remaining=selected.frames[0].duration_ms;deadline=at+remaining;
  }else{
    // Holds never animate. A queued event gets a finite, safe dispatch boundary;
    // with no queue there is no timer and the configured pose stays indefinitely.
    remaining=selected.frames[frameIndex].duration_ms;deadline=at+remaining;
  }
}

function tick(){
  timer=null;const now=clock();let steps=0;
  // Absolute deadlines avoid accumulated lateness across frames and completions.
  // Catch-up is bounded even after timer throttling or exceptionally late tasks.
  while(canTick()&&now>=deadline&&steps<256){
    const at=deadline;steps++;
    if(mode()==='hold'||frameIndex+1===selected.frames.length)boundary(at);
    else{
      frameIndex++;remaining=selected.frames[frameIndex].duration_ms;deadline=at+remaining;
    }
  }
  if(steps===256&&canTick()&&now>=deadline){remaining=selected.frames[frameIndex].duration_ms;deadline=now+remaining}
  refresh();
}

function selectState(id){
  if(!states.has(id))return false;
  queue.length=0;suspended.length=0;interruptions=0;paused=false;
  install(id);refresh();return true;
}

function dispatchLocalEvent(name){
  if(typeof name!=='string'||!Object.hasOwn(metadata.events,name))return false;
  const target=metadata.events[name], declared=Object.hasOwn(rules,name);
  const rule={target,priority:0,interrupt:'always',restart:!declared,resume:false,...(declared?rules[name]:{})};
  if(!legal(rule))return false;
  if(target===selected.id&&!rule.restart)return true;
  if(!still.checked&&rule.resume&&!completed&&suspended.length>=MAX_SUSPENDED)return false;
  const item={name,rule,order:arrival++,bypasses:0};
  // Static feedback has no in-flight motion to interrupt. It changes only in
  // response to an explicit event and never schedules an invisible animation.
  let canInterrupt=still.checked||completed||((selected.playback?.interruptible!==false)&&
    (rule.interrupt==='always'||(rule.interrupt==='higher'&&rule.priority>priority)));
  if(protectedTurn&&!still.checked&&!completed)canInterrupt=false;
  if(!still.checked&&!completed&&queue.length&&interruptions>=(contract.max_consecutive_interruptions??4))canInterrupt=false;
  if(canInterrupt){
    const pending=queue.findIndex(e=>e.name===name);
    if(pending>=0)queue.splice(pending,1);
    if(queue.length)interruptions++;else interruptions=0;
    if(!activate(item))return false;
    refresh();return true;
  }
  const existing=queue.find(e=>e.name===name);
  if(existing)return true;
  if(queue.length>=(contract.queue_limit??8))return false;
  queue.push(item);
  if(mode()==='hold'&&!paused&&!document.hidden)deadline=Math.max(deadline,clock());
  refresh();return true;
}

function pause(value=true){
  if(typeof value!=='boolean')return false;
  if(value===paused)return true;
  if(value)freeze();else deadline=clock()+remaining;
  paused=value;refresh();return true;
}

function resume(){return pause(false)}

function step(amount=1){
  if(!Number.isInteger(amount)||Math.abs(amount)>64)return false;
  pause(true);completed=false;frameIndex=((frameIndex+amount)%selected.frames.length+selected.frames.length)%selected.frames.length;
  remaining=selected.frames[frameIndex].duration_ms;render();return true;
}

function cancel(){return selectState(contract.cancel_state||metadata.static_state)}

function changeReduced(value){
  freeze();still.checked=value;queue.length=0;suspended.length=0;interruptions=0;
  deadline=clock()+remaining;refresh();
}

selector.onchange=()=>selectState(selector.value);
still.onchange=()=>changeReduced(still.checked);
reduced.addEventListener('change',e=>changeReduced(e.matches));
document.addEventListener('visibilitychange',()=>{
  if(document.hidden)freeze();else{deadline=clock()+remaining;schedule()}
});
window.hatchPet={selectState,dispatchLocalEvent,pause,resume,step,cancel,metadata,get playback(){return {
  state:selected.id,index:visibleIndex(),animationIndex:frameIndex,reducedMotion:still.checked,paused,completed,priority,
  queued:queue.map(x=>x.name),suspended:suspended.map(x=>x.id),protectedTurn,deadline,
  remainingMs:timer!==null?Math.max(0,deadline-clock()):remaining
}}};
window.addEventListener('hatch-pet-event',e=>dispatchLocalEvent(e.detail));
window.addEventListener('message',e=>{if(e.source===window.parent&&e.data?.type==='hatch-select')selectState(e.data.state)});
let eventIndex=0;document.querySelector('#event').onclick=()=>{const names=Object.keys(metadata.events);if(names.length)dispatchLocalEvent(names[eventIndex++%names.length])};
document.querySelector('#pause').onclick=()=>pause(!paused);
document.querySelector('#previous').onclick=()=>step(-1);document.querySelector('#next').onclick=()=>step(1);
document.querySelector('#cancel').onclick=cancel;
document.querySelector('#background').onchange=e=>document.querySelector('#viewport').dataset.background=e.target.value;
const params=new URLSearchParams(location.search);if(params.get('overlay')==='1')document.body.classList.add('overlay');
selectState(states.has(params.get('state'))?params.get('state'):(contract.initial||metadata.static_state));
