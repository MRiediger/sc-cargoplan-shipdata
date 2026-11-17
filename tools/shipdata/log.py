"""Every stage ends with three lines - checked / found / to do - on the screen and in $GITHUB_STEP_SUMMARY; numbers go to
out/numbers.tsv (pattern of spike/say.sh, S12.0). A log file is an attachment, never the only source (CLAUDE.md)."""
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

    def num(self, key: str, value: object) -> None:
        with (self.out_dir / 'numbers.tsv').open('a', encoding='utf-8', newline='\n') as f:
            f.write(f'{key}\t{value}\n')
        print(f'  # {key} = {value}', flush=True)

    def line(self, text: str) -> None:
        print(f'  {text}', flush=True)
