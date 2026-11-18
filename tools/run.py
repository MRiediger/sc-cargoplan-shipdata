"""run.py - the one entry point of the SC-CargoPlan ship data pipeline, locally and in CI (TASKS.md: one script for both).

  python -I tools/run.py fetch [--saved <dir>] [--catalog-only]      catalog (one API call, or saved answers), models by hash
  python -I tools/run.py previous [--today D]                       the last release (gh), and this run's release name
  python -I tools/run.py diff --previous <release dir>
  python -I tools/run.py build [--ship <id> ...] [--all] [--data-version V] [--generated-at T]
  python -I tools/run.py verify [--app-tag T] [--today D] [--ci]    --ci: exit 2 becomes 0, path=pr in $GITHUB_OUTPUT
  python -I tools/run.py pins                                       appTag and runner (tools/pins.json) as step outputs
  python -I tools/run.py release --dry-run
  python -I tools/run.py release --seed --app <sc-cargoplan> --holo <holo release dir> --catalog <raw dir> [--out <dir>]
  python -I tools/run.py draft [--folder <release dir>] [--target SHA]  the draft release, manifest.json uploaded last
  python -I tools/run.py publish (--tag T | --pending state/pending.json) [--target SHA]
  python -I tools/run.py gate --app <sc-cargoplan checkout> (--old-tag T | --old DIR) (--new-tag T | --new DIR)
                                                                    render gate on Windows; contact sheets to --new-tag
  python -I tools/run.py pr --tag T [--dry-run]                     PR data/YYYY.MM with state/pending.json (merge = release)
  python -I tools/run.py heartbeat                                  state/last-run.json + commit (NEEDS = toJSON(needs))

Stages hand on through <root>/work (see shipdata/stages.py). Exit codes: 0 done, 1 error, 2 a rule fired (PR path).
Every stage ends with checked / found / to do on the screen and in $GITHUB_STEP_SUMMARY."""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

# -I implies -P, which leaves the script's own folder off sys.path (Python docs, "Command line and environment", -P and -I);
# the package next to this file is added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shipdata import gate, stages, workflow  # noqa: E402
from shipdata.log import Reporter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# The app the gate renders with. One machine-readable source per pin (SD8): tools/pins.json; TOOLS.md is the copy.
PINS: dict[str, str] = json.loads((ROOT / 'tools' / 'pins.json').read_text(encoding='utf-8'))
APP_TAG: str = PINS['appTag']


def run_id() -> str:
    return os.environ.get('GITHUB_RUN_ID', 'local')


def run_url() -> str:
    """The run's page (Actions sets GITHUB_SERVER_URL, GITHUB_REPOSITORY and GITHUB_RUN_ID); '-' locally."""
    e = os.environ
    return f"{e['GITHUB_SERVER_URL']}/{e['GITHUB_REPOSITORY']}/actions/runs/{e['GITHUB_RUN_ID']}" if 'GITHUB_RUN_ID' in e else '-'


