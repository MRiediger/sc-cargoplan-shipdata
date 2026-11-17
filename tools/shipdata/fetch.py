"""fetch: the cargo grid catalog of Motherlode (cryon.rocks) and the ship models, ported from sc-ship-outlines'
fetch-motherlode.ps1 (catalog) and spike/probe.py (models by hash).

Sources (unchanged since SC-CargoPlan session 4b):
  grids   GET https://cryon.rocks/api/public/v1/cargo-grids, header "Authorization: Bearer <key>" - exactly one request per
          run; a 429 stops the run with its Retry-After, nothing is asked again (CLAUDE.md: never in a loop).
  models  the page https://cryon.rocks/ops/cargo (header "RSC: 1"; its React Server Component stream holds a "ships" array)
          for modelUrl only, joined by className, the file name before "-<hash>.glb". The hash is the first 12 hex digits of
          the model's SHA-256, so a model is checked against its own URL.
The key comes from MOTHERLODE_API_KEY only and is never logged. Models land in cache/models/<file> and are never deleted
here: older hashes go after a published release (condition B, release.py)."""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

API_URL = 'https://cryon.rocks/api/public/v1/cargo-grids'
PAGE_URL = 'https://cryon.rocks/ops/cargo'
USER_AGENT = 'sc-cargoplan-outlines/0.2 (fan project)'          # 1:1 as fetch-motherlode.ps1
BUILD_PATTERN = re.compile(r'^\d+\.\d+(\.\d+)?-[A-Z]+\.\d+$')
MODEL_NAME = re.compile(r'^(?P<cls>.+)-(?P<hash>[0-9a-f]{12})\.glb$')


class SourceError(RuntimeError):
    """Motherlode's answer is not usable: missing key, HTTP error, format changed. Nothing is written after it."""


def api_key() -> str:
    key = os.environ.get('MOTHERLODE_API_KEY', '').strip()
    if not key:
        raise SourceError('no API key: MOTHERLODE_API_KEY is not set (a repository secret on the runner)')
    return key


