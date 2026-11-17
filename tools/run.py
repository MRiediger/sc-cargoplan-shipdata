"""run.py - the one entry point of the SC-CargoPlan ship data pipeline, locally and in CI (TASKS.md: one script for both).

  python -I tools/run.py fetch [--saved <dir>] [--catalog-only]      catalog (one API call, or saved answers), models by hash
  python -I tools/run.py diff --previous <release dir> [--previous-catalog <catalog.json>]
  python -I tools/run.py build [--ship <id> ...] [--all] [--data-version V] [--generated-at T]
  python -I tools/run.py verify [--app-tag T] [--today D]
  python -I tools/run.py release --dry-run
  python -I tools/run.py release --seed --app <sc-cargoplan> --holo <holo release dir> [--out <dir>]

Stages hand on through <root>/work (see shipdata/stages.py). Exit codes: 0 done, 1 error, 2 a rule fired (PR path).
Every stage ends with checked / found / to do on the screen and in $GITHUB_STEP_SUMMARY."""
import argparse
import datetime as dt
import sys
from pathlib import Path

# -I implies -P, which leaves the script's own folder off sys.path (Python docs, "Command line and environment", -P and -I);
# the package next to this file is added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shipdata import stages  # noqa: E402
from shipdata.log import Reporter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APP_TAG = 'v0.5.1'      # the app the gate renders with; pinned in TOOLS.md with T12.2


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog='run.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', type=Path, default=ROOT, help='folder holding work/, cache/, out/ and overrides.json')
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('--saved', type=Path, help='saved answers (api.json + page.txt or page-ships.json) instead of the API')
    f.add_argument('--catalog-only', action='store_true')
    d = sub.add_parser('diff')
    d.add_argument('--previous', type=Path, required=True, help='folder of the last release (ships/, outlines.json, holo/, manifest.json)')
    d.add_argument('--previous-catalog', type=Path, help='catalog.json of the last run: the import then compares grid order')
    b = sub.add_parser('build')
    b.add_argument('--ship', action='append', default=[], help='build the model of this ship id (repeatable)')
    b.add_argument('--all', action='store_true', help='build every model, changed or not')
    b.add_argument('--data-version', default=f'ships-{dt.date.today():%Y.%m}')
    b.add_argument('--generated-at', default=stages.utc_now())
    v = sub.add_parser('verify')
    v.add_argument('--app-tag', default=APP_TAG)
    v.add_argument('--today', default=dt.date.today().isoformat(), help='date written as missingSince for newly gone ships')
    r = sub.add_parser('release')
    mode = r.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--seed', action='store_true', help='first release folder from the app and a holo release (no catalog)')
    r.add_argument('--app', type=Path, help='--seed: sc-cargoplan checkout at the tag')
    r.add_argument('--holo', type=Path, help='--seed: the holo release assets (manifest.json, <slug>.holo)')
    r.add_argument('--out', type=Path, help='--seed: target folder (default out/seed)')
    r.add_argument('--app-tag', default=APP_TAG)
    r.add_argument('--data-version', default=f'ships-{dt.date.today():%Y.%m}')
    r.add_argument('--generated-at', default=stages.utc_now())
    a = ap.parse_args(argv)

    p = stages.Paths(a.root.resolve())
    log = Reporter(p.out)
    try:
        if a.cmd == 'fetch':
            return stages.fetch_stage(p, log, a.saved, a.catalog_only)
        if a.cmd == 'diff':
            return stages.diff_stage(p, log, a.previous, a.previous_catalog)
        if a.cmd == 'build':
            return stages.build_stage(p, log, a.ship, a.all, a.data_version, a.generated_at)
        if a.cmd == 'verify':
            return stages.verify_stage(p, log, a.app_tag, a.today)
        if a.seed:
            if not (a.app and a.holo):
                ap.error('--seed needs --app and --holo')
            return stages.seed_stage(p, log, a.app, a.holo, a.out or p.out / 'seed', a.app_tag, a.data_version, a.generated_at)
        return stages.release_stage(p, log, a.dry_run)
    except Exception as e:
        # The boundary of the run: the three summary lines for the error, then re-raised (trace, exit 1).
        log.say(a.cmd, f'run.py {" ".join(argv)}', f'error: {type(e).__name__}: {e}', 'fix the cause; nothing was released')
        raise


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
