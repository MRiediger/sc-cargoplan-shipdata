"""The stages tell the workflow where to go through $GITHUB_OUTPUT (P7): no logic in YAML, only `if:` on these values.
verify --ci turns exit 2 (a rule fired) into exit 0 with path=pr; locally exit 2 stays the contract (T12.1)."""
import json
from pathlib import Path

import pytest

import run
from conftest import TOOLS


def outputs(path: Path) -> dict[str, str]:
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines() if '=' in line)


def test_pins_names_the_app_tag_and_the_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / 'github-output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(out))
    assert run.main(['--root', str(tmp_path), 'pins']) == 0
    pins = json.loads((TOOLS / 'pins.json').read_text(encoding='utf-8'))
    assert outputs(out) == {'appTag': pins['appTag'], 'runner': pins['runner']}


@pytest.mark.parametrize('rc, ci, expected_rc, path', [(2, True, 0, 'pr'), (0, True, 0, 'release'), (2, False, 2, 'pr'),
                                                        (1, True, 1, None)])
def test_verify_ci_maps_the_pr_path_to_an_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rc: int, ci: bool,
                                                  expected_rc: int, path: str | None) -> None:
    out = tmp_path / 'github-output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(out))
    monkeypatch.setattr(run.stages, 'verify_stage', lambda *a: rc)
    assert run.main(['--root', str(tmp_path), 'verify', *(['--ci'] if ci else [])]) == expected_rc
    assert outputs(out).get('path') == path if out.exists() else path is None
