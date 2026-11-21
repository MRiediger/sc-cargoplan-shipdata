"""ship-data.yml against the rules it has to keep (T12.2 plan, block 8): read line by line, no YAML package (the file is
plain block YAML written by hand; a test that needs a parser would be a new dependency).

  runs-on of the Ubuntu jobs = tools/pins.json runner (SD8); the gate on windows-latest (SD3: no pin needed)
  the Motherlode secret exactly once, as env of the fetch step (CLAUDE.md: secrets only where needed)
  every run: line calls run.py, pytest, pip or npm ci - no logic in YAML (lesson of S12.0)
  artifacts carry reports only: no catalog, ship files, holograms, pictures (A17, SD7, SD10)
  every report artifact carries tools/pins.json, so it keeps the out/ and work/ layout
  every action is pinned in TOOLS.md with the same version (no new dependency without a pin)
  cron 23 4 1 * * (D3), permissions {} at the top, chain timeout >= 90 min (T12.1: full run ~61 min locally)"""
import json
import re

from conftest import ROOT, TOOLS

YML = ROOT / '.github' / 'workflows' / 'ship-data.yml'
ALLOWED_RUN = ('python -I tools/run.py ', 'python -I -m pytest ', 'python -m pip install ', 'npm ci ')
FORBIDDEN_IN_ARTIFACTS = ('catalog', 'stage', 'ships', '.holo', '.png', 'cache', 'previous-release', 'raw')


def lines() -> list[str]:
    return YML.read_text(encoding='utf-8').splitlines()


def jobs() -> dict[str, list[str]]:
    """Job name -> its lines (jobs are the keys indented by two spaces under `jobs:`)."""
    out: dict[str, list[str]] = {}
    current = None
    inside = False
    for line in lines():
        if line == 'jobs:':
            inside = True
            continue
        m = re.match(r'^  ([a-z-]+):$', line)
        if inside and m:
            current = m[1]
            out[current] = []
        elif inside and current:
            out[current].append(line)
    return out


def steps(job_lines: list[str]) -> list[list[str]]:
    """A job's steps: each starts with '      - '."""
    out: list[list[str]] = []
    for line in job_lines:
        if line.startswith('      - '):
            out.append([line])
        elif out and line.startswith('        '):
            out[-1].append(line)
    return out


def test_ubuntu_jobs_run_on_the_pinned_runner() -> None:
    runner = json.loads((TOOLS / 'pins.json').read_text(encoding='utf-8'))['runner']
    found = {j: next(l.split(':', 1)[1].strip() for l in body if l.strip().startswith('runs-on:')) for j, body in jobs().items()}
    assert found.pop('gate') == 'windows-latest'
    assert set(found.values()) == {runner}, found


def test_the_secret_is_used_once_in_the_fetch_step() -> None:
    text = YML.read_text(encoding='utf-8')
    assert text.count('secrets.') == 1
    holder = [s for s in steps(jobs()['chain']) if any('secrets.MOTHERLODE_API_KEY' in l for l in s)]
    assert len(holder) == 1 and any(l.strip() == 'run: python -I tools/run.py fetch' for l in holder[0])


SHELL_LOGIC = ('&&', '||', ';', '|', '$(', '`', '>', '<', '$?')


def test_every_run_line_calls_a_script() -> None:
    """One command per step, no shell logic around it (an exit code mapped in YAML is logic: verify --ci does it)."""
    # `run:` alone is the key of `defaults: run: shell: bash`, not a command; `- run:` starts a step
    stripped = [l.strip().removeprefix('- ') for l in lines()]
    runs = [l[len('run: '):] for l in stripped if l.startswith('run:') and l != 'run:']
    assert runs and [r for r in runs if not r.startswith(ALLOWED_RUN)] == []
    assert [r for r in runs if any(op in r for op in SHELL_LOGIC)] == []
    assert not any(l in ('run: |', 'run: >') for l in stripped)                # no multi-line scripts


def artifact_paths() -> dict[str, list[str]]:
    """Artifact name -> the paths of its upload step."""
    out: dict[str, list[str]] = {}
    for body in jobs().values():
        for s in steps(body):
            if any('actions/upload-artifact@' in l for l in s):
                name = next(l.split(':', 1)[1].strip() for l in s if l.strip().startswith('name:'))
                paths = out.setdefault(name, [])
                block = False
                for l in s:
                    if l.strip() == 'path: |':
                        block = True
                    elif block and l.startswith('            '):
                        paths.append(l.strip())
                    else:
                        block = False
    return out


