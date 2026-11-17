"""The hologram chain for one model, ported 1:1 from spike/chain.sh, which reproduced sc-ship-outlines' decimate.ps1
-Source Motherlode byte for byte (S12.0): flatten-model -> cull (MinPixels 2) -> simplify.mjs ref (200 k, error 0.0005 x
length) -> PP ladder 20k/30k/40k (error 0.005 x length) with export (SliverLimit 0.1563), stop at the first step without
fails -> PP.holo / PP.json -> outline. Numbers are passed as text exactly as chain.sh passed them (Python's str() of a
float), since the bytes of the hologram depend on them. Works in <holo work>/<className>/."""
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from shipdata.log import Reporter

TOOLS = Path(__file__).resolve().parents[1]
MESH = TOOLS / 'holo_mesh.py'
SIMPLIFY = TOOLS / 'simplify.mjs'
LADDER = (20000, 30000, 40000)
SLIVER_LIMIT = '0.1563'


@dataclass
class ChainResult:
    class_name: str
    seconds: dict[str, float] = field(default_factory=dict)
    budget: int = 0
    pp: dict = field(default_factory=dict)


def _step(name: str, args: list[str], work: Path, env: dict[str, str], result: ChainResult) -> str:
    t = time.perf_counter()
    p = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
    result.seconds[name] = round(time.perf_counter() - t, 1)
    (work / f'{name}.out').write_text(p.stdout, encoding='utf-8', newline='\n')
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, args, p.stdout, p.stderr)
    return p.stdout


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def build_model(class_name: str, glb: Path, holo_work: Path) -> ChainResult:
    w = holo_work / class_name
    if w.exists():
        shutil.rmtree(w)                     # a rebuild starts clean: no step reads an older run's intermediates
    w.mkdir(parents=True)
    env = dict(os.environ, HOLO_WORK=str(holo_work))
    py = [sys.executable, '-I', str(MESH)]
    r = ChainResult(class_name)
    _step('flatten', py + ['flatten-model', class_name, str(glb)], w, env, r)
    length = _json(w / 'flat.json')['lengthM']
    _step('cull', py + ['cull', class_name, '2'], w, env, r)
    _step('ref', ['node', str(SIMPLIFY), str(w / 'shell.bin'), str(w / 'ref.idx'), '200000', str(0.0005 * length), 'ref'], w, env, r)
    final = 0
    for b in LADDER:
        out = _step(f'simplify-{b}', ['node', str(SIMPLIFY), str(w / 'shell.bin'), str(w / f'PP-{b}.idx'), str(b),
                                      str(0.005 * length), 'PP'], w, env, r)
        (w / f'PP-{b}.simplify.json').write_text(out, encoding='utf-8', newline='\n')
        s = json.loads(out)
        _step(f'export-{b}', py + ['export', class_name, f'PP-{b}', str(b), str(s['errorM']), 'true' if s['sloppy'] else 'false',
                                   str(s['ms']), SLIVER_LIMIT], w, env, r)
        final = b
        if len(_json(w / f'PP-{b}.json').get('fails', [])) == 0:
            break
    shutil.copyfile(w / f'PP-{final}.holo', w / 'PP.holo')
    pp = _json(w / f'PP-{final}.json')
    pp['passed'] = len(pp['fails']) == 0
    pp['budget'] = final
    (w / 'PP.json').write_text(json.dumps(pp, separators=(',', ':')), encoding='utf-8', newline='\n')
    _step('outline', py + ['outline', class_name], w, env, r)
    r.budget, r.pp = final, pp
    return r


def report(log: Reporter, r: ChainResult) -> None:
    for step, s in r.seconds.items():
        log.num(f'build.{r.class_name}.{step}.s', s)
    log.line(f"{r.class_name}: budget {r.budget}, {r.pp['triangles']} triangles, passed {r.pp['passed']}, "
             f"{sum(r.seconds.values()):.1f} s")
