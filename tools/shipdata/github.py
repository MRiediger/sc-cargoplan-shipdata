"""gh and git behind one function each (T12.2): the workflow stages call only these, tests replace them with a recorder
(monkeypatch), so every stage runs without GitHub. gh reads GH_TOKEN from the environment; it is set only in the steps
that need it, and its value never reaches a message here (the commands are logged, never the environment)."""
import json
import subprocess
from pathlib import Path


def gh(*args: str) -> str:
    """One gh call (gh 2.102, flags checked against `gh <command> --help`, A3); stdout as text, a failure raises."""
    return subprocess.run(['gh', *args], capture_output=True, text=True, check=True).stdout


def gh_json(*args: str) -> object:
    return json.loads(gh(*args) or 'null')


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True).stdout