def test_artifacts_carry_reports_only() -> None:
    paths = [p for ps in artifact_paths().values() for p in ps]
    assert paths
    bad = [p for p in paths if any(f in p for f in FORBIDDEN_IN_ARTIFACTS)]
    assert bad == [], bad


ANCHOR = 'tools/pins.json'


def test_every_report_artifact_keeps_the_repository_layout() -> None:
    """upload-artifact (README, v7 has no root input): "the least common ancestor of all the search paths will be used
    as the root directory". reports-pr and reports-publish* had search paths under out/ only, so 'out/' was cut off and
    after the merged download the heartbeat missed that job's lines (run 44296781671: 'error in job pr: see the log').
    tools/pins.json is a search path in every report artifact and exists after every checkout, so the root is always the
    repository root - and the artifact records the pins the job ran with."""
    found = artifact_paths()
    assert found
    assert [name for name, ps in found.items() if ANCHOR not in ps] == []


def test_every_action_is_pinned_in_tools_md() -> None:
    used = sorted({m[1] for l in lines() if (m := re.search(r'uses: (\S+@\S+)', l))})
    tools_md = (ROOT / 'TOOLS.md').read_text(encoding='utf-8')
    assert used and [u for u in used if f'`{u}`' not in tools_md] == []


def test_schedule_permissions_and_timeouts() -> None:
    text = YML.read_text(encoding='utf-8')
    assert "    - cron: '23 4 1 * *'" in text
    assert '\npermissions: {}\n' in text
    chain = jobs()['chain']
    assert int(next(l.split(':')[1] for l in chain if l.strip().startswith('timeout-minutes:'))) >= 90
    # contents: write only where a job writes (draft, gate's contact sheets, publish, pr, heartbeat): every job names
    # its permissions itself
    assert all(any(l.strip() == 'permissions:' for l in body) for body in jobs().values())


def test_publish_and_pr_need_a_green_gate() -> None:
    """P3: a red gate ends the run red; nothing is published, no PR."""
    for job in ('publish', 'pr'):
        cond = next(l for l in jobs()[job] if l.strip().startswith('if:'))
        assert "needs.gate.result == 'success'" in cond, cond


def step_named(job: str, prefix: str) -> list[str]:
    return next(s for s in steps(jobs()[job]) if any(l.strip().startswith(f'- name: {prefix}') or
                                                     l.strip().startswith(f'name: {prefix}') for l in s))


def test_the_hauling_step_never_stops_the_chain() -> None:
    """K2 (H1): a failed or crashed hauling step colours itself only - the ship data go on; it runs after previous
    (the last release's files) and before diff (a hauling change alone releases, SD14)."""
    names = [next((l.split('name:', 1)[1].strip() for l in s if 'name:' in l), s[0].strip()) for s in steps(jobs()['chain'])]
    at = next(i for i, n in enumerate(names) if n.startswith('Hauling'))
    assert names[at - 1] == 'Last release' and names[at + 1] == 'Diff'
    hauling = step_named('chain', 'Hauling')
    assert '        continue-on-error: true' in hauling and '        id: hauling' in hauling
    assert any(l.strip() == 'run: python -I tools/run.py hauling' for l in hauling)
    outputs = '\n'.join(jobs()['chain'])
    assert 'hauling: ${{ steps.hauling.outputs.status }}' in outputs
    assert 'haulingStep: ${{ steps.hauling.outcome }}' in outputs


def test_hauling_pr_reports_every_failure_and_the_heartbeat_waits_for_it() -> None:
    """E1: a failed status or a crashed step opens the alias PR or the issue - never silent."""
    body = jobs()['hauling-pr']
    cond = next(l for l in body if l.strip().startswith('if:'))
    assert "needs.chain.outputs.hauling == 'failed'" in cond and "needs.chain.outputs.haulingStep == 'failure'" in cond
    assert cond.strip().startswith('if: always() &&')
    perms = body[body.index('    permissions:') + 1:body.index('    permissions:') + 4]
    assert sorted(l.strip() for l in perms) == ['contents: write', 'issues: write', 'pull-requests: write']
    needs = next(l for l in jobs()['heartbeat'] if l.strip().startswith('needs:'))
    assert 'hauling-pr' in needs
