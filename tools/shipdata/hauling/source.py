"""The source of the hauling data (S-H0, SD14): StarCitizenWiki/scunpacked-data - octfx/ScDataDumper's output of the game
files, the same extraction api.star-citizen.wiki publishes. One commit holds both inputs: contracts/<uuid>.json (5,166
files on 13 Nov 2026, all 1,843 hauling UUIDs of the wiki API) and starmap_positions.json.

A run asks GitHub for the commit of master (gh api, one call) and streams that commit's tarball (one GET, about 195 MB,
28 s locally): nothing is written to disk and nothing is cached (SD7). Kept are the contracts of the two naming schemes and
the starmap. The game build is in the commit message only ('4.10.3-LIVE.13165946'), not in the files."""
import json
import re
import tarfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from shipdata import github
from shipdata.hauling import templates

REPOSITORY = 'StarCitizenWiki/scunpacked-data'
BRANCH = 'master'
STARMAP = 'starmap_positions.json'
USER_AGENT = 'sc-cargoplan-shipdata (+https://github.com/MRiediger/sc-cargoplan-shipdata)'
BUILD = re.compile(r'\d+\.\d+\.\d+-[A-Z]+\.\d+')
SAVED_COMMIT, SAVED_TARBALL = 'commit.json', 'scunpacked.tar.gz'   # run.py hauling --saved <dir>: the same two answers


class SourceError(RuntimeError):
    """The source could not be read: the hauling job stops, the ship data go on (K2)."""


@dataclass
class Source:
    commit: str
    message: str
    game_build: str
    contracts: list[dict]
    starmap: dict
    contract_files: int
    requests: int


def game_build(message: str) -> str:
    """The build from the commit message's first line; the line itself when it names none (a hint, SD14)."""
    first = (message.splitlines() or [''])[0].strip()
    m = BUILD.search(first)
    return m[0] if m else first


def read(stream: BinaryIO) -> tuple[list[dict], dict, int]:
    """(hauling candidates, starmap, number of contract files) from a tarball stream ('r|gz': read once, front to back;
    Python docs, tarfile.open). The archive's top folder is <repo>-<sha>/."""
    contracts, starmap, files = [], None, 0
    with tarfile.open(fileobj=stream, mode='r|gz') as tf:
        for m in tf:
            parts = m.name.split('/')
            if not m.isfile() or len(parts) < 2:
                continue
            if len(parts) == 3 and parts[1] == 'contracts' and parts[2].endswith('.json'):
                files += 1
                data = tf.extractfile(m).read()
                if not any(p.encode() in data for p in templates.PREFIXES):    # cheap test before parsing
                    continue
                raw = json.loads(data.decode('utf-8-sig'))
                if templates.candidate(raw):
                    contracts.append(raw)
            elif len(parts) == 2 and parts[1] == STARMAP:
                starmap = json.loads(tf.extractfile(m).read().decode('utf-8-sig'))
    if starmap is None or not isinstance(starmap.get('entities'), list):
        raise SourceError(f'{STARMAP} missing or without entities in the tarball')
    if not files:
        raise SourceError('no contracts/*.json in the tarball')
    return contracts, starmap, files


def fetch(saved: Path | None = None) -> Source:
    try:
        if saved is not None:
            commit = json.loads((saved / SAVED_COMMIT).read_text(encoding='utf-8'))
            with (saved / SAVED_TARBALL).open('rb') as f:
                contracts, starmap, files = read(f)
            requests = 0
        else:
            commit = github.gh_json('api', f'repos/{REPOSITORY}/commits/{BRANCH}')
            url = f"https://codeload.github.com/{REPOSITORY}/tar.gz/{commit['sha']}"
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as r:
                contracts, starmap, files = read(r)
            requests = 2
        message = commit['commit']['message']
    except SourceError:
        raise
    except (OSError, urllib.error.URLError, tarfile.TarError, json.JSONDecodeError, KeyError, TypeError, RuntimeError) as e:
        raise SourceError(f'{REPOSITORY}: {type(e).__name__}: {e}') from e
    return Source(commit['sha'], message, game_build(message), contracts, starmap, files, requests)
