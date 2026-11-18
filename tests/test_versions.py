"""Pins: one machine-readable source per pin, TOOLS.md is the human copy with a test (SD8, T12.0 K1).

  .python-version, .nvmrc       read by actions/setup-python (python-version-file) and actions/setup-node (node-version-file)
  tools/pins.json               appTag (gate checkout, run.py), runner (the chain's runs-on), pwsh (image on the runner, WSL)
  tools/requirements*.txt, tools/package-lock.json   the Python and npm packages

builtFrom.tools in the manifest names the versions that ran, comparable with the pins (TOOLS.md: a version that differs
from its pin is a finding). Package versions, not module versions: cv2 says 5.0.0, the pinned package is 5.0.0.93."""
import json
import re

from conftest import ROOT, TOOLS, needs_pwsh
from shipdata import stages


def pins() -> dict[str, str]:
    """Every pin from its machine-readable source."""
    req = dict(re.findall(r'^([\w-]+)==([\w.]+)$', (TOOLS / 'requirements.txt').read_text(encoding='utf-8'), re.M))
    dev = dict(re.findall(r'^([\w-]+)==([\w.]+)$', (TOOLS / 'requirements-dev.txt').read_text(encoding='utf-8'), re.M))
    lock = json.loads((TOOLS / 'package-lock.json').read_text(encoding='utf-8'))
    p = json.loads((TOOLS / 'pins.json').read_text(encoding='utf-8'))
    return {'python': (ROOT / '.python-version').read_text(encoding='utf-8').strip(),
            'node': (ROOT / '.nvmrc').read_text(encoding='utf-8').strip(),
            'numpy': req['numpy'], 'opencv': req['opencv-python-headless'], 'pytest': dev['pytest'],
            'meshoptimizer': lock['packages']['node_modules/meshoptimizer']['version'],
            'pwsh': p['pwsh'], 'appTag': p['appTag'], 'runner': p['runner']}


def tools_md() -> dict[str, str]:
    """First word of the version column of TOOLS.md's table, by tool name."""
    rows = re.findall(r'^\| ([^|]+?) \| ([^|]+?) \|', (ROOT / 'TOOLS.md').read_text(encoding='utf-8'), re.M)
    return {name: version.split()[0].strip('`') for name, version in rows if name not in ('Tool', '---')}


def test_tools_md_copies_the_sources() -> None:
    p, t = pins(), tools_md()
    assert (t['Python'], t['Node.js'], t['PowerShell']) == (p['python'], p['node'], p['pwsh'])
    assert (t['numpy'], t['opencv-python-headless'], t['pytest']) == (p['numpy'], p['opencv'], p['pytest'])
    assert t['meshoptimizer (npm)'] == p['meshoptimizer']
    assert (t['App for the gate'], t['Runner (chain)']) == (p['appTag'], p['runner'])


def test_package_json_names_the_locked_meshoptimizer() -> None:
    pkg = json.loads((TOOLS / 'package.json').read_text(encoding='utf-8'))
    assert pkg['dependencies']['meshoptimizer'] == pins()['meshoptimizer']


def test_run_py_takes_the_app_tag_from_pins_json() -> None:
    import run
    assert run.APP_TAG == pins()['appTag']


def test_local_wsl_reads_the_pins_instead_of_naming_them() -> None:
    script = (TOOLS / 'local-wsl.sh').read_text(encoding='utf-8')
    p = pins()
    assert [v for v in (p['python'], p['node'], p['pwsh']) if v in script] == []
    assert '.python-version' in script and '.nvmrc' in script and 'pins.json' in script


@needs_pwsh
def test_tool_versions_match_the_pins() -> None:
    v, p = stages.tool_versions(), pins()
    assert {k: v[k] for k in ('python', 'node', 'pwsh', 'numpy', 'opencv', 'meshoptimizer')} == \
           {k: p[k] for k in ('python', 'node', 'pwsh', 'numpy', 'opencv', 'meshoptimizer')}
