"""gh and git behind one function each (T12.2): the workflow stages call only these, tests replace them with a recorder
(monkeypatch), so every stage runs without GitHub. gh reads GH_TOKEN from the environment; it is set only in the steps
that need it, and its value never reaches a message here (the commands are logged, never the environment)."""
import json
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """stdout as text; a failure raises with the tool's own reason (its stderr) - CalledProcessError's text says only
    'returned non-zero exit status 1' (run 44296781671, A16). Only the tool and its first two arguments are named: the
    rest can be long (a PR title, a file path) and adds nothing to the reason."""
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        reason = (e.stderr or e.stdout or '').strip() or f'exit status {e.returncode}'
        raise RuntimeError(f"{' '.join(cmd[:3])} failed: {reason}") from e


def gh(*args: str) -> str:
    """One gh call (gh 2.102, flags checked against `gh <command> --help`, A3)."""
    return run(['gh', *args])


def gh_json(*args: str) -> object:
    return json.loads(gh(*args) or 'null')


def git(*args: str, cwd: Path) -> str:
    return run(['git', *args], cwd=cwd)