def head() -> str:
    """The commit a release points at: the workflow's GITHUB_SHA, locally HEAD (full SHA, gh release --target)."""
    return os.environ.get('GITHUB_SHA') or subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True,
                                                          text=True, check=True).stdout.strip()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog='run.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', type=Path, default=ROOT, help='folder holding work/, cache/, out/ and overrides.json')
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('--saved', type=Path, help='saved answers (api.json + page.txt or page-ships.json) instead of the API')
    f.add_argument('--catalog-only', action='store_true')
    pv = sub.add_parser('previous')
    pv.add_argument('--today', type=dt.date.fromisoformat, default=dt.date.today())
    d = sub.add_parser('diff')
    d.add_argument('--previous', type=Path, required=True, help='folder of the last release (ships/, outlines.json, holo/, manifest.json)')
    b = sub.add_parser('build')
    b.add_argument('--ship', action='append', default=[], help='build the model of this ship id (repeatable)')
    b.add_argument('--all', action='store_true', help='build every model, changed or not')
    b.add_argument('--data-version', help="default: this run's release name from previous (work/previous.json), "
                                           'else ships-YYYY.MM of today')
    b.add_argument('--generated-at', default=stages.utc_now())
    v = sub.add_parser('verify')
    v.add_argument('--app-tag', default=APP_TAG)
    v.add_argument('--today', default=dt.date.today().isoformat(), help='date written as missingSince for newly gone ships')
    v.add_argument('--ci', action='store_true', help='in the workflow: a fired rule is path=pr with exit 0 (P7)')
    sub.add_parser('pins')
    r = sub.add_parser('release')
    mode = r.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--seed', action='store_true', help='first release folder from the app and a holo release (no catalog)')
    r.add_argument('--app', type=Path, help='--seed: sc-cargoplan checkout at the tag')
    r.add_argument('--holo', type=Path, help='--seed: the holo release assets (manifest.json, <slug>.holo)')
    r.add_argument('--catalog', type=Path, help='--seed: saved answers of the catalog the app data was built from (orderKeys)')
    r.add_argument('--out', type=Path, help='--seed: target folder (default out/seed)')
    r.add_argument('--app-tag', default=APP_TAG)
    r.add_argument('--data-version', default=f'ships-{dt.date.today():%Y.%m}')
    r.add_argument('--generated-at', default=stages.utc_now())
    dr = sub.add_parser('draft')
    dr.add_argument('--folder', type=Path, help='a packed release folder (the seed); default: pack work/stage')
    dr.add_argument('--target', default=None, help='commit of the release (default GITHUB_SHA, else HEAD)')
    pb = sub.add_parser('publish')
    which = pb.add_mutually_exclusive_group(required=True)
    which.add_argument('--tag')
    which.add_argument('--pending', type=Path, help='state/pending.json of a merged PR (P6)')
    pb.add_argument('--target', default=None, help='commit of the release (default GITHUB_SHA, else HEAD)')
    g = sub.add_parser('gate')
    g.add_argument('--app', type=Path, required=True, help='sc-cargoplan checked out at appTag (tools/pins.json)')
    old = g.add_mutually_exclusive_group(required=True)
    old.add_argument('--old-tag', help='the last release (gh release download)')
    old.add_argument('--old', type=Path, help='a local release folder instead')
    new = g.add_mutually_exclusive_group(required=True)
    new.add_argument('--new-tag', help="this run's draft release; the contact sheets are uploaded to it")
    new.add_argument('--new', type=Path, help='a local release folder instead (nothing uploaded)')
    pr = sub.add_parser('pr')
    pr.add_argument('--tag', required=True, help='the draft release the PR names')
    pr.add_argument('--dry-run', action='store_true', help='write out/pr-body.md only: no git, no gh')
    hb = sub.add_parser('heartbeat')
    hb.add_argument('--today', default=dt.date.today().isoformat())
    a = ap.parse_args(argv)

    p = stages.Paths(a.root.resolve())
    log = Reporter(p.out)
    try:
        if a.cmd == 'fetch':
            return stages.fetch_stage(p, log, a.saved, a.catalog_only)
        if a.cmd == 'previous':
            return workflow.previous_stage(p, log, a.today)
        if a.cmd == 'draft':
            return workflow.draft_stage(p, log, a.folder, a.target or head())
        if a.cmd == 'publish':
            return workflow.publish_stage(p, log, a.tag, a.pending, a.target or head())
        if a.cmd == 'gate':
            return gate.gate_stage(p, log, a.app.resolve(), old_tag=a.old_tag, new_tag=a.new_tag, old_dir=a.old,
                                   new_dir=a.new, upload_tag=a.new_tag)
        if a.cmd == 'pr':
            return workflow.pr_stage(p, log, a.tag, run_id(), run_url(), a.dry_run)
        if a.cmd == 'heartbeat':
            return workflow.heartbeat_stage(p, log, json.loads(os.environ.get('NEEDS') or '{}'),
                                            os.environ.get('GITHUB_EVENT_NAME', 'local'), run_id(), run_url(), a.today)
        if a.cmd == 'diff':
            return stages.diff_stage(p, log, a.previous)
        if a.cmd == 'build':
            version = a.data_version or (json.loads(p.w('previous.json').read_text(encoding='utf-8'))['nextVersion']
                                         if p.w('previous.json').exists() else f'ships-{dt.date.today():%Y.%m}')
            return stages.build_stage(p, log, a.ship, a.all, version, a.generated_at)
        if a.cmd == 'pins':
            log.output('appTag', PINS['appTag'])
            log.output('runner', PINS['runner'])
            return 0
        if a.cmd == 'verify':
            rc = stages.verify_stage(p, log, a.app_tag, a.today)
            if rc in (0, 2):
                log.output('path', 'pr' if rc == 2 else 'release')
            return 0 if a.ci and rc == 2 else rc
        if a.seed:
            if not (a.app and a.holo and a.catalog):
                ap.error('--seed needs --app, --holo and --catalog')
            return stages.seed_stage(p, log, a.app, a.holo, a.catalog, a.out or p.out / 'seed', a.app_tag, a.data_version,
                                     a.generated_at)
        return stages.release_stage(p, log, a.dry_run)
    except Exception as e:
        # The boundary of the run: the three summary lines for the error, then re-raised (trace, exit 1).
        log.say(a.cmd, f'run.py {" ".join(argv)}', f'error: {type(e).__name__}: {e}', 'fix the cause; nothing was released')
        raise


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
