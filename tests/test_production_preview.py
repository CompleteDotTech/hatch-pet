"""Actual Chromium exercises for local frame, layer, comparison and audio review."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading
import unittest

from test_production_render import fixture_project
from production_render import audio_fixture, render_shot


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


class ProductionPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise unittest.SkipTest("Playwright package unavailable; browser integration not exercised") from exc
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        executable = os.environ.get("HATCH_BROWSER_EXECUTABLE")
        available = Path(executable or cls.playwright.chromium.executable_path)
        if not available.is_file():
            raise unittest.SkipTest("Chromium executable unavailable; install the documented browser test dependency")
        # Once a binary exists, launch errors are failures, never availability skips.
        cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=executable,
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        cls.addClassCleanup(cls.browser.close)
        print("Production preview actual browser:", cls.browser.version)
        cls.temp = tempfile.TemporaryDirectory(prefix="hatch-preview-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.home = Path(cls.temp.name)
        bundle = fixture_project(cls.home/"project")
        shot = bundle["shots"]["first"]
        shot["duration_frames"] = 24
        shot["instances"][0]["clips"][0]["end_frame"] = 24
        cue = audio_fixture(bundle["root"]/"dialogue.wav", duration_frames=24)
        shot["audio"] = [{"id": "test-line", "file": {"path": "dialogue.wav", "sha256": cue["sha256"]},
            "start_frame": 0, "duration_frames": 24, "speaker": "alice", "text": "Synthetic timing cue",
            "provenance": cue["provenance"], "gain": .2, "mouth_cues": []}]
        cls.manifest = render_shot(bundle, "first", cls.home/"render")
        handler = partial(QuietHandler, directory=str(cls.home))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/render/preview.html"

    def setUp(self):
        self.context = self.browser.new_context(reduced_motion="reduce" if "reduced_motion" in self.id() else "no-preference")
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.url)
        self.page.wait_for_function("window.hatchPreview && hatchPreview.renderedFrame === 0")

    def tearDown(self):
        self.assertFalse(self.errors)
        self.assertEqual(self.page.locator("#error").inner_text(), "")

    def seek_number(self, frame):
        field = self.page.locator("#frame-number")
        field.fill(str(frame))
        field.press("Tab")
        expected = max(0, min(23, frame))
        self.page.wait_for_function("value => hatchPreview.renderedFrame === value", arg=expected)

    def pixel(self, canvas, x, y):
        return self.page.locator(canvas).evaluate("(node, p) => Array.from(node.getContext('2d').getImageData(p[0], p[1], 1, 1).data)", [x, y])

    def test_scrub_step_clamps_timing_and_actual_source_inspection(self):
        self.assertEqual(self.pixel("#canvas", 6, 15), [220, 40, 30, 255])
        self.assertIn("Synthetic regression fixture", self.page.locator("#origin").inner_text())
        self.page.locator("#next").click()
        self.page.wait_for_function("hatchPreview.renderedFrame === 1")
        self.page.locator("#previous").click()
        self.page.wait_for_function("hatchPreview.renderedFrame === 0")
        self.page.locator("#previous").click()
        self.assertEqual(self.page.evaluate("hatchPreview.frame"), 0)
        self.seek_number(999)
        self.assertEqual(self.page.locator("#frame-number").input_value(), "23")
        self.seek_number(-3)
        self.page.locator("#scrubber").evaluate("node => {node.value='7';node.dispatchEvent(new Event('input',{bubbles:true}));}")
        self.page.wait_for_function("hatchPreview.renderedFrame === 7")
        self.assertIn("[7/12, 8/12)", self.page.locator("#interval").inner_text())
        self.assertIn(self.manifest["frames"][7]["sha256"], self.page.locator("#evidence").inner_text())
        self.page.locator("#title").click()
        self.page.keyboard.press("ArrowRight")
        self.page.wait_for_function("hatchPreview.renderedFrame === 8")
        self.assertIn("alice: Synthetic timing cue", self.page.locator("#dialogue").inner_text())

    def test_track_visibility_and_pinned_comparison_change_real_pixels(self):
        self.page.locator('input[data-track="alice"]').uncheck()
        self.page.wait_for_function("document.querySelector('#canvas').getContext('2d').getImageData(6,15,1,1).data[3] === 0")
        self.assertEqual(self.pixel("#canvas", 22, 15), [30, 80, 220, 255])
        self.page.locator('input[data-track="alice"]').check()
        self.page.wait_for_function("document.querySelector('#canvas').getContext('2d').getImageData(6,15,1,1).data[3] === 255")
        self.page.locator("#pin").click()
        self.seek_number(3)
        self.page.locator("#comparison-panel").wait_for(state="visible")
        self.assertEqual(self.pixel("#canvas", 6, 15)[3], 0)
        self.assertEqual(self.pixel("#comparison", 6, 15), [220, 40, 30, 255])
        self.page.locator("#comparison-mode").select_option("onion")
        self.page.wait_for_function("document.querySelector('#canvas').getContext('2d').getImageData(6,15,1,1).data[3] > 0")
        self.assertAlmostEqual(self.pixel("#canvas", 6, 15)[3], 115, delta=1)
        self.assertTrue(self.page.locator("#comparison-panel").is_hidden())
        self.assertLessEqual(self.page.evaluate("hatchPreview.cachedImages"), 64)

    def test_playback_catches_up_after_main_thread_stall_and_stops_at_boundary(self):
        self.page.locator("#play").click()
        self.page.wait_for_function("hatchPreview.playing")
        self.page.evaluate("() => {const start=performance.now();while(performance.now()-start<450){}}")
        self.page.wait_for_function("hatchPreview.frame >= 4")
        self.page.locator("#play").click()
        self.assertFalse(self.page.evaluate("hatchPreview.playing"))
        self.seek_number(22)
        self.page.locator("#play").click()
        self.page.wait_for_function("!hatchPreview.playing && hatchPreview.renderedFrame === 23")
        self.assertEqual(self.page.locator("#play").inner_text(), "Play")

    def test_audio_seek_is_stable_and_reduced_motion_does_not_autoplay(self):
        self.assertIn("Reduced motion", self.page.locator("#status").inner_text())
        self.assertFalse(self.page.evaluate("hatchPreview.playing"))
        self.assertTrue(self.page.locator("#audio").evaluate("node => node.paused"))
        self.page.locator("#audio-enabled").check()
        self.seek_number(12)
        self.page.wait_for_function("Math.abs(document.querySelector('#audio').currentTime-1)<.02 && !document.querySelector('#audio').seeking")
        self.page.wait_for_timeout(120)
        self.assertEqual(self.page.evaluate("hatchPreview.frame"), 12)
        self.seek_number(6)
        self.seek_number(15)
        self.page.wait_for_function("Math.abs(document.querySelector('#audio').currentTime-1.25)<.02 && !document.querySelector('#audio').seeking")
        self.assertEqual(self.page.evaluate("hatchPreview.frame"), 15)
        self.page.locator("#play").click()
        self.page.wait_for_function("hatchPreview.playing && hatchPreview.frame >= 16")
        self.page.locator("#play").click()
        paused = self.page.evaluate("hatchPreview.frame")
        self.page.wait_for_timeout(120)
        self.assertEqual(self.page.evaluate("hatchPreview.frame"), paused)
        self.assertTrue(self.page.locator("#audio").evaluate("node => node.paused"))


if __name__ == "__main__":
    unittest.main()
