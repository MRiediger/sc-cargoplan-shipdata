"""The workflow's stages around the chain (T12.2, docs/plans/T12.2-workflow.md): the last release (previous), the draft
release that carries a run's assets until it is published (draft, SD10), publishing it (publish), the PR for Martin's
merge (pr) and the heartbeat commit (heartbeat, SD9). Pure functions first; gh and git only through shipdata.github.

Release names (SD4): ships-YYYY.MM, a second release in the same month ships-YYYY.MM.1, .2, ... Order is by version,
never by GitHub's latest flag (E1): the flag can be set by hand."""
import datetime as dt
import re

VERSION = re.compile(r'^ships-(?P<year>\d{4})\.(?P<month>\d{2})(?:\.(?P<n>\d+))?$')
KEEP = 2                    # published data releases that stay (SD4)


class WorkflowError(RuntimeError):
    pass


def version_key(tag: str) -> tuple[int, int, int]:
    """ships-2026.11 -> (2026, 11, 0), ships-2026.11.10 -> (2026, 11, 10): .10 sorts after .9."""
    m = VERSION.match(tag)
    if not m:
        raise WorkflowError(f'{tag!r} is not a data release name (ships-YYYY.MM[.N])')
    return int(m['year']), int(m['month']), int(m['n'] or 0)


def next_version(day: dt.date, tags: list[str]) -> str:
    """The release name for a run on `day`: ships-YYYY.MM, or the next free .N if that month has one already."""
    base = f'ships-{day:%Y.%m}'
    taken = [version_key(t)[2] for t in tags if t == base or t.startswith(base + '.') and VERSION.match(t)]
    return base if not taken else f'{base}.{max(taken) + 1}'


def published(releases: list[dict]) -> list[str]:
    """Tags of the published data releases (gh release list --json tagName,isDraft), oldest version first."""
    return sorted((r['tagName'] for r in releases if not r['isDraft'] and VERSION.match(r['tagName'])), key=version_key)


def pick_previous(releases: list[dict]) -> str:
    """The last release a run compares with: the highest published version (E1), not isLatest."""
    tags = published(releases)
    if not tags:
        raise WorkflowError('no data release yet: upload the seed first (run.py release --seed, draft, publish)')
    return tags[-1]


def to_delete(releases: list[dict], keep: int = KEEP) -> list[str]:
    """Hygiene after a publish (SD4): every published data release but the last `keep`; drafts and other tags stay."""
    tags = published(releases)
    return tags[:-keep] if len(tags) > keep else []


def stale_drafts(releases: list[dict]) -> list[str]:
    """Every data draft: a new run replaces the draft of an earlier one (its PR is superseded)."""
    return sorted(r['tagName'] for r in releases if r['isDraft'] and VERSION.match(r['tagName']))
