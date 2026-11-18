"""run.py gate - the render gate (SD3, P3, P5), on windows-latest: the last release and the new draft rendered with the
same app (sc-cargoplan at appTag, tools/pins.json) in one job, hash-exact. Only ships whose data changed may differ.

  old state  -> app/ships, app/outlines/ship-outlines.json; bin/**/ships emptied; dotnet build; bin checked against it;
                ShipPictureTests without baseline (every PNG)
  new state  -> the same; ShipPictureTests with the old run as baseline and the expected ships
  compare    -> gate.json; contact sheets (unexpected ships first, then the stops) to the draft, also when red

S12.0 E3: ShipPictureTests reads ships/ and outlines/ from bin (CopyToOutputDirectory IfDifferent: copies, never
deletes), so the swap empties bin and checks the copy - a build that kept old files would measure old data. Ports
tools/gate/{pictures.sh, swap.sh, csvdiff.py} (S12.0). Exit 1 when a ship differs that nobody expected."""
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from shipdata import diff, github, manifest, release, sheet, workflow
from shipdata.log import Reporter

TESTS = Path('tests') / 'CargoPlan.App.Tests'
FILTER = 'FullyQualifiedName~ShipPictureTests'


class GateError(RuntimeError):
    pass


def read_csv(path: Path) -> dict[str, str]:
    """pictures.csv (key = id;look;size;camera -> hash) or values.csv (id -> placement numbers), as ShipPictureTests.Split:
    a line with two separators is a value line keyed by the ship id, a picture line is keyed by all but its hash."""
    rows = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            parts = line.split(';', 1) if line.count(';') == 2 else line.rsplit(';', 1)
            if len(parts) == 2:
                rows[parts[0]] = parts[1]
    return rows


@dataclass
class Runs:
    equal: int
    different: list[str] = field(default_factory=list)      # picture keys new or with another hash
    missing: list[str] = field(default_factory=list)        # picture keys only in the old run
    numbers: list[str] = field(default_factory=list)        # ship ids whose placement numbers differ

    def ships(self) -> list[str]:
        return sorted({k.split(';', 1)[0] for k in self.different + self.missing} | set(self.numbers))


def compare_runs(old: Path, new: Path) -> Runs:
    """Two picture runs, as ShipPictureTests.Compare counts them."""
    before, after = read_csv(old / 'pictures.csv'), read_csv(new / 'pictures.csv')
    vb, va = read_csv(old / 'values.csv'), read_csv(new / 'values.csv')
    different = sorted(k for k in after if before.get(k) != after[k])
    return Runs(equal=len(after) - len(different), different=different, missing=sorted(set(before) - set(after)),
                numbers=sorted(k for k in va if vb.get(k) != va[k]))


def unexpected(runs: Runs, expected: list[str]) -> list[str]:
    return [s for s in runs.ships() if s not in set(expected)]


def expected_ids(old_m: dict, new_m: dict, old_data: Path, new_data: Path) -> list[str]:
    """Ships allowed to differ: their file without stamps (diff.content_hash), their hologram (SHA-256) or their outline
    entry changed, or they are new. Not the byte hashes of `files`: a new catalog date changes `source` in nearly every
    file (S12.0 run 4: 99) and would make every ship 'expected' - the gate would check nothing. A hologram or outline
    counts for every ship of its modelKey."""
    holo = lambda m: {s: e['sha256'] for s, e in ((m.get('holo') or {}).get('ships') or {}).items()}
    outlines = lambda d: {e['slug']: json.dumps(e, sort_keys=True)
                          for e in json.loads((d / 'outlines.json').read_text(encoding='utf-8-sig'))['ships']}
    ho, hn, oo, on = holo(old_m), holo(new_m), outlines(old_data), outlines(new_data)
    moved = {s for s in set(ho) | set(hn) if ho.get(s) != hn.get(s)} | {s for s in set(oo) | set(on) if oo.get(s) != on.get(s)}
    out = []
    for q in sorted((new_data / 'ships').glob('*.json')):
        doc = json.loads(q.read_text(encoding='utf-8-sig'))
        old = old_data / 'ships' / q.name
        if (not old.exists() or diff.content_hash(json.loads(old.read_text(encoding='utf-8-sig'))) != diff.content_hash(doc)
                or doc.get('modelKey') in moved):
            out.append(q.stem)
    # Cargo modules (app K5.3): ShipLoader adds one entry <ship>_<module> per ship a module names
    # (ModuleDto.ConfigurationId), rendered with the base ship's hologram and outline. It may differ when its base may,
    # or when the module file itself changed (without stamps). Found by the local gate of 18 Nov (aurora_mk_ii_ts_module).
    read = lambda q: json.loads(q.read_text(encoding='utf-8-sig')) if q.exists() else None
    bases = set(out)
    for name in sorted({q.name for d in (old_data, new_data) for q in (d / 'ships' / 'modules').glob('*.json')}):
        old_mod, new_mod = read(old_data / 'ships' / 'modules' / name), read(new_data / 'ships' / 'modules' / name)
        changed = old_mod is None or new_mod is None or diff.content_hash(old_mod) != diff.content_hash(new_mod)
        for mod in (m for m in (old_mod, new_mod) if m):
            out += [f"{sid}_{mod['id']}" for sid in mod.get('ships', []) if changed or sid in bases]
    return sorted(set(out))


