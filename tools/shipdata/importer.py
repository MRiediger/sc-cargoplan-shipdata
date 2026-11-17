"""Runs tools/import-motherlode.ps1 under pwsh (racks and anchors stay in PowerShell, plan T12.1 P6) and reads its report.

Exit codes of the script: 0 done, 1 something to look at (listed in the report), 2 error (nothing written)."""
import csv
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'import-motherlode.ps1'


class ImportError_(RuntimeError):
    """The import script failed (exit 2) or wrote no report."""


@dataclass
class ImportResult:
    rc: int
    output: str
    entries: list[dict] = field(default_factory=list)

    @property
    def by_id(self) -> dict[str, dict]:
        return {e['id']: e for e in self.entries}


def write_key_map(path: Path, key_map: dict[str, str]) -> Path:
    """className -> modelKey of the last release, for ships the import creates (-Create)."""
    with path.open('w', encoding='utf-8', newline='\n') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['className', 'modelKey'])
        for cls in sorted(key_map):
            w.writerow([cls, key_map[cls]])
    return path


def run_import(catalog: Path, ships: Path, outlines: Path, model_map: Path, report: Path, key_map: dict[str, str],
               create: bool = True, previous: Path | None = None) -> ImportResult:
    keys = write_key_map(report.with_name(report.stem + '-keys.csv'), key_map)
    args = [os.environ.get('PWSH', 'pwsh'), '-NoProfile', '-NonInteractive', '-File', str(SCRIPT), '-Catalog', str(catalog),
            '-ShipsFolder', str(ships), '-Outlines', str(outlines), '-ModelMap', str(model_map), '-Report', str(report),
            '-KeyMap', str(keys)]
    if create:
        args.append('-Create')
    if previous:
        args += ['-Previous', str(previous)]
    if report.exists():
        report.unlink()
    # NO_COLOR: pwsh >= 7.2 then writes errors without ANSI escapes (about_ANSI_Terminals), readable in logs.
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', env=dict(os.environ, NO_COLOR='1'))
    output = p.stdout + p.stderr
    if p.returncode not in (0, 1):
        raise ImportError_(f'import-motherlode.ps1 exit {p.returncode}: {output.strip()[-2000:]}')
    if not report.exists():
        raise ImportError_(f'import-motherlode.ps1 exit {p.returncode} without a report: {output.strip()[-2000:]}')
    return ImportResult(p.returncode, output, json.loads(report.read_text(encoding='utf-8-sig')))
