"""Use a configured or installed real Chromium; do not hide launch failures."""
import os
from pathlib import Path
import unittest


def launch_chromium(runtime):
    executable = os.environ.get('HATCH_BROWSER_EXECUTABLE')
    if executable:
        if not Path(executable).is_file():
            raise ValueError('configured HATCH_BROWSER_EXECUTABLE is missing')
    elif not Path(runtime.chromium.executable_path).is_file():
        raise unittest.SkipTest('Chromium is not installed; run python -m playwright install chromium')
    return runtime.chromium.launch(headless=True, executable_path=executable,
                                   args=['--no-sandbox', '--disable-dev-shm-usage'])