def sheet_order(runs: Runs, unexpected: list[str], new_m: dict, verify: dict) -> list[tuple[str, str]]:
    """The contact sheet's ships: unexpected first (a red gate must be visible, Martin 18 Nov), then the ships of
    findings that stop the release (a judge finding names a hologram: every ship of that modelKey), then every other
    ship with a differing picture."""
    ships = new_m['ships']
    stops = set()
    for f in verify.get('findings', []):
        if f['stop']:
            stops |= {f['id']} if f['id'] in ships else {s for s, e in ships.items() if e.get('modelKey') == f['id']}
    order = [(s, 'UNEXPECTED') for s in unexpected]
    order += [(s, 'stop') for s in sorted(stops) if s not in unexpected]
    order += [(s, '') for s in runs.ships() if s not in unexpected and s not in stops]
    return order


# ---------------------------------------------------------------- the app checkout (replaced in tests)

def bin_dirs(app: Path) -> list[Path]:
    root = app / TESTS / 'bin' / 'Release'
    return sorted(d for d in root.iterdir() if d.is_dir()) if root.exists() else []


def swap(app: Path, data: Path) -> None:
    """A release's ships/ and outlines.json into the checkout; bin's copies go, the build copies them anew."""
    shutil.rmtree(app / 'ships')
    shutil.copytree(data / 'ships', app / 'ships')
    shutil.copyfile(data / 'outlines.json', app / 'outlines' / 'ship-outlines.json')
    for b in bin_dirs(app):
        if (b / 'ships').exists():
            shutil.rmtree(b / 'ships')
        (b / 'outlines' / 'ship-outlines.json').unlink(missing_ok=True)


def bin_problems(app: Path, data: Path) -> list[str]:
    """bin must hold exactly the swapped state, or the picture run measures other data (S12.0 swap.sh, check s4)."""
    dirs = bin_dirs(app)
    if not dirs:
        return [f'no bin folder under {app / TESTS}']
    files = lambda root: {q.relative_to(root).as_posix(): q.read_bytes() for q in root.rglob('*.json')} if root.exists() else {}
    want = files(data / 'ships')
    problems = []
    for b in dirs:
        have = files(b / 'ships')
        bad = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
        if bad:
            problems.append(f"{b.name}/ships: {len(bad)} files differ from the state ({', '.join(bad[:5])})")
        o = b / 'outlines' / 'ship-outlines.json'
        if not o.exists() or o.read_bytes() != (data / 'outlines.json').read_bytes():
            problems.append(f'{b.name}/outlines/ship-outlines.json differs from the state')
    return problems


