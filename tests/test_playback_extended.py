"""Real Chromium tests exercise exported HTML, not a duplicate Python state machine."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from fixture_workflow import hatch, build_run, small_profile
from demonstrate import ROOT, demonstrate

FAKE_CLOCK = '''
window.testTime=0;window.timers=new Map();let serial=0;
Object.defineProperty(performance,'now',{value:()=>testTime});
window.setTimeout=(callback,delay)=>{let id=++serial;timers.set(id,{callback,delay,due:testTime+delay});return id};
window.clearTimeout=id=>timers.delete(id);
window.testAdvance=ms=>{const end=testTime+ms;let steps=0;while(timers.size){const [id,t]=Array.from(timers.entries()).sort((a,b)=>a[1].due-b[1].due)[0];if(t.due>end)break;if(++steps>500)throw Error('runaway');testTime=t.due;timers.delete(id);t.callback()}testTime=end};
window.late=ms=>{testTime+=ms;const [id,t]=Array.from(timers.entries()).sort((a,b)=>a[1].due-b[1].due)[0];timers.delete(id);t.callback()};
window.testHidden=false;Object.defineProperty(document,'hidden',{get:()=>testHidden});
window.hide=flag=>{testHidden=flag;document.dispatchEvent(new Event('visibilitychange'))};
'''


@unittest.skipUnless(importlib.util.find_spec('playwright'),'Playwright is optional')
class ExtendedBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.runtime=sync_playwright().start()
        try:cls.browser=cls.runtime.chromium.launch(headless=True)
        except Exception as exc:
            cls.runtime.stop();raise unittest.SkipTest(str(exc))

    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.runtime.stop()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hatch-extended-browser-');self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.page=self.browser.new_page(reduced_motion='no-preference');self.addCleanup(self.page.close)
        self.errors=[];self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.page.add_init_script(FAKE_CLOCK)

    def export(self,profile=None):
        data=build_run(self.home/'run',profile);hatch.export(self.home/'run',data,self.home/'export')
        self.page.goto((self.home/'export/preview.html').as_uri())

    def state(self):return self.page.evaluate('hatchPet.playback')

    def test_once_queue_legal_transitions_priority_and_completion(self):
        self.export(ROOT/'presets/protocol.json')
        self.assertEqual(self.state()['state'],'idle')
        self.assertFalse(self.page.evaluate("hatchPet.dispatchLocalEvent('receive-ack')"))
        self.assertTrue(self.page.evaluate("hatchPet.dispatchLocalEvent('send')"))
        self.page.evaluate("hatchPet.dispatchLocalEvent('receive-ack');hatchPet.dispatchLocalEvent('receive-ack')")
        self.assertEqual(self.state()['queued'],['receive-ack'])
        self.page.evaluate('testAdvance(360)');self.assertEqual(self.state()['state'],'ack')
        self.page.evaluate('testAdvance(240)');self.assertEqual(self.state()['state'],'done')
        self.assertEqual(self.page.evaluate('timers.size'),0)
        self.page.evaluate("hatchPet.cancel();hatchPet.dispatchLocalEvent('send');hatchPet.dispatchLocalEvent('receive-ack');hatchPet.dispatchLocalEvent('timeout');testAdvance(360)")
        self.assertEqual(self.state()['state'],'fault')
        self.assertEqual(self.errors,[])

    def test_deadlines_visibility_cancel_and_reduced_motion(self):
        self.export()
        self.page.evaluate('late(115)')
        self.assertEqual(self.state()['index'],2)
        self.assertEqual(self.page.evaluate('Array.from(timers.values())[0].delay'),85)
        self.page.evaluate('testAdvance(10);hide(true)');index=self.state()['index']
        self.page.evaluate('testAdvance(10000)');self.assertEqual(self.state()['index'],index)
        self.page.evaluate('hide(false);testAdvance(74)');self.assertEqual(self.state()['index'],index)
        self.page.evaluate('testAdvance(1)');self.assertEqual(self.state()['index'],0)
        self.page.evaluate("hatchPet.selectState('jump');hatchPet.cancel()")
        self.assertEqual(self.state()['state'],'rest')
        self.page.emulate_media(reduced_motion='reduce')
        self.page.wait_for_function('hatchPet.playback.reducedMotion')
        self.assertEqual(self.page.evaluate('timers.size'),0)
        self.assertEqual(self.page.locator('#character').get_attribute('src'),'static/rest.png')
        self.assertEqual(self.errors,[])

    def test_bounded_queue_hold_frame_and_higher_priority_interruption(self):
        p=small_profile();p['states'][0]['playback']={'mode':'once','interruptible':False}
        p['states'][1]['playback']={'mode':'hold','hold_frame':2}
        p['events']={'first':'jump','second':'jump'}
        p['playback']={'queue_limit':1,'events':{'first':{'target':'jump','priority':1,'interrupt':'higher','restart':True},'second':{'target':'jump','priority':2,'interrupt':'higher','restart':True}}}
        self.export(p)
        self.assertTrue(self.page.evaluate("hatchPet.dispatchLocalEvent('first')"))
        self.assertFalse(self.page.evaluate("hatchPet.dispatchLocalEvent('second')"))
        self.assertTrue(self.page.evaluate("hatchPet.dispatchLocalEvent('first')"))
        self.assertEqual(self.state()['queued'],['first'])
        self.page.evaluate('testAdvance(200)')
        self.assertEqual((self.state()['state'],self.state()['index']),('jump',2))
        self.assertEqual(self.page.evaluate('timers.size'),0)
        # A lower-priority event queues; a higher-priority event interrupts a hold.
        self.assertTrue(self.page.evaluate("hatchPet.dispatchLocalEvent('first')"))
        self.assertEqual(self.state()['queued'],['first'])
        self.assertTrue(self.page.evaluate("hatchPet.dispatchLocalEvent('second')"))
        self.assertEqual(self.state()['priority'],2)
        self.assertEqual(self.errors,[])

    def test_declared_event_default_does_not_restart_active_animation(self):
        p=small_profile();p['playback']={'events':{'success':{'target':'jump'}}}
        self.export(p);self.page.evaluate("hatchPet.dispatchLocalEvent('success');testAdvance(40)")
        self.assertEqual(self.state()['index'],1)
        self.page.evaluate("hatchPet.dispatchLocalEvent('success')")
        self.assertEqual(self.state()['index'],1)

    def test_reduced_motion_static_export_matches_each_selected_frame(self):
        from PIL import Image
        p=small_profile()
        p['states'][0]['playback']={'reduced_motion_frame':2,'interruptible':False}
        p['states'][1]['playback']={'mode':'once','reduced_motion_frame':1}
        p['playback']={'events':{'success':{'target':'jump','interrupt':'never'}}}
        self.export(p)
        metadata=hatch.read(self.home/'export/animation.json')
        for state in metadata['states']:
            expected=2 if state['id']=='rest' else 1
            self.assertEqual(state['static_frame'],expected)
            with Image.open(self.home/'export'/state['static']) as static, Image.open(self.home/'export'/state['frames'][expected]['path']) as frame:
                self.assertEqual(static.convert('RGBA').tobytes(),frame.convert('RGBA').tobytes())
        self.page.emulate_media(reduced_motion='reduce')
        self.page.wait_for_function('hatchPet.playback.reducedMotion')
        self.assertEqual(self.state()['index'],2)
        self.assertEqual(self.page.locator('#character').get_attribute('src'),'static/rest.png')
        self.assertTrue(self.page.evaluate("hatchPet.dispatchLocalEvent('success')"))
        self.assertEqual((self.state()['state'],self.state()['index']),('jump',1))
        self.assertEqual(self.page.locator('#character').get_attribute('src'),'static/jump.png')
        self.assertEqual(self.page.evaluate('timers.size'),0)
        self.assertEqual(self.errors,[])

    def test_resumable_notification_restores_frame_and_pause_timing(self):
        p=small_profile();p['states'][1]['playback']={'mode':'once','completion':'rest'}
        p['playback']={'events':{'success':{'target':'jump','priority':8,'resume':True}}}
        self.export(p)
        self.page.evaluate("testAdvance(60);hatchPet.dispatchLocalEvent('success');testAdvance(200)")
        self.assertEqual((self.state()['state'],self.state()['index']),('rest',1))
        self.assertEqual(self.state()['remainingMs'],50)
        self.page.evaluate('hatchPet.pause();hide(true);testAdvance(1000);hide(false);testAdvance(1000)')
        self.assertTrue(self.state()['paused']);self.assertEqual(self.state()['remainingMs'],50)
        self.page.evaluate('hatchPet.resume();testAdvance(49)');self.assertEqual(self.state()['index'],1)
        self.page.evaluate('testAdvance(1)');self.assertEqual(self.state()['index'],2)
        self.assertEqual(self.errors,[])

    def test_repeated_high_priority_events_have_bounded_queue_fairness(self):
        p=small_profile();p['events']={'low':'jump','flood':'rest'}
        p['states'][1]['playback']={'mode':'once','completion':'rest'}
        p['playback']={'queue_limit':2,'max_consecutive_interruptions':2,'events':{
            'low':{'target':'jump','priority':0,'interrupt':'never'},
            'flood':{'target':'rest','priority':100,'restart':True}}}
        self.export(p)
        serviced=self.page.evaluate("""() => {
            hatchPet.dispatchLocalEvent('low');
            for(let round=0;round<6;round++){
                for(let burst=0;burst<100;burst++)hatchPet.dispatchLocalEvent('flood');
                testAdvance(200);
                if(hatchPet.playback.state==='jump'){
                    for(let burst=0;burst<100;burst++)hatchPet.dispatchLocalEvent('flood');
                    testAdvance(199);
                    return hatchPet.playback.state==='jump';
                }
            }
            return false;
        }""")
        self.assertTrue(serviced);self.assertLessEqual(len(self.state()['queued']),2)
        self.assertEqual(self.errors,[])

    def test_queued_event_source_is_checked_before_default_completion(self):
        p=small_profile();p['states'][0]['playback']={'mode':'once','completion':'jump','interruptible':False}
        p['playback']={'events':{'success':{'target':'jump','from':['rest'],'priority':7,'interrupt':'never'}}}
        self.export(p)
        self.page.evaluate("hatchPet.dispatchLocalEvent('success');testAdvance(200)")
        self.assertEqual((self.state()['state'],self.state()['priority']),('jump',7))
        self.assertEqual(self.errors,[])

    def test_review_ui_steps_frames_and_binds_downloaded_evidence(self):
        demonstrate('assembly',self.home)
        self.page.goto((self.home/'assembly/review/review.html').as_uri())
        self.assertEqual(self.page.locator('figure img').count(),6)
        frame=self.page.frame_locator('iframe')
        frame.locator('#state').select_option('insert');frame.locator('#next').click()
        self.assertEqual(frame.locator('#character').get_attribute('data-state'),'insert')
        frame.locator('#background').select_option('dark')
        self.assertEqual(frame.locator('#viewport').get_attribute('data-background'),'dark')
        self.page.locator('#reviewer').fill('browser fixture review exercise')
        self.page.locator('#canonical').check();self.page.locator('#contact').check()
        for state in ('exploded','insert','tighten','test'):
            self.page.locator('#review-state').select_option(state)
            visible=self.page.locator('fieldset:not([hidden])')
            visible.locator('input[type=checkbox]').check()
            for locator in visible.locator('select').all():locator.select_option('pass')
            for locator in visible.locator('textarea').all():locator.fill('Synthetic browser test; no production judgment.')
        with self.page.expect_download() as download:
            self.page.get_by_role('button',name='Download bound review JSON').click()
        path=self.home/'download.json';download.value.save_as(path)
        result=hatch.read(path)
        expected=hatch.read(self.home/'assembly/review/review-template.json')
        self.assertEqual(result['artifact_hashes'],expected['artifact_hashes'])
        self.assertEqual(set(result['evidence']['playback_states']),set(expected['rows']))
        self.assertEqual(self.errors,[])

    def test_board_configurator_and_cursor_adapters_locally(self):
        for name in ('communication','configurator','cursor'):demonstrate(name,self.home)
        self.page.goto((self.home/'communication/export/board.html').as_uri())
        self.page.locator('button[data-state=help]').click()
        self.assertEqual(self.page.locator('#static').get_attribute('src'),'static/help.png')
        self.page.goto((self.home/'configurator/export/preview.html').as_uri())
        self.page.locator('#state').select_option('blue-glaze')
        self.assertEqual(self.page.locator('#character').get_attribute('data-state'),'blue-glaze')
        self.page.goto((self.home/'cursor/export/cursor-demo.html').as_uri())
        self.page.evaluate("document.querySelector('#area').addEventListener('pointermove',e=>window.lastPointer=[e.clientX,e.clientY])")
        self.page.locator('#area').hover(position={'x':80,'y':80})
        self.assertEqual(self.page.locator('#cursor').evaluate('(e)=>getComputedStyle(e).display'),'block')
        self.assertEqual(self.page.evaluate('cursorDemo.hotspot'),[4,4])
        self.assertTrue(self.page.evaluate("(()=>{const r=document.querySelector('#cursor').getBoundingClientRect();return Math.abs(r.left+4-lastPointer[0])<1&&Math.abs(r.top+4-lastPointer[1])<1})()"))
        before=self.page.locator('#cursor').get_attribute('src');self.page.evaluate('testAdvance(80)')
        self.assertNotEqual(self.page.locator('#cursor').get_attribute('src'),before)
        self.assertEqual(self.errors,[])


if __name__=='__main__':unittest.main()
