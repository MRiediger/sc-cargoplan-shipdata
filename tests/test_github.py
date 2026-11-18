"""shipdata.github: a failed gh or git call names its reason. Run 44296781671 failed in `gh pr create` with only
'returned non-zero exit status 1' - gh's message was in stderr, which subprocess keeps on the exception but not in its
text, so the stage's 'found' line and the heartbeat could not say why (A16)."""
import subprocess

import pytest

from shipdata import github

REASON = 'pull request create failed: GraphQL: GitHub Actions is not permitted to create or approve pull requests'


@pytest.fixture
def failing(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:
        calls.append(cmd)
        raise subprocess.CalledProcessError(1, cmd, output='', stderr=REASON + '\n')

    monkeypatch.setattr(github.subprocess, 'run', run)
    return calls


def test_a_failed_gh_call_names_gh_s_reason(failing: list[list[str]]) -> None:
    with pytest.raises(RuntimeError) as e:
        github.gh('pr', 'create', '--base', 'main')
    assert 'gh pr create' in str(e.value) and REASON in str(e.value)
    assert isinstance(e.value.__cause__, subprocess.CalledProcessError)


def test_a_failed_git_call_names_git_s_reason(failing: list[list[str]], tmp_path) -> None:
    with pytest.raises(RuntimeError) as e:
        github.git('push', 'origin', 'HEAD:main', cwd=tmp_path)
    assert 'git push' in str(e.value) and REASON in str(e.value)


def test_a_good_call_returns_stdout(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(github.subprocess, 'run',
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout='ok\n', stderr=''))
    assert github.gh('api', 'x') == 'ok\n' and github.git('status', cwd=tmp_path) == 'ok\n'