def build(app: Path, log: Path) -> None:
    with log.open('w', encoding='utf-8') as f:
        r = subprocess.run(['dotnet', 'build', str(TESTS), '-c', 'Release'], cwd=app, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        tail = log.read_text(encoding='utf-8', errors='replace').splitlines()[-20:]
        raise GateError(f'dotnet build failed (exit {r.returncode}), see {log}:\n' + '\n'.join(tail))


def pictures(app: Path, out: Path, holo: Path, baseline: Path | None, expected: list[str], log: Path) -> int:
    """One ShipPictureTests run (app CLAUDE.md, Befehle; S12.0 pictures.sh): its exit code; pictures.csv, values.csv,
    report.txt and the PNGs land in `out`."""
    if out.exists():
        shutil.rmtree(out)
    env = {k: v for k, v in os.environ.items() if k not in ('CARGOPLAN_PICTURES_BASELINE', 'CARGOPLAN_PICTURES_EXPECTED')}
    env.update(CARGOPLAN_PICTURES_OUT=str(out.resolve()), CARGOPLAN_HOLO_FOLDER=str(holo.resolve()))
    if baseline is not None:
        env['CARGOPLAN_PICTURES_BASELINE'] = str(baseline.resolve())
    if expected:
        env['CARGOPLAN_PICTURES_EXPECTED'] = ','.join(expected)
    with log.open('w', encoding='utf-8') as f:
        return subprocess.run(['dotnet', 'test', str(TESTS), '-c', 'Release', '--no-build', '-p:RunSettingsFilePath=',
                               '--filter', FILTER], cwd=app, env=env, stdout=f, stderr=subprocess.STDOUT).returncode


# ---------------------------------------------------------------- the stage

def obtain(p, side: str, tag: str | None, folder: Path | None) -> tuple[Path, Path, dict]:
    """A release's assets (downloaded by tag, or a local folder) checked against its manifest, ships.zip unpacked."""
    assets = folder or p.w(f'gate/{side}')
    if folder is None:
        if not tag:
            raise GateError(f'gate needs --{side}-tag or --{side}')
        if assets.exists():
            shutil.rmtree(assets)
        github.gh('release', 'download', tag, '--dir', str(assets))
    m = manifest.read(assets / 'manifest.json')
    problems = workflow.holo_problems(assets, m)
    if problems:
        raise GateError(f'{side} release {m["dataVersion"]} differs from its manifest: {"; ".join(problems[:5])}')
    data = p.w(f'gate/{side}-data')
    release.unpack(assets, data)
    return assets, data, m


def gate_stage(p, log: Reporter, app: Path, old_tag: str | None = None, new_tag: str | None = None,
               old_dir: Path | None = None, new_dir: Path | None = None, upload_tag: str | None = None) -> int:
    seconds: dict[str, float] = {}
    old_assets, old_data, om = obtain(p, 'old', old_tag, old_dir)
    new_assets, new_data, nm = obtain(p, 'new', new_tag, new_dir)
    expected = expected_ids(om, nm, old_data, new_data)
    pics = p.w('gate') / 'pics'
    rc = {}
    for side, data, holo, baseline, exp in (('old', old_data, old_assets, None, []), ('new', new_data, new_assets, pics / 'old', expected)):
        t = time.monotonic()
        swap(app, data)
        build(app, p.out / f'gate-build-{side}.log')
        seconds[f'build-{side}'] = round(time.monotonic() - t, 1)
        problems = bin_problems(app, data)
        if problems:
            raise GateError(f'bin does not hold the {side} state after the build: {"; ".join(problems)}')
        t = time.monotonic()
        rc[side] = pictures(app, pics / side, holo, baseline, exp, p.out / f'gate-pictures-{side}.log')
        seconds[f'pictures-{side}'] = round(time.monotonic() - t, 1)
    if rc['old'] != 0:
        raise GateError(f"ShipPictureTests of the old state failed (exit {rc['old']}, no baseline): see {p.out / 'gate-pictures-old.log'}")
    runs = compare_runs(pics / 'old', pics / 'new')
    unexp = unexpected(runs, expected)
    verify = workflow.load_optional(p.w('verify.json')) or {}
    order = sheet_order(runs, unexp, nm, verify)
    made = sheet.sheets([s for s, _ in order], pics / 'old', pics / 'new', p.w('gate') / 'sheets', dict(order))
    if upload_tag and made:             # before exit 1 too: a red gate must be visible on the draft (Martin, 18 Nov)
        github.gh('release', 'upload', upload_tag, *[str(q) for q, _ in made], '--clobber')
    g = {'old': om['dataVersion'], 'new': nm['dataVersion'],
         'pictures': {'equal': runs.equal, 'different': len(runs.different), 'missing': len(runs.missing)},
         'numbers': runs.numbers, 'expected': expected, 'expectedShips': len(expected), 'unexpected': unexp,
         'sheets': [q.name for q, _ in made], 'sheetShips': [{'id': s, 'mark': mk} for s, mk in order], 'rc': rc, 'seconds': seconds}
    workflow.save_json(p.w('gate.json'), g)
    report = pics / 'new' / 'report.txt'
    if rc['new'] != 0 and not unexp:
        raise GateError(f"ShipPictureTests failed (exit {rc['new']}) without a picture difference outside the expected ships: "
                        f"see {report} and {p.out / 'gate-pictures-new.log'}")
    for k, v in seconds.items():
        log.num(f'gate.{k}.s', v)
    log.num('gate.pictures.equal', runs.equal)
    log.num('gate.pictures.different', len(runs.different))
    log.num('gate.unexpected', len(unexp))
    log.say('gate', f"{om['dataVersion']} and {nm['dataVersion']} rendered with the same app in one job "
            f"({sum(seconds.values()):.0f} s); {len(expected)} ships expected to change (data without stamps, hologram, outline)",
            f"{runs.equal} pictures equal, {len(runs.different)} different, {len(runs.missing)} missing, placement numbers "
            f"differ for {len(runs.numbers)}; unexpected: {', '.join(unexp) or 'none'}; "
            f"{len(made)} contact sheets" + (f' on draft {upload_tag}' if upload_tag and made else ''),
            'none: publish or PR' if not unexp else
            f'gate red: {len(unexp)} ships differ unexpectedly - the contact sheet shows them first; nothing is published')
    return 1 if unexp else 0
