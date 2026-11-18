"""Every stage ends with three lines - checked / found / to do - on the screen and in $GITHUB_STEP_SUMMARY; numbers go to
out/numbers.tsv (pattern of spike/say.sh, S12.0). A log file is an attachment, never the only source (CLAUDE.md)."""
import json
import os
from pathlib import Path


class Reporter:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

    def say(self, step: str, checked: str, found: str, todo: str) -> None:
        print(f'\n=== {step}\n  checked: {checked}\n  found:   {found}\n  to do:   {todo}\n', flush=True)
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a', encoding='utf-8') as f:
                f.write(f'### {step}\n- **checked:** {checked}\n- **found:** {found}\n- **to do:** {todo}\n\n')
        # The same three lines for the heartbeat (state/last-run.json), one file per job (GITHUB_JOB), sent on as a report.
        job = os.environ.get('GITHUB_JOB', 'local')
        with (self.out_dir / f'say-{job}.jsonl').open('a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps({'job': job, 'step': step, 'checked': checked, 'found': found, 'todo': todo}) + '\n')

    def headline(self, text: str) -> None:
        """The one line of a run (SD11), at the top of the heartbeat job's summary."""
        print(f'\n##### {text}\n', flush=True)
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a', encoding='utf-8') as f:
                f.write(f'## {text}\n\n')

    def output(self, key: str, value: object) -> None:
        """A step output for the workflow's conditions ($GITHUB_OUTPUT, key=value); nothing outside Actions. Values are
        tags, hashes and words - never a secret."""
        target = os.environ.get('GITHUB_OUTPUT')
        if target:
            with open(target, 'a', encoding='utf-8') as f:
                f.write(f'{key}={value}\n')
        print(f'  > {key} = {value}', flush=True)

    def num(self, key: str, value: object) -> None:
        with (self.out_dir / 'numbers.tsv').open('a', encoding='utf-8', newline='\n') as f:
            f.write(f'{key}\t{value}\n')
        print(f'  # {key} = {value}', flush=True)

    def line(self, text: str) -> None:
        print(f'  {text}', flush=True)
