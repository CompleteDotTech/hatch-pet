"""Exercise the exported HTML in a real local browser with a controlled clock."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from fixture_workflow import build_run, hatch


@unittest.skipUnless(importlib.util.find_spec('playwright'), 'optional local Playwright is not installed')
class BrowserExportTests(unittest.TestCase):
    def test_actual_export_frame_order_timing_events_and_reduced_motion(self):
        from playwright.sync_api import sync_playwright, expect
        with tempfile.TemporaryDirectory(prefix='hatch-browser-fixture-') as td:
            root = Path(td) / 'run'
            data = build_run(root)
            exported = Path(td) / 'export'
            hatch.export(root, data, exported)
            metadata = hatch.read(exported / 'animation.json')
            with sync_playwright() as runtime:
                try:
                    browser = runtime.chromium.launch(headless=True)
                except Exception as exc:
                    self.skipTest('local Chromium is unavailable: ' + str(exc).splitlines()[0])
                try:
                    page = browser.new_page(reduced_motion='no-preference')
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.add_init_script('''
                        window.fixtureTimers = new Map(); let serial = 0, fixtureTime = 0;
                        Object.defineProperty(performance, 'now', {value: () => fixtureTime});
                        window.setTimeout = (callback, delay) => {const id=++serial;fixtureTimers.set(id,{callback,delay});return id};
                        window.clearTimeout = id => fixtureTimers.delete(id);
                        window.fixtureTick = () => {const [id,t]=Array.from(fixtureTimers.entries())[0];fixtureTimers.delete(id);fixtureTime+=t.delay;t.callback();return t.delay};
                    ''')
                    page.goto((exported / 'preview.html').as_uri())
                    rest = metadata['states'][0]
                    for index, frame in enumerate(rest['frames']):
                        self.assertEqual(page.locator('#character').get_attribute('data-frame-index'), str(index))
                        self.assertTrue(page.locator('#character').get_attribute('src').endswith(frame['path']))
                        self.assertEqual(page.evaluate('window.fixtureTick()'), frame['duration_ms'])
                    self.assertEqual(page.locator('#character').get_attribute('data-frame-index'), '0')
                    page.select_option('#state', 'jump')
                    self.assertEqual(page.evaluate('hatchPet.playback.state'), 'jump')
                    self.assertTrue(page.evaluate("hatchPet.dispatchLocalEvent('ready')"))
                    self.assertFalse(page.evaluate("hatchPet.dispatchLocalEvent('undefined-event')"))
                    page.check('#still')
                    self.assertEqual(page.locator('#character').get_attribute('src'), 'static/rest.png')
                    self.assertEqual(page.evaluate('fixtureTimers.size'), 0)
                    self.assertEqual(page.evaluate('hatchPet.playback.index'), 1)
                    page.uncheck('#still')
                    page.emulate_media(reduced_motion='reduce')
                    expect(page.locator('#still')).to_be_checked()
                    page.goto((exported / 'preview.html').as_uri() + '?overlay=1&state=jump')
                    self.assertEqual(page.locator('.controls').evaluate('(el)=>getComputedStyle(el).display'), 'none')
                    self.assertEqual(page.evaluate('hatchPet.playback.state'), 'jump')
                    self.assertEqual(errors, [])
                    self.assertGreater(page.locator('#character').evaluate('(el)=>el.naturalWidth'), 0)
                finally:
                    browser.close()


if __name__ == '__main__':
    unittest.main()
