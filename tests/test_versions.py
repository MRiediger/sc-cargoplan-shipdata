"""builtFrom.tools in the manifest names the versions that ran, comparable with the pins (TOOLS.md: a version that differs
from its pin is a finding). Package versions, not module versions: cv2 says 5.0.0, the pinned package is 5.0.0.93."""
import json
import re

from conftest import TOOLS, needs_pwsh
from shipdata import stages


@needs_pwsh
def test_tool_versions_match_the_pins() -> None:
    pins = dict(re.findall(r'^([\w-]+)==([\w.]+)$', (TOOLS / 'requirements.txt').read_text(encoding='utf-8'), re.M))
    v = stages.tool_versions()
    assert (v['numpy'], v['opencv']) == (pins['numpy'], pins['opencv-python-headless'])
    assert v['meshoptimizer'] == json.loads((TOOLS / 'package.json').read_text(encoding='utf-8'))['dependencies']['meshoptimizer']
    assert (v['python'], v['node'], v['pwsh']) == ('3.14.5', '24.16.0', '7.6.10')
