"""Run the shipped JS engine with deterministic DOM/clock shims and strict profiles.

Node supplies JavaScript execution, not a replacement animation implementation.
Actual exported PNG/HTML behavior is also exercised by test_playback_extended.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from fixture_workflow import small_profile
from profile_spec import load_profile, profile_hash

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')

DOM_CLOCK = r'''
const assert=require('node:assert/strict');
const elements=new Map(), listeners=new Map(), mediaListeners=new Map();
function element(id){
  if(!elements.has(id))elements.set(id,{value:'',checked:false,dataset:{},style:{},
    classList:{add(){}},append(){},textContent:'',src:'',alt:''});
  return elements.get(id);
}
global.window=global;window.parent=window;
window.addEventListener=(name,fn)=>listeners.set(name,fn);
global.location={search:''};
global.document={hidden:false,querySelector:element,createElement:()=>({}),
  body:element('body'),addEventListener:(name,fn)=>listeners.set(name,fn)};
global.matchMedia=()=>({matches:false,addEventListener:(name,fn)=>mediaListeners.set(name,fn)});
global.Image=class {set src(value){this.path=value}};
let testTime=0,serial=0;
const timers=new Map();
Object.defineProperty(performance,'now',{value:()=>testTime});
global.setTimeout=(callback,delay)=>{const id=++serial;timers.set(id,{callback,due:testTime+delay});return id};
global.clearTimeout=id=>timers.delete(id);
function advance(ms){
  const end=testTime+ms;let iterations=0;
  while(timers.size){
    const [id,timer]=[...timers.entries()].sort((a,b)=>a[1].due-b[1].due)[0];
    if(timer.due>end)break;
    if(++iterations>2000)throw Error('unbounded timer work');
    testTime=timer.due;timers.delete(id);timer.callback();
  }
  testTime=end;
}
function late(ms){
  testTime+=ms;
  const [id,timer]=[...timers.entries()].sort((a,b)=>a[1].due-b[1].due)[0];
  timers.delete(id);timer.callback();
}
function hidden(flag){document.hidden=flag;listeners.get('visibilitychange')()}
function setReduced(flag){mediaListeners.get('change')({matches:flag})}
function playback(){return hatchPet.playback}
function send(name){return hatchPet.dispatchLocalEvent(name)}
'''


def runtime_metadata(profile):
    p = load_profile(profile)
    return {
        'states': [
            {
                **state,
                'frames': [
                    {'path': f'frames/{state["id"]}/{index:02d}.png', 'duration_ms': duration}
                    for index, duration in enumerate(state['durations'])
                ],
                'static_frame': state.get('playback', {}).get(
                    'reduced_motion_frame',
                    p['export']['static_frame'] if state['id'] == p['export']['static_state'] else 0),
                'static': f'static/{state["id"]}.png',
            }
            for state in p['states']
        ],
        'layout': p['layout'], 'events': p['events'], 'playback': p.get('playback', {}),
        'static_state': p['export']['static_state'], 'fixture': True,
    }


class PlaybackValidation(unittest.TestCase):
    def test_new_fields_serialize_and_preserve_default_contract(self):
        p = small_profile()
        p['states'][1]['playback'] = {'mode': 'once', 'completion': 'rest', 'reduced_motion_frame': 2}
        p['playback'] = {'max_consecutive_interruptions': 2, 'events': {
            'success': {'target': 'jump', 'resume': True, 'restart': False}}}
        validated = load_profile(p)
        self.assertEqual(validated, load_profile(json.loads(json.dumps(validated))))
        self.assertEqual(profile_hash(p), profile_hash(validated))
        codex = load_profile()
        self.assertNotIn('playback', codex)
        self.assertTrue(all('playback' not in state for state in codex['states']))
        self.assertEqual((codex['layout']['rows'], codex['layout']['columns'],
                          codex['layout']['cell_width'], codex['layout']['cell_height']), (9, 8, 192, 208))

    def test_malformed_playback_is_always_a_value_error(self):
        mutations = [
            lambda p: p.update(playback=[]),
            lambda p: p.update(playback={'initial': []}),
            lambda p: p.update(playback={'cancel_state': {}}),
            lambda p: p.update(playback={'events': []}),
            lambda p: p.update(playback={'events': {4: {}}}),
            lambda p: p.update(playback={'events': {'success': []}}),
            lambda p: p.update(playback={'events': {'success': {'target': []}}}),
            lambda p: p.update(playback={'events': {'success': {'target': 'jump', 'from': [{}]}}}),
            lambda p: p.update(playback={'events': {'success': {'target': 'jump', 'from': ['rest', 'rest']}}}),
            lambda p: p['states'][0].update(playback=[]),
            lambda p: p['states'][0].update(playback={'mode': 'once', 'completion': []}),
            lambda p: p['states'][0].update(playback={'unexpected': 1}),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                p = small_profile()
                mutate(p)
                with self.assertRaises(ValueError):
                    load_profile(p)

    def test_strict_static_frame_queue_and_interruption_limits(self):
        for key in ('queue_limit', 'max_consecutive_interruptions'):
            for value in (True, -1, 33, 1.0, [], None):
                with self.subTest(key=key, value=value):
                    p = small_profile()
                    p['playback'] = {key: value}
                    with self.assertRaises(ValueError):
                        load_profile(p)
        for value in (True, -1, 3, 1.0, [], None):
            with self.subTest(frame=value):
                p = small_profile()
                p['states'][0]['playback'] = {'reduced_motion_frame': value}
                with self.assertRaisesRegex(ValueError, 'reduced_motion_frame'):
                    load_profile(p)

    def test_resume_requires_finite_once_target(self):
        for value in ('yes', 1, [], None, True):
            with self.subTest(resume=value):
                p = small_profile()
                p['playback'] = {'events': {'success': {'target': 'jump', 'resume': value}}}
                with self.assertRaisesRegex(ValueError, 'resume'):
                    load_profile(p)
        p['states'][1]['playback'] = {'mode': 'once', 'completion': 'rest'}
        self.assertTrue(load_profile(p)['playback']['events']['success']['resume'])

    def test_completion_cycles_and_invalid_targets_fail(self):
        p = small_profile()
        p['states'][0]['playback'] = {'mode': 'once', 'completion': 'jump'}
        p['states'][1]['playback'] = {'mode': 'once', 'completion': 'rest'}
        with self.assertRaisesRegex(ValueError, 'completion cycle'):
            load_profile(p)
        p['states'][1]['playback'] = {'mode': 'hold'}
        self.assertEqual(load_profile(p)['states'][0]['playback']['completion'], 'jump')
        p['states'][0]['playback']['completion'] = 'absent'
        with self.assertRaisesRegex(ValueError, 'existing state'):
            load_profile(p)


@unittest.skipUnless(NODE, 'Node is required to execute the shipped JavaScript engine')
class StatePlaybackRuntime(unittest.TestCase):
    def execute(self, profile, script, search=''):
        source = (ROOT / 'assets/playback.js').read_text(encoding='utf-8')
        runner = DOM_CLOCK + '\nconst metadata=' + json.dumps(runtime_metadata(profile)) + ';\n'
        runner += 'location.search=' + json.dumps(search) + ';\n' + source + '\n' + script
        # Large real catalog recipes exceed Windows' process-argument limit.
        # Feed the same exported engine and assertions through Node's stdin.
        result = subprocess.run([NODE, '-'], input=runner, text=True, encoding='utf-8',
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exact_nine_row_codex_timing_and_legacy_working_event(self):
        self.execute(load_profile(), """
            assert.equal(metadata.states.length,9);
            for(const state of metadata.states){
                assert.equal(hatchPet.selectState(state.id),true);
                for(const [index,frame] of state.frames.entries()){
                    assert.equal(playback().index,index);
                    assert.equal(playback().remainingMs,frame.duration_ms);
                    advance(frame.duration_ms);
                }
                assert.equal(playback().index,0);
                assert.equal(playback().completed,false);
            }
            send('working');assert.equal(playback().state,'running');
            advance(120);assert.equal(playback().index,1);
            send('working');assert.equal(playback().index,0);
            hatchPet.cancel();setReduced(true);
            assert.equal(playback().state,'idle');assert.equal(playback().index,0);
            assert.equal(element('#character').src,'static/idle.png');
            assert.equal(timers.size,0);
        """)

    def test_loop_and_hold_queues_have_finite_dispatch_boundaries(self):
        p = small_profile()
        p['playback'] = {'events': {'success': {'target': 'jump', 'interrupt': 'never'}}}
        self.execute(p, """
            assert.equal(send('success'),true);
            advance(199);assert.equal(playback().state,'rest');
            advance(1);assert.equal(playback().state,'jump');
            assert.deepEqual(playback().queued,[]);
        """)
        p['states'][0]['playback'] = {'mode': 'hold', 'hold_frame': 2, 'interruptible': False}
        self.execute(p, """
            assert.equal(timers.size,0);
            assert.equal(send('success'),true);
            assert.equal(timers.size,1);
            advance(89);assert.equal(playback().state,'rest');
            advance(1);assert.equal(playback().state,'jump');
        """)

    def test_queued_from_finishing_state_precedes_default_completion(self):
        p = small_profile()
        p['states'][0]['playback'] = {'mode': 'once', 'completion': 'jump', 'interruptible': False}
        p['states'][1]['playback'] = {'mode': 'hold'}
        other = copy.deepcopy(p['states'][1])
        other['id'] = 'attention'
        p['states'].append(other)
        for key in ('rows', 'width', 'height'):
            p['layout'].pop(key, None)
        p['events']['notice'] = 'attention'
        p['playback'] = {'events': {'notice': {'target': 'attention', 'from': ['rest'], 'interrupt': 'never'}}}
        self.execute(p, """
            assert.equal(send('notice'),true);
            advance(200);
            assert.equal(playback().state,'attention');
            assert.equal(timers.size,0);
        """)

    def test_once_holds_last_frame_and_completion_preserves_late_deadlines(self):
        p = small_profile()
        p['states'][0]['playback'] = {'mode': 'once', 'completion': 'jump'}
        p['states'][1]['playback'] = {'mode': 'once'}
        self.execute(p, """
            late(250);assert.equal(playback().state,'jump');
            assert.equal(playback().index,1);assert.equal(playback().deadline,310);
            advance(150);assert.equal(playback().index,2);
            assert.equal(playback().completed,true);assert.equal(timers.size,0);
            assert.equal(playback().remainingMs,0);
            assert.equal(send('ready'),true);assert.equal(playback().state,'rest');
        """)

    def test_priority_fifo_and_coalescing_keep_original_arrival(self):
        p = small_profile()
        p['states'][0]['playback'] = {'mode': 'once', 'interruptible': False}
        p['events'] = {'first': 'jump', 'second': 'jump', 'urgent': 'jump'}
        p['playback'] = {'events': {
            name: {'target': 'jump', 'priority': rank, 'interrupt': 'never', 'restart': True}
            for name, rank in [('first', 1), ('second', 1), ('urgent', 2)]}}
        self.execute(p, """
            send('first');send('second');send('first');send('urgent');
            assert.deepEqual(playback().queued,['first','second','urgent']);
            advance(200);assert.equal(playback().priority,2);
            assert.deepEqual(playback().queued,['first','second']);
            advance(200);assert.equal(playback().priority,1);
            assert.deepEqual(playback().queued,['second']);
        """)

    def test_repeated_interruptions_and_priority_flood_cannot_starve_queue(self):
        p = small_profile()
        p['states'][1]['playback'] = {'mode': 'once', 'completion': 'rest'}
        p['events'] = {'low': 'jump', 'flood': 'rest'}
        p['playback'] = {'queue_limit': 2, 'max_consecutive_interruptions': 2, 'events': {
            'low': {'target': 'jump', 'priority': 0, 'interrupt': 'never'},
            'flood': {'target': 'rest', 'priority': 100, 'restart': True}}}
        self.execute(p, """
            send('low');let serviced=false;
            for(let round=0;round<6&&!serviced;round++){
                for(let burst=0;burst<100;burst++)send('flood');
                assert.ok(playback().queued.length<=2);
                advance(200);serviced=playback().state==='jump';
            }
            assert.equal(serviced,true);
            assert.equal(playback().protectedTurn,true);
            for(let burst=0;burst<100;burst++)send('flood');
            advance(199);assert.equal(playback().state,'jump');
            advance(1);assert.equal(playback().state,'rest');
        """)

    def test_zero_interruption_allowance_and_zero_queue_limit(self):
        p = small_profile()
        p['events'] = {'low': 'jump', 'flood': 'rest'}
        p['playback'] = {'max_consecutive_interruptions': 0, 'events': {
            'low': {'target': 'jump', 'interrupt': 'never'},
            'flood': {'target': 'rest', 'restart': True}}}
        self.execute(p, """
            advance(20);send('low');send('flood');
            assert.equal(playback().remainingMs,20);
            advance(180);assert.equal(playback().state,'jump');
        """)
        p['playback']['queue_limit'] = 0
        self.execute(p, "assert.equal(send('low'),false);assert.deepEqual(playback().queued,[]);")

    def test_resume_restores_interrupted_frame_duration_and_priority(self):
        p = small_profile()
        p['states'][1]['playback'] = {'mode': 'once', 'completion': 'rest'}
        p['playback'] = {'events': {
            'ready': {'target': 'rest', 'priority': 7, 'restart': True},
            'success': {'target': 'jump', 'priority': 8, 'resume': True}}}
        self.execute(p, """
            send('ready');advance(60);send('success');
            assert.deepEqual(playback().suspended,['rest']);
            advance(200);assert.equal(playback().state,'rest');
            assert.equal(playback().index,1);assert.equal(playback().priority,7);
            assert.equal(playback().remainingMs,50);
            advance(49);assert.equal(playback().index,1);
            advance(1);assert.equal(playback().index,2);
        """)

    def test_resume_stack_is_bounded_and_cancel_is_final(self):
        p = small_profile()
        p['states'][1]['playback'] = {'mode': 'once'}
        p['playback'] = {'events': {'success': {'target': 'jump', 'resume': True, 'restart': True}}}
        self.execute(p, """
            for(let i=0;i<32;i++)assert.equal(send('success'),true);
            assert.equal(send('success'),false);assert.equal(playback().suspended.length,32);
            assert.equal(hatchPet.cancel(),true);assert.deepEqual(playback().suspended,[]);
            assert.equal(playback().state,'rest');advance(600);assert.equal(playback().state,'rest');
        """)

    def test_pause_visibility_resume_and_paused_event_preserve_time(self):
        p = small_profile()
        p['playback'] = {'events': {'success': {'target': 'jump'}}}
        self.execute(p, """
            advance(20);hatchPet.pause();hidden(true);advance(1000);
            hidden(false);advance(1000);
            assert.equal(playback().paused,true);assert.equal(playback().remainingMs,20);
            hatchPet.resume();advance(19);assert.equal(playback().index,0);
            advance(1);assert.equal(playback().index,1);
            hidden(true);hatchPet.pause();advance(1000);hidden(false);
            hatchPet.resume();advance(69);assert.equal(playback().index,1);
            advance(1);assert.equal(playback().index,2);
            hatchPet.pause();send('success');
            assert.equal(playback().paused,true);assert.equal(timers.size,0);
            hatchPet.resume();advance(40);assert.equal(playback().index,1);
        """)

    def test_reduced_motion_uses_each_state_static_frame_with_no_timers(self):
        p = small_profile()
        p['states'][0]['playback'] = {'interruptible': False, 'reduced_motion_frame': 2}
        p['states'][1]['playback'] = {'mode': 'once', 'reduced_motion_frame': 1}
        p['playback'] = {'events': {'success': {'target': 'jump', 'interrupt': 'never',
                                              'resume': True, 'restart': True}}}
        self.execute(p, """
            advance(50);send('success');setReduced(true);
            assert.equal(playback().index,2);assert.deepEqual(playback().queued,[]);
            assert.equal(timers.size,0);assert.equal(element('#character').src,'static/rest.png');
            assert.equal(send('success'),true);assert.equal(playback().state,'jump');
            assert.equal(playback().index,1);assert.equal(element('#character').src,'static/jump.png');
            for(let i=0;i<40;i++)assert.equal(send('success'),true);
            assert.deepEqual(playback().suspended,[]);
            assert.equal(timers.size,0);advance(10000);assert.equal(playback().state,'jump');
            setReduced(false);assert.equal(playback().index,0);
        """)

    def test_repeat_default_and_invalid_event_and_selection_do_not_restart(self):
        p = small_profile()
        p['playback'] = {'events': {'success': {'target': 'jump'}}}
        self.execute(p, """
            send('success');advance(60);send('success');
            assert.equal(playback().index,1);assert.equal(playback().remainingMs,50);
            for(const value of ['toString','constructor','__proto__','unknown',{},null]){
                assert.equal(send(value),false);
                assert.equal(hatchPet.selectState(value),false);
            }
            assert.equal(playback().index,1);assert.equal(playback().remainingMs,50);
        """)
        self.execute(small_profile(), """
            send('success');advance(60);send('success');
            assert.equal(playback().index,0);
        """)

    def test_stale_illegal_events_are_discarded_and_unknown_url_is_safe(self):
        p = small_profile()
        p['events']['interrupt'] = 'jump'
        p['playback'] = {'events': {
            'success': {'target': 'jump', 'from': ['rest'], 'interrupt': 'never'},
            'interrupt': {'target': 'jump', 'priority': 5},
            'ready': {'target': 'rest'}}}
        self.execute(p, """
            send('success');send('interrupt');assert.equal(send('success'),false);
            assert.deepEqual(playback().queued,['success']);advance(200);
            assert.deepEqual(playback().queued,[]);
        """, '?state=not-in-profile')
        self.execute(p, "assert.equal(playback().state,'rest');", '?state=not-in-profile')

    def test_catch_up_has_a_finite_resynchronization_budget(self):
        self.execute(small_profile(), """
            late(100000000);
            assert.equal(timers.size,1);
            assert.ok(playback().deadline>testTime);
            assert.ok(playback().remainingMs<=90);
        """)

    def test_every_compiled_recipe_runs_its_animated_and_static_step_graph(self):
        from state_catalog import compile_profile, load_library
        library = load_library()
        for name, recipe in library.recipes.items():
            for static in (False, True):
                with self.subTest(recipe=name, static=static):
                    result = compile_profile(recipe=name, archetype='humanoid',
                                             reduced_motion=static, library=library)
                    script = 'const recipeSteps=' + json.dumps(recipe['steps']) + ';\n' + """
                        function remainingCycle(){
                            const current=playback(),state=metadata.states.find(s=>s.id===current.state);
                            return current.remainingMs+state.frames.slice(current.animationIndex+1)
                                .reduce((total,frame)=>total+frame.duration_ms,0);
                        }
                        assert.equal(playback().state,recipeSteps[0]);
                        for(let index=0;index+1<recipeSteps.length;index++){
                            const from=recipeSteps[index],target=recipeSteps[index+1];
                            assert.equal(playback().state,from);
                            const state=metadata.states.find(s=>s.id===from);
                            if(state.playback.completion===target||playback().suspended.at(-1)===target){
                                advance(remainingCycle());
                            }else{
                                const event=Object.entries(metadata.playback.events).find(([name,rule])=>
                                    rule.target===target&&(!rule.from||rule.from.includes(from)));
                                assert.ok(event,'No event for '+from+' -> '+target);
                                assert.equal(send(event[0]),true);
                                if(playback().state!==target)advance(remainingCycle());
                            }
                            assert.equal(playback().state,target,'Recipe step '+from+' -> '+target);
                        }
                        hatchPet.cancel();assert.equal(playback().state,metadata.playback.cancel_state);
                        assert.deepEqual(playback().queued,[]);assert.deepEqual(playback().suspended,[]);
                    """
                    self.execute(result['profile'], script)


if __name__ == '__main__':
    unittest.main()