def _get(url: str, headers: dict[str, str], timeout: int = 60) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers=dict(headers, **{'User-Agent': USER_AGENT}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, b'', dict(e.headers)


def fetch_api() -> bytes:
    """The one API request. Messages are written here, never taken from the request: they must not carry the header."""
    status, body, headers = _get(API_URL, {'Authorization': f'Bearer {api_key()}'})
    if status == 429:
        raise SourceError(f'API: 429 Too Many Requests, Retry-After {headers.get("Retry-After", "?")}; one request per run')
    if status != 200:
        raise SourceError(f'API answered HTTP {status}')
    return body


def fetch_page() -> str:
    status, body, _ = _get(PAGE_URL, {'RSC': '1'})
    if status != 200:
        raise SourceError(f'cargo page answered HTTP {status}: model URLs unavailable')
    return body.decode('utf-8')


def ships_array_text(text: str) -> str:
    """The page's "ships" array as text: brackets counted, strings skipped, since names could hold brackets."""
    marker = '"ships":['
    start = text.find(marker)
    if start < 0:
        raise SourceError(f'no {marker} in the page answer - page format changed?')
    start += len(marker) - 1
    depth, in_string, escape = 0, False, False
    for k in range(start, len(text)):
        c = text[k]
        if in_string:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return text[start:k + 1]
    raise SourceError("the page's ships array has no end - answer cut off?")


def class_name(model_url: str) -> str:
    return re.sub(r'-[0-9a-f]+\.glb$', '', model_url.rsplit('/', 1)[-1])


def check_api(api: dict) -> None:
    """The API answer against the catalog format; anything out of it stops the run before anything is written."""
    if not (isinstance(api.get('gameBuild'), str) and BUILD_PATTERN.match(api['gameBuild'])):
        raise SourceError('API answer: gameBuild missing or not like 4.10.2-LIVE.12913470')
    if not api.get('updatedAt'):
        raise SourceError('API answer: updatedAt missing')
    if not api.get('ships'):
        raise SourceError('API answer: no ships')
    for s in api['ships']:
        if not s.get('name'):
            raise SourceError('API answer: a ship without name')
        if not isinstance(s.get('grids'), list):
            raise SourceError(f"API answer: {s['name']} has no grids list")
        for g in s['grids']:
            if len(g.get('size') or []) != 3:
                raise SourceError(f"API answer: {s['name']}/{g.get('name')}: size has not 3 values")
            if g.get('transform') is not None and len(g['transform']) != 12:
                raise SourceError(f"API answer: {s['name']}/{g.get('name')}: transform has not 12 values")


def join(api: dict, page_ships: list) -> tuple[dict, list[str]]:
    """The catalog: the API's ships as they come, modelUrl joined by className. Returns it and the notes for the log."""
    check_api(api)
    models = {class_name(p['modelUrl']): p['modelUrl'] for p in page_ships if p.get('modelUrl')}
    notes, joined, ships = [], set(), []
    for s in api['ships']:
        ship = {k: v for k, v in s.items() if k != 'modelUrl'}
        cls = s.get('className')
        if cls and cls in models:
            ship['modelUrl'] = models[cls]
            joined.add(cls)
        elif cls:
            notes.append(f"no model on the page for {cls} ({s['name']})")
        ships.append(ship)
    notes += [f'model on the page without an API ship: {c}' for c in sorted(set(models) - joined)]
    return {'gameBuild': api['gameBuild'], 'updatedAt': api['updatedAt'], 'ships': ships}, notes


def load_saved(folder: Path) -> tuple[dict, list]:
    """Saved answers: api.json, and the page as page.txt (the RSC stream, as the runner saw it) or page-ships.json (only
    the ships array, as sc-ship-outlines archived it)."""
    api = json.loads((folder / 'api.json').read_text(encoding='utf-8-sig'))
    if (folder / 'page.txt').exists():
        page = ships_array_text((folder / 'page.txt').read_text(encoding='utf-8'))
    else:
        page = (folder / 'page-ships.json').read_text(encoding='utf-8')
    return api, json.loads(page)


def model_files(catalog: dict) -> dict[str, str]:
    """className -> model file name, for every ship with a model URL."""
    return {s['className']: s['modelUrl'].rsplit('/', 1)[-1] for s in catalog['ships'] if s.get('className') and s.get('modelUrl')}


def get_model(url: str) -> tuple[int, bytes]:
    try:
        status, body, _ = _get(url, {}, timeout=120)
    except (urllib.error.URLError, TimeoutError) as e:          # network: no status, the model counts as unavailable
        print(f'  model GET failed: {url.rsplit("/", 1)[-1]}: {type(e).__name__}: {e}', flush=True)
        return 0, b''
    return status, body


def fetch_models(catalog: dict, models_dir: Path, get: Callable[[str], tuple[int, bytes]] = get_model,
                 pause: float = 0.2) -> dict[str, dict]:
    """Every model not in the cache yet: one GET each, `pause` seconds apart, no retry. A model that does not answer 200 or
    whose bytes do not match the hash in its name is 'unavailable' (condition A): its ship keeps its last hologram and
    outline, the others still load. Returns className -> {file, status, http, sha256}."""
    models_dir.mkdir(parents=True, exist_ok=True)
    urls = {s['className']: s['modelUrl'] for s in catalog['ships'] if s.get('className') and s.get('modelUrl')}
    out: dict[str, dict] = {}
    for cls in sorted(urls):
        url = urls[cls]
        name = url.rsplit('/', 1)[-1]
        m = MODEL_NAME.match(name)
        path = models_dir / name
        if path.exists():
            out[cls] = {'file': name, 'status': 'cached', 'http': None, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            continue
        status, body = get(url)
        sha = hashlib.sha256(body).hexdigest()
        if status != 200 or not m or not sha.startswith(m['hash']):
            reason = f'HTTP {status}' if status != 200 else 'bytes do not match the hash in the file name'
            out[cls] = {'file': name, 'status': 'unavailable', 'http': status, 'sha256': None, 'reason': reason}
        else:
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(body)
            os.replace(tmp, path)
            out[cls] = {'file': name, 'status': 'fetched', 'http': status, 'sha256': sha}
        if pause:
            time.sleep(pause)
    return out


def prune_models(models_dir: Path, keep: set[str]) -> list[str]:
    """After a published release (condition B): every older hash of a className that has a file in `keep` goes; models of
    other classes (ships gone from the catalog) stay for a rollback. Returns the removed file names."""
    current = {MODEL_NAME.match(n)['cls'] for n in keep if MODEL_NAME.match(n)}
    removed = []
    for p in sorted(models_dir.glob('*.glb')):
        m = MODEL_NAME.match(p.name)
        if m and m['cls'] in current and p.name not in keep:
            p.unlink()
            removed.append(p.name)
    return removed
