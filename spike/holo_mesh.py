"""holo_mesh.py - holo meshes for SC-CargoPlan (T7.4c-1). numpy + cv2, see TOOLS.md.

Steps per ship (driven by decimate.ps1, files in holo-work/<slug>/):
  flatten <slug>          plain.glb -> flat.npz: node transforms, glTF axes -> ship axes (x bow+, y port+, z up+, metres,
                          origin = centre of the x/y box, z = 0 at the keel), scaled to lengthM, welded with tolerance
  cull <slug>             flat.npz -> shell.npz + shell.bin: drops triangles never seen from outside
  (node simplify.mjs)     shell.bin -> <method>.idx
  export <slug> <method>  shell.npz + <method>.idx -> <method>.holo (SCH2, docs/holo-format.md in sc-cargoplan) + metrics
  sheet <method> <out>    contact sheets of every exported ship, worst first
  release <dir> ...       release folder: <slug>.holo, NOTICE.md, manifest.json
  verify <dir>            every file against the format and the manifest

Motherlode models (SC-CargoPlan session 4b, D93), files in $HOLO_WORK/<className>/ (decimate.ps1 -Source Motherlode):
  flatten-model <key> <glb>    the game model -> flat.npz + flat.json: only turned into ship axes, origin and size kept
  outline <key> <out.json>     top-view silhouette of flat.npz in metres, origin = the model's
  probe <key> <ship.json> <out.png>   top, side and front view with the ship file's racks moved by its fraction s
"""
import hashlib, json, math, os, struct, sys
from collections import namedtuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# The Motherlode run works in a folder of its own (holo-work-ml), so holo-v1's intermediates stay as they are.
WORK = os.environ.get('HOLO_WORK') or os.path.join(HERE, 'holo-work')
OUT = os.path.join(HERE, 'holo')

FORMAT_VERSION = 2
HEADER = struct.Struct('<4sHHI5I7f')        # magic, version, headerBytes, flags, 5 counts, lengthM, bounds
MAGIC = b'SCH2'

WELD_MIN_M, WELD_MAX_M = 0.001, 0.01        # weld tolerance bounds; between them 0.6 x the Draco step
STEP_MIN_VERTICES = 1000                    # a primitive this small says nothing about the quantization step
CREASE_DEG = 30.0                           # feature edge candidate
TURN_DEG = 40.0                             # chains continue through a vertex when the turn is this small
LEVEL_SHARES = (0.30, 0.60)                 # levels 1 and 2 by share of the total edge score
LEVEL1_MAX, LEVEL3_MAX = 3000, 15000        # absolute caps on edges
CULL_VIEWS, CULL_PIXELS = 100, 1024
CULL_MIN_PIXELS = 2                         # calibrated on Hull A and Hull D, see TASKS.md T7.4c-1

Mesh = namedtuple('Mesh', 'vertices triangles normals max_step steps')


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def load_json(path):
    # utf-8-sig: Windows PowerShell 5.1 writes JSON with a BOM
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def atomic(path, write):
    """Writes through path + '.tmp' and renames, so a stopped run leaves no half file behind."""
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        write(f)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------------------------------------- glTF

def read_glb(path):
    b = read_bytes(path)
    if b[:4] != b'glTF':
        raise ValueError(f'{path}: not a GLB')
    off, js, binc = 12, None, b''
    while off < len(b):
        ln, typ = struct.unpack_from('<II', b, off)
        chunk = b[off + 8: off + 8 + ln]
        if typ == 0x4E4F534A: js = json.loads(chunk)
        elif typ == 0x004E4942: binc = chunk
        off += 8 + ln
    return js, binc


def node_matrix(n):
    if 'matrix' in n:
        return np.array(n['matrix'], dtype=np.float64).reshape(4, 4).T   # column-major
    tx, ty, tz = n.get('translation', [0, 0, 0])
    qx, qy, qz, qw = n.get('rotation', [0, 0, 0, 1])
    sx, sy, sz = n.get('scale', [1, 1, 1])
    r = np.array([[1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
                  [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
                  [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]])
    m = np.eye(4)
    m[:3, :3] = r * np.array([sx, sy, sz])
    m[:3, 3] = [tx, ty, tz]
    return m


DTYPE = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
NORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


def accessor(js, binc, i):
    a = js['accessors'][i]
    if 'sparse' in a:
        raise ValueError('sparse accessors are not supported')
    bv = js['bufferViews'][a['bufferView']]
    dt = np.dtype(DTYPE[a['componentType']])
    n = NCOMP[a['type']]
    stride = bv.get('byteStride') or dt.itemsize * n
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    arr = np.ndarray((a['count'], n), dtype=dt, buffer=binc, offset=base, strides=(stride, dt.itemsize))
    out = arr.astype(np.float64 if dt.kind == 'f' or a.get('normalized') else np.int64)
    if a.get('normalized'):
        out = np.maximum(out / NORM[a['componentType']], -1.0)
    return out[:, 0] if n == 1 else out


def scene_mesh(js, binc):
    """World-space vertices, triangles and normals of every TRIANGLES primitive in the default scene, plus the
    quantization step per primitive (smallest non-zero coordinate difference, in world units)."""
    verts, tris, norms, steps = [], [], [], []
    have_normals = True

    def walk(ni, parent):
        nonlocal have_normals
        n = js['nodes'][ni]
        m = parent @ node_matrix(n)
        if 'mesh' in n:
            lin = m[:3, :3]
            flip = np.linalg.det(lin) < 0
            for p in js['meshes'][n['mesh']]['primitives']:
                if p.get('mode', 4) != 4: continue
                local = accessor(js, binc, p['attributes']['POSITION'])
                base = sum(len(v) for v in verts)
                verts.append(local @ lin.T + m[:3, 3])
                if 'NORMAL' in p['attributes']:
                    nr = accessor(js, binc, p['attributes']['NORMAL']) @ np.linalg.inv(lin)   # inverse transpose
                    norms.append(nr / np.maximum(np.linalg.norm(nr, axis=1, keepdims=True), 1e-12))
                else:
                    have_normals = False
                idx = accessor(js, binc, p['indices']) if 'indices' in p else np.arange(len(local))
                t = idx[: len(idx) // 3 * 3].reshape(-1, 3) + base
                tris.append(t[:, [0, 2, 1]] if flip else t)
                diffs = []
                for k in range(3):
                    u = np.unique(local[:, k])
                    d = np.diff(u)
                    d = d[d > 0]
                    if len(d): diffs.append(d.min())
                if diffs:
                    steps.append((min(diffs) * np.linalg.norm(lin, axis=0).max(), len(local)))
        for c in n.get('children', []):
            walk(c, m)

    for root in js['scenes'][js.get('scene', 0)]['nodes']:
        walk(root, np.eye(4))
    v = np.vstack(verts)
    t = np.vstack(tris).astype(np.int64)
    nr = np.vstack(norms) if have_normals and norms else None
    return Mesh(v, t, nr, max((s for s, _ in steps), default=0.0), steps)


# ---------------------------------------------------------------------------------------------------------- weld

def weld(v, tol):
    """Merges vertices closer than tol on every axis: snap to a grid of 2 tol, then again to the same grid shifted by
    tol, so pairs on either side of a cell boundary meet in the second pass. Representatives are the first vertex of
    their group. Returns (unique vertices, remap from old to new index)."""
    cell = 2 * tol
    _, first, inv = np.unique(np.floor(v / cell).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    order = np.argsort(first)                       # keep representatives in input order (deterministic)
    rank = np.empty_like(order); rank[order] = np.arange(len(order))
    rep = v[np.sort(first)]
    remap1 = rank[inv.ravel()]
    _, first2, inv2 = np.unique(np.floor(rep / cell + 0.5).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    order2 = np.argsort(first2)
    rank2 = np.empty_like(order2); rank2[order2] = np.arange(len(order2))
    remap = rank2[inv2.ravel()][remap1]
    return rep[np.sort(first2)], remap


def clean_triangles(t):
    """Drops degenerate triangles and duplicates of the same three vertices (either winding); keeps the first."""
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    _, first = np.unique(np.sort(t, axis=1), axis=0, return_index=True)
    return t[np.sort(first)]


def compact(v, t, *extra):
    used, inv = np.unique(t.ravel(), return_inverse=True)
    return (v[used], inv.reshape(t.shape)) + tuple(e[used] if e is not None else None for e in extra)


# ---------------------------------------------------------------------------------------------------------- topology

def edge_table(t):
    """Undirected edges (E, 2, smaller index first), the edge of every half-edge (3 per triangle, in order 01 12 20),
    faces per edge, and the directed half-edges."""
    half = t[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    n = int(t.max()) + 1 if len(t) else 1
    key = np.minimum(half[:, 0], half[:, 1]) * n + np.maximum(half[:, 0], half[:, 1])
    uniq, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
    return np.stack([uniq // n, uniq % n], axis=1), inv, counts, half


def winding_conflicts(t):
    """Manifold edges (two triangles) that both triangles run the same way: zero on a consistently wound mesh.
    An edge of three or more triangles can't be consistent and doesn't count."""
    _, inv, counts, half = edge_table(t)
    two = np.nonzero(counts[inv] == 2)[0]
    pairs = two[np.argsort(inv[two], kind='stable')].reshape(-1, 2)
    return int((half[pairs[:, 0], 0] == half[pairs[:, 1], 0]).sum())


def face_normals(v, t):
    c = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    area2 = np.linalg.norm(c, axis=1)
    return c / np.maximum(area2, 1e-30)[:, None], area2 / 2


def components(t):
    """Connected components of triangles over shared vertices (union-find on vertices)."""
    parent = np.arange(int(t.max()) + 1)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c in t.tolist():
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    roots = np.array([find(a) for a in t[:, 0].tolist()])
    return np.unique(roots, return_inverse=True)[1]


def orient(v, t, normals):
    """Consistent winding per component (breadth-first over manifold edges), then outward: by the source normals
    where they exist, else by the signed volume of the component."""
    t = t.copy()
    edges, inv, counts, half = edge_table(t)
    face_of_half = np.repeat(np.arange(len(t)), 3)
    by_edge = {}
    for h in np.nonzero(counts[inv] == 2)[0].tolist():
        by_edge.setdefault(int(inv[h]), []).append(h)
    nbr = [[] for _ in range(len(t))]
    for a, b in by_edge.values():
        fa, fb = face_of_half[a], face_of_half[b]
        same = half[a, 0] == half[b, 0]                 # same direction: one of them must flip
        nbr[fa].append((fb, same)); nbr[fb].append((fa, same))
    flip = np.zeros(len(t), dtype=bool)
    seen = np.zeros(len(t), dtype=bool)
    comp = np.full(len(t), -1)
    ncomp = 0
    for start in range(len(t)):
        if seen[start]: continue
        stack = [start]; seen[start] = True; comp[start] = ncomp
        while stack:
            f = stack.pop()
            for g, same in nbr[f]:
                if not seen[g]:
                    seen[g] = True; comp[g] = ncomp
                    flip[g] = flip[f] ^ bool(same)
                    stack.append(g)
        ncomp += 1
    t[flip] = t[flip][:, ::-1]
    fn, area = face_normals(v, t)
    if normals is not None:
        src = normals[t].sum(axis=1)
        vote = np.bincount(comp, weights=area * np.einsum('ij,ij->i', fn, src), minlength=ncomp)
    else:
        vote = np.zeros(ncomp)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    centre = v[t].mean(axis=(0, 1))
    vol = np.einsum('ij,ij->i', a - centre, np.cross(b - centre, c - centre))
    volume = np.bincount(comp, weights=vol, minlength=ncomp)
    turn = np.where(np.abs(vote) > 1e-12, vote < 0, volume < 0)
    t[turn[comp]] = t[turn[comp]][:, ::-1]
    return t


# ---------------------------------------------------------------------------------------------------------- edges

def edge_angles(v, t):
    """Undirected edges, triangles per edge and the angle between the normals of a manifold edge's two triangles,
    measured along the winding (a flipped neighbour is turned back first); open and non-manifold edges get pi/2."""
    edges, inv, counts, half = edge_table(t)
    fn, _ = face_normals(v, t)
    face_of_half = np.repeat(np.arange(len(t)), 3)
    angle = np.full(len(edges), math.pi / 2)
    two = np.nonzero(counts[inv] == 2)[0]
    pairs = two[np.argsort(inv[two], kind='stable')].reshape(-1, 2)
    ha, hb = pairs[:, 0], pairs[:, 1]
    n1, n2 = fn[face_of_half[ha]], fn[face_of_half[hb]]
    n2 = np.where((half[ha, 0] == half[hb, 0])[:, None], -n2, n2)
    angle[inv[ha]] = np.arccos(np.clip(np.einsum('ij,ij->i', n1, n2), -1, 1))
    return edges, counts, angle


def feature_edges(v, t, length_m, boundary=True):
    """Feature edges ordered by level: candidates are creases >= CREASE_DEG (measured along the winding, so a flipped
    neighbour is no crease), non-manifold edges and, with boundary, open edges. Candidates link into chains through
    a vertex when the turn is <= TURN_DEG (straightest pairs first). Chain score = sum of length x (1 - cos angle).
    Level 1 = best chains up to LEVEL_SHARES[0] of the total score, level 2 up to LEVEL_SHARES[1], level 3 all; caps
    LEVEL1_MAX and LEVEL3_MAX cut at chain boundaries. Returns (edges, level1Count, level2Count)."""
    edges, counts, angle = edge_angles(v, t)
    cand = (counts > 2) | ((counts == 2) & (angle >= math.radians(CREASE_DEG)))
    if boundary:
        cand |= counts == 1
    ids = np.nonzero(cand)[0]
    if len(ids) == 0:
        return np.zeros((0, 2), dtype=np.int64), 0, 0
    e = edges[ids]
    vec = v[e[:, 1]] - v[e[:, 0]]
    length = np.linalg.norm(vec, axis=1)
    score_e = length * (1 - np.cos(angle[ids]))
    # chains: union-find over candidate edges
    parent = list(range(len(ids)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    at = {}
    for k, (a, b) in enumerate(e.tolist()):
        at.setdefault(a, []).append(k); at.setdefault(b, []).append(k)
    cos_turn = math.cos(math.radians(TURN_DEG))
    for vert, ks in at.items():
        if len(ks) < 2: continue
        dirs = []
        for k in ks:
            other = e[k, 1] if e[k, 0] == vert else e[k, 0]
            d = v[other] - v[vert]
            dirs.append(d / max(np.linalg.norm(d), 1e-30))
        cand_pairs = []
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                straight = -float(np.dot(dirs[i], dirs[j]))     # 1 = straight on
                if straight >= cos_turn:
                    cand_pairs.append((-straight, ks[i], ks[j]))
        used = set()
        for _, ki, kj in sorted(cand_pairs):
            if ki in used or kj in used: continue
            used.add(ki); used.add(kj)
            parent[find(ki)] = find(kj)
    root = np.array([find(k) for k in range(len(ids))])
    _, chain = np.unique(root, return_inverse=True)
    chain_score = np.bincount(chain, weights=score_e)
    chain_size = np.bincount(chain)
    chain_first = np.full(len(chain_score), len(ids))
    np.minimum.at(chain_first, chain, np.arange(len(ids)))
    rank = np.lexsort((chain_first, -chain_score))          # best first, ties by first edge
    total = chain_score.sum()
    counts_lvl, cum, n_edges = [0, 0], 0.0, 0
    kept = []
    for c in rank.tolist():
        if n_edges + chain_size[c] > LEVEL3_MAX: break
        for lvl, share in enumerate(LEVEL_SHARES):
            if cum < share * total and not (lvl == 0 and n_edges + chain_size[c] > LEVEL1_MAX and n_edges > 0):
                counts_lvl[lvl] = n_edges + chain_size[c]
        cum += chain_score[c]
        n_edges += chain_size[c]
        kept.append(c)
    counts_lvl[1] = max(counts_lvl[1], counts_lvl[0])
    pos = {c: i for i, c in enumerate(kept)}
    sel = np.array([k for k in range(len(ids)) if chain[k] in pos], dtype=np.int64)
    sel = sel[np.lexsort((sel, np.array([pos[chain[k]] for k in sel])))]
    return e[sel], counts_lvl[0], counts_lvl[1]


# ---------------------------------------------------------------------------------------------------------- SCH2

def write_sch2(path, v, t, e, l1, l2, length_m):
    v = np.asarray(v, dtype='<f4'); t = np.asarray(t); e = np.asarray(e).reshape(-1, 2)
    if not 0 <= l1 <= l2 <= len(e):
        raise ValueError(f'levels must be prefixes: {l1} <= {l2} <= {len(e)}')
    idx = '<u2' if len(v) < 65536 else '<u4'
    lo, hi = (v.min(axis=0), v.max(axis=0)) if len(v) else (np.zeros(3), np.zeros(3))
    head = HEADER.pack(MAGIC, FORMAT_VERSION, HEADER.size, 0, len(v), len(t), len(e), l1, l2, float(length_m),
                       *lo.tolist(), *hi.tolist())
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(head + v.tobytes() + t.astype(idx).tobytes() + e.astype(idx).tobytes())
    os.replace(tmp, path)


def read_sch2(path):
    b = read_bytes(path)
    if len(b) < HEADER.size:
        raise ValueError(f'{path}: shorter than the header')
    magic, ver, hb, flags, vc, tc, ec, l1, l2, length, *box = HEADER.unpack_from(b)
    if magic != MAGIC or ver != FORMAT_VERSION:
        raise ValueError(f'{path}: not SCH2 version {FORMAT_VERSION}')
    ib = 2 if vc < 65536 else 4
    if len(b) != hb + 12 * vc + ib * (3 * tc + 2 * ec):
        raise ValueError(f'{path}: {len(b)} bytes, expected {hb + 12 * vc + ib * (3 * tc + 2 * ec)}')
    if not l1 <= l2 <= ec:
        raise ValueError(f'{path}: levels {l1}/{l2}/{ec} are not prefixes')
    dt = '<u2' if ib == 2 else '<u4'
    o = hb
    verts = np.frombuffer(b, '<f4', 3 * vc, o).reshape(-1, 3); o += 12 * vc
    tris = np.frombuffer(b, dt, 3 * tc, o).reshape(-1, 3).astype(np.int64); o += ib * 3 * tc
    edges = np.frombuffer(b, dt, 2 * ec, o).reshape(-1, 2).astype(np.int64)
    if vc and (tris.max(initial=0) >= vc or edges.max(initial=0) >= vc):
        raise ValueError(f'{path}: index out of range')
    return {'formatVersion': ver, 'headerBytes': hb, 'flags': flags, 'vertices': verts, 'triangles': tris,
            'edges': edges, 'level1Count': l1, 'level2Count': l2, 'lengthM': length, 'bounds': list(box),
            'indexBytes': ib}


# ---------------------------------------------------------------------------------------------------------- splats

def sample_surface(v, t, spacing):
    """Points on every triangle no further apart than spacing, and the triangle of each point. Rows parallel to the
    longest edge, rows and points in a row at most spacing apart, so a sliver gets points by its area, not by its
    length. A triangle whose longest edge is under spacing gets its centroid only."""
    tri = v[t].astype(np.float64)                                   # (M, 3, 3)
    elen = np.linalg.norm(tri[:, [1, 2, 0]] - tri, axis=2)          # edge k runs from corner k to k + 1
    k = elen.argmax(axis=1)
    rows = np.arange(len(t))
    A, B, C = tri[rows, k], tri[rows, (k + 1) % 3], tri[rows, (k + 2) % 3]
    base = elen[rows, k]
    small = base <= spacing
    area2 = np.linalg.norm(np.cross(B - A, C - A), axis=1)
    height = np.where(base > 0, area2 / np.maximum(base, 1e-30), 0)
    pts, ids = [((A[small] + B[small] + C[small]) / 3).astype(np.float32)], [np.nonzero(small)[0].astype(np.int32)]
    big = np.nonzero(~small)[0]
    for s in range(0, len(big), 200_000):
        q = big[s: s + 200_000]
        kr = np.maximum(1, np.ceil(height[q] / spacing)).astype(np.int64)            # row intervals
        row_tri = np.repeat(np.arange(len(q)), kr + 1)
        r = np.arange(len(row_tri)) - np.repeat(np.cumsum(kr + 1) - (kr + 1), kr + 1)
        f = r / kr[row_tri]
        p0 = A[q][row_tri] + (C[q][row_tri] - A[q][row_tri]) * f[:, None]
        p1 = B[q][row_tri] + (C[q][row_tri] - B[q][row_tri]) * f[:, None]
        m = np.maximum(1, np.ceil((1 - f) * base[q][row_tri] / spacing)).astype(np.int64)   # points per row - 1
        pt_row = np.repeat(np.arange(len(row_tri)), m + 1)
        j = np.arange(len(pt_row)) - np.repeat(np.cumsum(m + 1) - (m + 1), m + 1)
        g = (j / m[pt_row])[:, None]
        pts.append((p0[pt_row] + (p1[pt_row] - p0[pt_row]) * g).astype(np.float32))
        ids.append(q[row_tri[pt_row]].astype(np.int32))
    return np.vstack(pts), np.concatenate(ids)


def fibonacci_sphere(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    theta = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)], axis=1)


def basis(d):
    d = d / np.linalg.norm(d)
    up = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    r = np.cross(d, up); r /= np.linalg.norm(r)
    return r, np.cross(d, r), d


def visible_triangles(v, t, views=CULL_VIEWS, pixels=CULL_PIXELS, min_pixels=CULL_MIN_PIXELS):
    """Triangles seen from outside: kept when nearest in at least min_pixels pixels over all views (seen_pixels)."""
    return seen_pixels(v, t, views, pixels) >= min_pixels


def seen_pixels(v, t, views=CULL_VIEWS, pixels=CULL_PIXELS):
    """Pixels per triangle where it is nearest, summed over orthographic views from directions on a sphere; depth
    buffer from surface samples no further apart than half a pixel, a sample counts within 1.5 pixels of the nearest
    depth."""
    diag = float(np.linalg.norm(v.max(axis=0) - v.min(axis=0)))
    pix = diag / pixels
    pts, ids = sample_surface(v, t, pix / 2)
    seen = np.zeros(len(t), dtype=np.int64)
    eps = 1.5 * pix
    for d in fibonacci_sphere(views):
        r, s, d = basis(d)
        u = pts @ r.astype(np.float32); w = pts @ s.astype(np.float32); z = pts @ d.astype(np.float32)
        ui = ((u - u.min()) / pix).astype(np.int64); wi = ((w - w.min()) / pix).astype(np.int64)
        width = int(ui.max()) + 1
        cell = wi * width + ui
        zbuf = np.full(int(cell.max()) + 1, np.inf, dtype=np.float32)
        np.minimum.at(zbuf, cell, z)
        hit = z <= zbuf[cell] + eps
        pairs = np.unique(ids[hit].astype(np.int64) * len(zbuf) + cell[hit])
        seen += np.bincount(pairs // len(zbuf), minlength=len(t))
    return seen


# ---------------------------------------------------------------------------------------------------------- renders

class Camera:
    """Orthographic camera over a set of points: right/down/depth basis, pixel size, image size."""

    def __init__(self, pts, right, down, depth, long_px, margin=0.03):
        self.r, self.s, self.d = (np.asarray(x, dtype=np.float64) for x in (right, down, depth))
        u, w = pts @ self.r, pts @ self.s
        span = max(u.max() - u.min(), w.max() - w.min())
        self.pix = span * (1 + 2 * margin) / long_px
        self.u0 = u.min() - margin * span; self.w0 = w.min() - margin * span
        self.W = int((u.max() - self.u0) / self.pix + margin * span / self.pix) + 1
        self.H = int((w.max() - self.w0) / self.pix + margin * span / self.pix) + 1

    def project(self, p):
        return (((p @ self.r) - self.u0) / self.pix).astype(np.int64), (((p @ self.s) - self.w0) / self.pix).astype(np.int64), p @ self.d

    def depth(self, v, t):
        return self.depth_of(sample_surface(v, t, self.pix / 2)[0])

    def depth_of(self, pts):
        """Depth buffer from surface samples no further apart than half a pixel of this camera."""
        x, y, z = self.project(pts.astype(np.float64))
        ok = (x >= 0) & (x < self.W) & (y >= 0) & (y < self.H)
        zbuf = np.full(self.W * self.H, np.inf)
        np.minimum.at(zbuf, y[ok] * self.W + x[ok], z[ok])
        return zbuf.reshape(self.H, self.W)


def view(name, yaw=45.0, pitch=math.degrees(math.atan(1 / math.sqrt(2)))):
    if name == 'top': return (-1, 0, 0), (0, 1, 0), (0, 0, -1)
    if name == 'side': return (-1, 0, 0), (0, 0, -1), (0, -1, 0)
    if name == 'front': return (0, -1, 0), (0, 0, -1), (-1, 0, 0)
    th, ph = math.radians(yaw), math.radians(pitch)             # as IsoProjection in the app
    return ((-math.sin(th), math.cos(th), 0), (math.cos(th) * math.sin(ph), math.sin(th) * math.sin(ph), -math.cos(ph)),
            (-math.cos(ph) * math.cos(th), -math.cos(ph) * math.sin(th), -math.sin(ph)))


def silhouette_edges(v, t, d):
    """Contours of smooth surfaces seen along d: manifold edges under CREASE_DEG between a front and a back face.
    Creases are feature edges and come with their level, so they don't return here (else every bevel of a panel
    would be drawn at every level)."""
    edges, inv, counts, _ = edge_table(t)
    _, _, angle = edge_angles(v, t)
    fn, _ = face_normals(v, t)
    front = fn @ np.asarray(d) < 0
    face_of_half = np.repeat(np.arange(len(t)), 3)
    nf = np.bincount(inv, weights=front[face_of_half], minlength=len(edges))
    return edges[(counts == 2) & (nf == 1) & (angle < math.radians(CREASE_DEG))]


def edge_mask(cam, v, zbuf, e):
    """Visible pixels of edges against a depth buffer (samples every half pixel, 2 pixels of depth tolerance)."""
    m = np.zeros((cam.H, cam.W), dtype=np.uint8)
    if len(e) == 0: return m
    a, b = v[e[:, 0]], v[e[:, 1]]
    n = np.maximum(2, np.ceil(np.linalg.norm(b - a, axis=1) / (cam.pix / 2)).astype(np.int64))
    k = np.repeat(np.arange(len(e)), n)
    f = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n - 1, n)
    p = a[k] + (b[k] - a[k]) * f[:, None]
    x, y, z = cam.project(p)
    ok = (x >= 0) & (x < cam.W) & (y >= 0) & (y < cam.H)
    x, y, z = x[ok], y[ok], z[ok]
    vis = z <= zbuf[y, x] + 2 * cam.pix
    m[y[vis], x[vis]] = 1
    return m


def hidden_line(cam, v, t, e):
    import cv2
    zbuf = cam.depth(v, t)
    img = np.full((cam.H, cam.W), 18, dtype=np.uint8)
    img[np.isfinite(zbuf)] = 44
    lines = edge_mask(cam, v, zbuf, e) | edge_mask(cam, v, zbuf, silhouette_edges(v, t, cam.d))
    mask = np.isfinite(zbuf).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(lines, contours, -1, 1, 1)
    img[lines > 0] = 230
    return img


def xray(cam, v, t):
    pts, _ = sample_surface(v, t, cam.pix / 2)
    x, y, _ = cam.project(pts.astype(np.float64))
    ok = (x >= 0) & (x < cam.W) & (y >= 0) & (y < cam.H)
    acc = np.bincount(y[ok] * cam.W + x[ok], minlength=cam.W * cam.H).reshape(cam.H, cam.W).astype(np.float64)
    if acc.max() > 0:
        acc = np.log1p(acc) / np.log1p(acc.max())
    return (18 + acc * 220).astype(np.uint8)


# ---------------------------------------------------------------------------------------------------------- metrics

def min_angles(v, t):
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]

    def ang(p, q, r):
        u, w = q - p, r - p
        cosv = np.einsum('ij,ij->i', u, w) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1), 1e-30)
        return np.degrees(np.arccos(np.clip(cosv, -1, 1)))
    return np.minimum(np.minimum(ang(a, b, c), ang(b, c, a)), ang(c, a, b))


def boundary_length(v, t):
    edges, _, counts, _ = edge_table(t)
    e = edges[counts == 1]
    return float(np.linalg.norm(v[e[:, 1]] - v[e[:, 0]], axis=1).sum())


def silhouette_scores(ref, cand, length_m, long_px=512):
    """IoU and symmetric boundary Hausdorff (share of length) of top, side and front masks."""
    import cv2
    out = {}
    for name in ('top', 'side', 'front'):
        cam = Camera(ref[0], *view(name), long_px)
        a, b = np.isfinite(cam.depth(*ref)), np.isfinite(cam.depth(*cand))
        out[name + 'Iou'] = float((a & b).sum() / max((a | b).sum(), 1))
        # how far one mask reaches out of the other (Hausdorff of the filled regions; a boundary ring would count a
        # pinhole open in one mask only as far as its own boundary)
        d_to = [cv2.distanceTransform((~m).astype(np.uint8), cv2.DIST_L2, 5) for m in (a, b)]
        h = max(float(d_to[0][b].max(initial=0)), float(d_to[1][a].max(initial=0)))
        out[name + 'Hausdorff'] = h * cam.pix / length_m
    return out


def edge_fscore(ref, ref_e, cand, cand_e, yaw, long_px=600, tol=2.0):
    import cv2
    cam = Camera(ref[0], *view('iso', yaw), long_px)
    masks = []
    for (v, t), e in ((ref, ref_e), (cand, cand_e)):
        z = cam.depth(v, t)
        masks.append(edge_mask(cam, v, z, e) | edge_mask(cam, v, z, silhouette_edges(v, t, cam.d)))
    d = [cv2.distanceTransform((1 - m).astype(np.uint8), cv2.DIST_L2, 5) for m in masks]
    p = float((d[0][masks[1] > 0] <= tol).mean()) if masks[1].any() else 0.0
    r = float((d[1][masks[0] > 0] <= tol).mean()) if masks[0].any() else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


# Set before the runs (plan T7.4c-1). Slivers: relative only, 1.5 x max(Hull A, Hull D), passed in as sliver_limit;
# triangles: at most 110 % of the budget step (a small ship below it is fine).
THRESHOLDS = {'triangles': 0.10, 'iou': 0.95, 'hausdorff': 0.005, 'errorShare': 0.005, 'holes': 1.1,
              'winding': 0.005, 'fscore': 0.8}


def judge(rec, sliver_limit):
    th = THRESHOLDS
    fails = []
    if rec['triangles'] > (1 + th['triangles']) * rec['target']: fails.append('triangles')
    if min(rec['topIou'], rec['sideIou'], rec['frontIou']) < th['iou']: fails.append('iou')
    if max(rec['topHausdorff'], rec['sideHausdorff'], rec['frontHausdorff']) > th['hausdorff']: fails.append('hausdorff')
    if rec['errorM'] > th['errorShare'] * rec['lengthM']: fails.append('error')
    if rec['holeRatio'] > th['holes']: fails.append('holes')
    if rec['windingShare'] > th['winding']: fails.append('winding')
    if rec['sliverShare'] > sliver_limit: fails.append('slivers')
    if rec['edgeFscore'] < th['fscore']: fails.append('fscore')
    return fails


# ---------------------------------------------------------------------------------------------------------- pipeline

def work(slug, name=''):
    d = os.path.join(WORK, slug)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def ship_entry(slug):
    ships = load_json(os.path.join(HERE, 'ship-outlines.json'))['ships']
    return next(s for s in ships if s['slug'] == slug)


def is_long(v):
    ext = v.max(axis=0) - v.min(axis=0)
    return ext[0] > 2 * ext[1]


CORE_QUANTILES = (0.005, 0.995)   # area-weighted, per axis
CORE_MARGIN = 0.5                 # of the core's largest extent
AXIS_IOU_TIE = 0.03               # below this IoU gap between the two axes, Fleetyards' length / beam decides


def inside_core(v, t):
    """Triangles whose box meets the core of the mesh: per axis the area-weighted CORE_QUANTILES of the triangle
    centroids, widened by CORE_MARGIN x the core's largest extent. Drops stray parts far from the ship (Cutter Scout:
    2,450 specks over 4 x its length) and keeps antennas and barrels that reach out of the core."""
    tri = v[t]
    cen = tri.mean(axis=1)
    _, area = face_normals(v, t)
    cw_total = max(float(area.sum()), 1e-30)
    lo, hi = np.zeros(3), np.zeros(3)
    for k in range(3):
        o = np.argsort(cen[:, k], kind='stable')
        cw = np.cumsum(area[o]) / cw_total
        lo[k] = cen[o[min(int(np.searchsorted(cw, CORE_QUANTILES[0])), len(o) - 1)], k]
        hi[k] = cen[o[min(int(np.searchsorted(cw, CORE_QUANTILES[1])), len(o) - 1)], k]
    pad = CORE_MARGIN * float((hi - lo).max())
    return ((tri.max(axis=1) >= lo - pad) & (tri.min(axis=1) <= hi + pad)).all(axis=1)


def pick_axes(ext, length_m, beam_m, iou):
    """Bow axis (0 = glTF x, 2 = glTF z) and sign: the highest top-view IoU against the outline over both axes and
    both signs. Not the longer horizontal axis: a ship wider than long (Syulen 16 x 28 m) would lie across. Not
    Fleetyards' length / beam either, except to break a tie (IoU gap under AXIS_IOU_TIE): the holo's pose can differ
    from the dimensions (Reliant flies with its wings upright, so its beam of 28.5 m stands vertical)."""
    best = {a: max(iou[(a, 1)], iou[(a, -1)]) for a in (0, 2)}
    if abs(best[0] - best[2]) >= AXIS_IOU_TIE:
        axis = max(best, key=best.get)
    else:
        ratio = length_m / beam_m
        axis = min((0, 2), key=lambda a: abs(math.log(ext[a] / ext[2 - a] / ratio)))
    return axis, max((1, -1), key=lambda s: iou[(axis, s)])


def flatten(slug):
    import cv2
    js, binc = read_glb(work(slug, 'plain.glb'))
    m = scene_mesh(js, binc)
    entry = ship_entry(slug)
    core = inside_core(m.vertices, m.triangles)
    tris = m.triangles[core]
    v = m.vertices
    used = v[np.unique(tris)]
    ext = used.max(axis=0) - used.min(axis=0)
    poly = np.array(entry['outline'], dtype=np.float64)
    (ox0, oy0), (ox1, oy1) = poly.min(axis=0), poly.max(axis=0)
    nx, ny = 160, 64

    def raster(p2):
        x = np.clip(((p2[:, 0] - ox0) / (ox1 - ox0) * nx).astype(np.int64), 0, nx - 1)
        y = np.clip(((p2[:, 1] - oy0) / (oy1 - oy0) * ny).astype(np.int64), 0, ny - 1)
        r = np.zeros((ny, nx), dtype=bool); r[y, x] = True
        return r
    pm = np.zeros((ny, nx), dtype=np.uint8)
    pp = np.stack([(poly[:, 0] - ox0) / (ox1 - ox0) * nx, (poly[:, 1] - oy0) / (oy1 - oy0) * ny], axis=1)
    cv2.fillPoly(pm, [np.round(pp - 0.5).astype(np.int32)], 1)
    pm = pm.astype(bool)
    pts, _ = sample_surface(v, tris, float(ext.max()) / 400)
    pts = pts.astype(np.float64)
    up = np.array([0, 1.0, 0])

    def rotation(axis, sign):
        bow = np.zeros(3); bow[axis] = sign
        return np.stack([bow, np.cross(up, bow), up])    # rows: ship x, y, z in glTF coordinates

    scores = {}
    for axis in (0, 2):
        for sign in (1, -1):
            q = pts @ rotation(axis, sign).T
            c = (q.min(axis=0) + q.max(axis=0)) / 2
            k = (ox1 - ox0) / (q[:, 0].max() - q[:, 0].min())
            for mirror in (1, -1):
                p2 = np.stack([(q[:, 0] - c[0]) * k, mirror * (q[:, 1] - c[1]) * k], axis=1)
                r = raster(p2)
                scores[(axis, sign, mirror)] = float((r & pm).sum() / max((r | pm).sum(), 1))
    long_axis, sign = pick_axes({0: float(ext[0]), 2: float(ext[2])}, entry['lengthM'], entry['beamM'],
                                {(a, sg): scores[(a, sg, 1)] for a in (0, 2) for sg in (1, -1)})
    score = scores[(long_axis, sign, 1)]
    rot = rotation(long_axis, sign)
    q = v @ rot.T
    qu = used @ rot.T
    s = entry['lengthM'] / (qu[:, 0].max() - qu[:, 0].min())
    lo, hi = qu.min(axis=0), qu.max(axis=0)
    q = (q - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])) * s
    normals = m.normals @ rot.T if m.normals is not None else None
    big = [st for st, n in m.steps if n >= STEP_MIN_VERTICES]
    step_m = (max(big) if big else 0.0) * s
    tol = float(np.clip(0.6 * step_m, WELD_MIN_M, WELD_MAX_M))
    before = edge_table(tris)[2]
    wv, remap = weld(q, tol)
    t = clean_triangles(remap[tris])
    wn = None
    if normals is not None:
        wn = np.zeros_like(wv)
        np.add.at(wn, remap, normals)
        wn /= np.maximum(np.linalg.norm(wn, axis=1, keepdims=True), 1e-12)
    wv, t, wn = compact(wv, t, wn)
    after = edge_table(t)[2]
    atomic(work(slug, 'flat.npz'), lambda f: np.savez(f, vertices=wv.astype(np.float32), triangles=t.astype(np.int32),
             normals=wn.astype(np.float32) if wn is not None else np.zeros((0, 3), np.float32), lengthM=entry['lengthM']))
    rec = {'slug': slug, 'step': 'flatten', 'rawTriangles': int(len(m.triangles)), 'primitives': len(m.steps),
           'hasNormals': normals is not None, 'longAxis': 'x' if long_axis == 0 else 'z', 'bowSign': sign,
           'strayTriangles': int((~core).sum()),
           'iou': round(score, 3), 'iouTurned': round(scores[(long_axis, -sign, 1)], 3),
           'iouMirrored': round(scores[(long_axis, sign, -1)], 3), 'iouAcross': round(max(scores[(2 - long_axis, sg, 1)] for sg in (1, -1)), 3),
           'scale': round(float(s), 6), 'dracoStepM': round(float(step_m), 5), 'weldTolM': round(tol, 5),
           'vertices': int(len(wv)), 'triangles': int(len(t)),
           'nonManifoldBefore': int((before > 2).sum()), 'boundaryBefore': int((before == 1).sum()),
           'nonManifoldAfter': int((after > 2).sum()), 'boundaryAfter': int((after == 1).sum()),
           'widthM': round(float(wv[:, 1].max() - wv[:, 1].min()), 2), 'beamM': entry['beamM'],
           'heightM': round(float(wv[:, 2].max() - wv[:, 2].min()), 2), 'shipHeightM': entry['heightM']}
    print(json.dumps(rec))


# ---------------------------------------------------------------------------------------------------------- Motherlode

# The models lie in three.js space: glTF = (game x, game z, -game y), game x starboard, y bow, z up, in metres. Ship axes
# are x bow, y port, z up, so ship = (game y, -game x, game z) = (-glTF z, -glTF x, glTF y), the mapping
# tools/import-motherlode.ps1 applies to the cargo grids. A rotation (det +1), never a mirror; nothing is centred or
# scaled, so the origin stays the game model's and the ship file's fraction s places the mesh (D93).
MODEL_TO_SHIP = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=np.float64)   # rows: ship x, y, z in glTF axes
CELL_M = 1.25                                  # one cell, one SCU (SC-CargoPlan D9)
OUTLINE_MIN_RES_M, OUTLINE_PIXELS = 0.01, 4000  # raster: 1 cm, or the length in 4000 pixels on the largest ships
# Slits between parts seen from above are closed with the first of these radii at which the largest contour holds
# OUTLINE_MIN_SHARE of the seen area: the Hull A's bow and stern hang together by the spindle's lattice only.
OUTLINE_CLOSE_M = (0.1, 0.2, 0.4, 0.8, 1.6)
OUTLINE_MIN_SHARE = 0.99
OUTLINE_TOLERANCE_M, OUTLINE_TOLERANCE_SHARE = 0.08, 0.004   # Douglas-Peucker as trace.py: max(0.08 m, 0.4 % of length)


def model_to_ship(v):
    return np.asarray(v, dtype=np.float64) @ MODEL_TO_SHIP.T


def box_record(v):
    """Length, beam, height and floor of a mesh in ship axes, metres to the millimetre."""
    lo, hi = v.min(axis=0), v.max(axis=0)
    mm = lambda x: round(float(x), 3)
    return {'lengthM': mm(hi[0] - lo[0]), 'beamM': mm(hi[1] - lo[1]), 'heightM': mm(hi[2] - lo[2]), 'floorM': mm(lo[2]),
            'boxMin': [mm(x) for x in lo], 'boxMax': [mm(x) for x in hi]}


def flatten_model(key, glb_path):
    """A Motherlode model -> flat.npz (ship axes, metres, welded) and flat.json (its record). Stray specks go as in
    flatten; the length is the kept mesh's extent along the bow."""
    js, binc = read_glb(glb_path)
    m = scene_mesh(js, binc)
    core = inside_core(m.vertices, m.triangles)
    tris = m.triangles[core]
    q = model_to_ship(m.vertices)
    normals = m.normals @ MODEL_TO_SHIP.T if m.normals is not None else None
    big = [st for st, n in m.steps if n >= STEP_MIN_VERTICES]
    tol = float(np.clip(0.6 * (max(big) if big else 0.0), WELD_MIN_M, WELD_MAX_M))
    before = edge_table(tris)[2]
    wv, remap = weld(q, tol)
    t = clean_triangles(remap[tris])
    wn = None
    if normals is not None:
        wn = np.zeros_like(wv)
        np.add.at(wn, remap, normals)
        wn /= np.maximum(np.linalg.norm(wn, axis=1, keepdims=True), 1e-12)
    wv, t, wn = compact(wv, t, wn)
    after = edge_table(t)[2]
    box = box_record(wv)
    atomic(work(key, 'flat.npz'), lambda f: np.savez(f, vertices=wv.astype(np.float32), triangles=t.astype(np.int32),
             normals=wn.astype(np.float32) if wn is not None else np.zeros((0, 3), np.float32), lengthM=box['lengthM']))
    rec = dict({'key': key, 'step': 'flatten', 'source': 'motherlode', 'model': os.path.basename(glb_path),
                'rawSha256': hashlib.sha256(read_bytes(glb_path)).hexdigest(),
                'cargoPose': 'cargoPose' in js.get('asset', {}).get('extras', {}),
                'rawTriangles': int(len(m.triangles)), 'strayTriangles': int((~core).sum()), 'weldTolM': round(tol, 5),
                'vertices': int(len(wv)), 'triangles': int(len(t)),
                'nonManifoldBefore': int((before > 2).sum()), 'boundaryBefore': int((before == 1).sum()),
                'nonManifoldAfter': int((after > 2).sum()), 'boundaryAfter': int((after == 1).sum())}, **box)
    atomic(work(key, 'flat.json'), lambda f: f.write(json.dumps(rec).encode()))
    print(json.dumps(rec))
    return rec


def top_outline(v, t):
    """Top-view silhouette of a mesh in ship axes: every triangle filled into a raster, slits closed (OUTLINE_CLOSE_M),
    the largest outer contour simplified as trace.py does. Points in metres around the mesh's own origin; largestShare
    tells how much of the seen area that contour holds (a part further apart than the largest radius is dropped)."""
    import cv2
    v = np.asarray(v, dtype=np.float64)
    lo, hi = v.min(axis=0), v.max(axis=0)
    length = float(hi[0] - lo[0])
    res = max(OUTLINE_MIN_RES_M, length / OUTLINE_PIXELS)
    pad = int(round(max(OUTLINE_CLOSE_M) / res)) + 3
    x0, y0 = lo[0] - pad * res, lo[1] - pad * res
    w = int(math.ceil((hi[0] - lo[0]) / res)) + 2 * pad + 1
    h = int(math.ceil((hi[1] - lo[1]) / res)) + 2 * pad + 1
    shift = 4                                                    # sub-pixel corners: 1/16 pixel
    px = np.round(np.stack([(v[:, 0] - x0) / res, (v[:, 1] - y0) / res], axis=1) * (1 << shift)).astype(np.int32)
    mask = np.zeros((h, w), dtype=np.uint8)
    for tri in px[t]:
        cv2.fillConvexPoly(mask, tri, 1, cv2.LINE_8, shift)
    for close_m in OUTLINE_CLOSE_M:
        k = max(3, int(round(close_m / res)) | 1)
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        areas = [cv2.contourArea(c) for c in contours]
        if max(areas) >= OUTLINE_MIN_SHARE * sum(areas):
            break
    best = contours[int(np.argmax(areas))]
    eps = max(OUTLINE_TOLERANCE_M, OUTLINE_TOLERANCE_SHARE * length) / res
    simple = cv2.approxPolyDP(best, eps, True)[:, 0, :].astype(np.float64)
    pts = np.stack([x0 + (simple[:, 0] + 0.5) * res, y0 + (simple[:, 1] + 0.5) * res], axis=1)
    return dict({'outline': [[round(float(x), 3), round(float(y), 3)] for x, y in pts], 'rawPoints': int(len(best)),
                 'points': int(len(pts)), 'resolutionM': res, 'closeM': close_m,
                 'largestShare': round(float(max(areas) / max(sum(areas), 1e-30)), 4)},
                **{k: x for k, x in box_record(v).items() if k in ('lengthM', 'beamM', 'heightM', 'floorM')})


def outline(key, out_path=None):
    """outline.json next to flat.npz: the model's top-view silhouette with its box (lengthM, beamM, heightM, floorM)."""
    v, t, _, _ = load_flat(key)
    o = dict({'key': key}, **top_outline(v, t))
    atomic(out_path or work(key, 'outline.json'), lambda f: f.write(json.dumps(o).encode()))
    print(json.dumps({k: x for k, x in o.items() if k != 'outline'}))


def read_map(path):
    """model-map.csv of SC-CargoPlan's tools/import-motherlode.ps1 -ModelMap: id, className, modelKey, s. A map written
    before SC-CargoPlan D94 names the column fleetyardsSlug; both read as modelKey."""
    import csv
    with open(path, encoding='utf-8', newline='') as f:
        return [dict(r, modelKey=r.get('modelKey', r.get('fleetyardsSlug', '')), s=[float(r['sx']), float(r['sy']), float(r['sz'])])
                for r in csv.DictReader(f)]


def slug_models(rows):
    """The model that shows each slug: the className of the slug's row with the smallest id (variants share their base
    ship's slug; only the Carrack family has two models, 24 bytes apart). Returns {slug: className} and the slugs with
    more than one model."""
    by_slug = {}
    for r in sorted(rows, key=lambda r: r['id']):
        if r['modelKey']:
            by_slug.setdefault(r['modelKey'], []).append(r['className'])
    return {s: c[0] for s, c in by_slug.items()}, sorted(s for s, c in by_slug.items() if len(set(c)) > 1)


def fit(map_csv, ships_dir, out_csv, ids=()):
    """Per ship of the map: (a) share of rack corners in the model's box, (b) the worst rack's intrusion, (c) IoU of the
    outline (outline.json) and the hologram's top view (PP.holo, else the flat mesh), and the outline's largestShare."""
    rows = [r for r in read_map(map_csv) if not ids or r['id'] in ids]
    lines = ['id,className,racks,cornersInBox,maxIntrusion,worstRack,outlineIou,largestShare']
    for r in rows:
        key = r['className']
        v, t, _, _ = load_flat(key)
        racks = load_json(os.path.join(ships_dir, r['id'] + '.json'))['racks']
        corners = corners_in_box(v, racks, r['s'])
        worst = max(((rack_intrusion(v, t, k, r['s']), k['id']) for k in racks), key=lambda x: x[0])
        iou, share = '', ''
        if os.path.exists(work(key, 'outline.json')):
            o = load_json(work(key, 'outline.json'))
            hv, ht = v, t
            if os.path.exists(work(key, 'PP.holo')):
                h = read_sch2(work(key, 'PP.holo'))
                hv, ht = h['vertices'].astype(np.float64), h['triangles'].astype(np.int64)
            iou, share = outline_iou(o['outline'], hv, ht), o['largestShare']
        lines.append(f"{r['id']},{key},{len(racks)},{corners:.4f},{worst[0]:.4f},{worst[1]},{iou},{share}")
        print(lines[-1])
    atomic(out_csv, lambda f: f.write(('\n'.join(lines) + '\n').encode()))


# Ship axis of the grid's length, width and stack per stack axis (SC-CargoPlan Rack.FrameOf, D26).
FRAMES = {'+x': (2, 1, 0), '-x': (2, 1, 0), '+y': (0, 2, 1), '-y': (0, 2, 1), '+z': (0, 1, 2), '-z': (0, 1, 2)}


def rack_box(rack):
    """Min and max corner of a rack in cells, before its rotation, as Rack.Bounds in SC-CargoPlan."""
    g = rack['grid']
    lo = np.array(rack['origin'], dtype=np.float64)
    size = np.zeros(3)
    for k, ext in enumerate((g['length'], g['width'], g['stack'])):
        size[FRAMES[rack.get('stackAxis', '+z')][k]] = ext
    return lo, lo + size


def rack_corners_m(rack, s):
    """The rack's eight corners in the model's metres: turned about its middle as RackTransform does (R = Rz(yaw)
    Ry(pitch) Rx(roll), D91), then moved by the ship file's fraction s, where the model's origin lies in cells."""
    lo, hi = rack_box(rack)
    c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    mid = (lo + hi) / 2
    c = (c - mid) @ rack_rotation(rack).T + mid
    return (c - np.asarray(s, dtype=np.float64)) * CELL_M


def rack_rotation(rack):
    """R = Rz(yaw) Ry(pitch) Rx(roll) of a rack (D91), identity for a straight one."""
    if not rack.get('rotation'):
        return np.eye(3)
    yaw, pitch, roll = (math.radians(a) for a in rack['rotation'])
    rz = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
    ry = np.array([[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]])
    rx = np.array([[1, 0, 0], [0, math.cos(roll), -math.sin(roll)], [0, math.sin(roll), math.cos(roll)]])
    return rz @ ry @ rx


# fit (session 4b, E1): a rack's box is shrunk by this on each side before the hull may cut into it, so the rounding to
# whole cells (up to 0.4 cells per axis, D92) and the floor a rack stands on don't count.
FIT_MARGIN_M, FIT_MARGIN_SHARE = 0.5, 0.2
FIT_SPACING_M = 0.05
FIT_CORNER_EPS_M = 0.001


def rack_intrusion(v, t, rack, s):
    """Hull surface inside the rack's shrunk box, as a share of that box's surface: 0 when no wall cuts through it, about
    1/6 for a wall through its middle. The mesh is in model metres; the rack is turned (D91) and moved by s."""
    lo, hi = rack_box(rack)
    lo_m, hi_m = (lo - np.asarray(s, dtype=np.float64)) * CELL_M, (hi - np.asarray(s, dtype=np.float64)) * CELL_M
    margin = np.minimum(FIT_MARGIN_M, FIT_MARGIN_SHARE * (hi_m - lo_m))
    a, b = lo_m + margin, hi_m - margin
    rot, mid = rack_rotation(rack), (lo_m + hi_m) / 2
    corners = rack_corners_m(rack, s)
    tri = v[t]
    near = ((tri.max(axis=1) >= corners.min(axis=0)) & (tri.min(axis=1) <= corners.max(axis=0))).all(axis=1)
    d = b - a
    box_area = 2 * (d[0] * d[1] + d[1] * d[2] + d[0] * d[2])
    if not near.any():
        return 0.0
    sel = t[near]
    pts, ids = sample_surface(v, sel, FIT_SPACING_M)
    local = (pts.astype(np.float64) - mid) @ rot + mid              # back into the straight rack's frame
    inside = ((local >= a) & (local <= b)).all(axis=1)
    if not inside.any():
        return 0.0
    _, area = face_normals(v, sel)
    share = np.bincount(ids[inside], minlength=len(sel)) / np.maximum(np.bincount(ids, minlength=len(sel)), 1)
    return round(float((area * share).sum() / box_area), 4)


def corners_in_box(v, racks, s):
    """Share of the racks' corners (turned, moved by s) inside the model's box."""
    lo, hi = v.min(axis=0) - FIT_CORNER_EPS_M, v.max(axis=0) + FIT_CORNER_EPS_M
    c = np.vstack([rack_corners_m(r, s) for r in racks])
    return float(((c >= lo) & (c <= hi)).all(axis=1).mean())


def outline_iou(outline_pts, v, t, long_px=1000):
    """IoU of an outline polygon and a mesh's top view, rastered at the mesh's length / long_px."""
    import cv2
    poly = np.asarray(outline_pts, dtype=np.float64)
    both = np.vstack([v[:, :2], poly])
    lo, hi = both.min(axis=0), both.max(axis=0)
    res = float((hi - lo).max()) / long_px
    w, h = int((hi[0] - lo[0]) / res) + 3, int((hi[1] - lo[1]) / res) + 3
    shift = 4
    px = lambda p: np.round((np.asarray(p)[..., :2] - lo) / res * (1 << shift)).astype(np.int32)
    mesh = np.zeros((h, w), np.uint8)
    for tri in px(v)[t]:
        cv2.fillConvexPoly(mesh, tri, 1, cv2.LINE_8, shift)
    out = np.zeros((h, w), np.uint8)
    cv2.fillPoly(out, [px(poly)], 1, cv2.LINE_8, shift)
    return round(float((mesh & out).sum() / max((mesh | out).sum(), 1)), 4)


BOX_EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count('1') == 1]   # corners differ in one axis
# BGR: blue, green, orange, violet, then yellow and cyan
RACK_COLOURS = [(255, 170, 60), (80, 220, 120), (80, 160, 255), (220, 90, 220), (90, 220, 220), (240, 240, 90)]


def probe(key, ship_path, s, out_png, tile=480):
    """Hidden-line top, side, front and iso view of flat.npz with the ship file's racks drawn over it, moved by the
    fraction s: what the app shows with holoOrigin = s, without the app (session 4b gate: racks in the hull)."""
    import cv2
    v, t, _, length = load_flat(key)
    ship = load_json(ship_path)
    racks = [rack_corners_m(r, s) for r in ship['racks']]
    e = feature_edges(v, t, length)[0]
    tiles = []
    for name in ('top', 'side', 'front', 'iso'):
        cam = Camera(np.vstack([v] + racks), *view(name, 70.0 if is_long(v) else 45.0), tile)
        im = cv2.cvtColor(hidden_line(cam, v, t, e), cv2.COLOR_GRAY2BGR)
        for k, c in enumerate(racks):
            x, y, _ = cam.project(c)
            for a, b in BOX_EDGES:
                cv2.line(im, (int(x[a]), int(y[a])), (int(x[b]), int(y[b])), RACK_COLOURS[k % len(RACK_COLOURS)], 1, cv2.LINE_AA)
        cv2.putText(im, name, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1, cv2.LINE_AA)
        canvas = np.full((tile, tile, 3), 18, dtype=np.uint8)
        im = im[:tile, :tile]
        canvas[:im.shape[0], :im.shape[1]] = im
        tiles.append(canvas)
    head = np.full((26, tile * 4, 3), 18, dtype=np.uint8)
    cv2.putText(head, f"{key}  {ship['id']}  s = {s}  length {length:.2f} m  racks in colour (rack 1 blue, 2 green, 3 orange, 4 violet)",
                (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.imwrite(out_png, np.vstack([head, np.hstack(tiles)]))


def load_flat(slug, name='flat.npz'):
    z = np.load(work(slug, name))
    n = z['normals']
    return z['vertices'].astype(np.float64), z['triangles'].astype(np.int64), (n.astype(np.float64) if len(n) else None), float(z['lengthM'])


def write_bin(path, v, t):
    atomic(path, lambda f: f.write(struct.pack('<II', len(v), len(t)) + v.astype('<f4').tobytes() + t.astype('<u4').tobytes()))


def cull(slug, min_pixels=CULL_MIN_PIXELS):
    v, t, n, length = load_flat(slug)
    keep = visible_triangles(v, t, min_pixels=min_pixels)
    st = t[keep]
    sv, st, sn = compact(v, st, n)
    atomic(work(slug, 'shell.npz'), lambda f: np.savez(f, vertices=sv.astype(np.float32), triangles=st.astype(np.int32),
             normals=sn.astype(np.float32) if sn is not None else np.zeros((0, 3), np.float32), lengthM=length))
    write_bin(work(slug, 'shell.bin'), sv, st)
    rec = {'slug': slug, 'step': 'cull', 'minPixels': min_pixels, 'triangles': int(len(t)), 'kept': int(len(st)),
           'removedShare': round(1 - len(st) / len(t), 4), 'boundaryLengthM': round(boundary_length(sv, st), 2)}
    print(json.dumps(rec))


def read_idx(path):
    b = read_bytes(path)
    (tc,) = struct.unpack_from('<I', b)
    return np.frombuffer(b, '<u4', 3 * tc, 4).reshape(-1, 3).astype(np.int64)


def export(slug, method, target, error_m, sloppy, ms, sliver_limit=None):
    sv, st, sn, length = load_flat(slug, 'shell.npz')
    t = read_idx(work(slug, method + '.idx'))
    v, t, n = compact(sv, t, sn)
    t = orient(v, t, n)
    e, l1, l2 = feature_edges(v, t, length)
    out = work(slug, method + '.holo')
    write_sch2(out, v, t, e, l1, l2, length)
    rv, rt, rn = compact(sv, read_idx(work(slug, 'ref.idx')), sn)
    rt = orient(rv, rt, rn)
    re_, _, rl2 = feature_edges(rv, rt, length)
    yaw = 70.0 if is_long(sv) else 45.0
    _, _, counts, _ = edge_table(t)
    rec = {'slug': slug, 'step': 'export', 'method': method, 'target': target, 'triangles': int(len(t)),
           'vertices': int(len(v)), 'errorM': round(error_m, 4), 'sloppy': sloppy, 'simplifyMs': ms,
           'lengthM': length, 'edges': [int(l1), int(l2), int(len(e))], 'bytes': os.path.getsize(out),
           'holeRatio': round(boundary_length(v, t) / max(boundary_length(sv, st), 1e-9), 3),
           'windingShare': round(winding_conflicts(t) / max(int((counts == 2).sum()), 1), 5),
           'sliverShare': round(float((min_angles(v, t) < 3).mean()), 4),
           'edgeFscore': round(edge_fscore((rv, rt), re_[:rl2], (v, t), e[:l2], yaw), 3)}
    rec.update({k: round(x, 4) for k, x in silhouette_scores((rv, rt), (v, t), length).items()})
    if sliver_limit is not None:
        rec['fails'] = judge(rec, sliver_limit)
    atomic(work(slug, method + '.json'), lambda f: f.write(json.dumps(rec).encode()))
    print(json.dumps(rec))


def sheet(method, out_dir, slugs=None, per_sheet=12, tile=320):
    import cv2
    os.makedirs(out_dir, exist_ok=True)
    recs = []
    for slug in sorted(os.listdir(WORK)):
        p = os.path.join(WORK, slug, method + '.json')
        if os.path.exists(p) and (slugs is None or slug in slugs):
            recs.append(load_json(p))
    # not clean ships on sheets of their own; worst first: most failed criteria, then the lowest edge F-score
    recs.sort(key=lambda r: (-len(r.get('fails', [])), r['edgeFscore'], r['slug']))
    groups = [('clean', [r for r in recs if 'fails' in r and not r['fails']]),
              ('notclean', [r for r in recs if r.get('fails')]),
              ('unjudged', [r for r in recs if 'fails' not in r])]
    for group, members in groups:
        sheet_group(method, out_dir, group, members, per_sheet, tile)


def sheet_outline(key):
    """The outline drawn on the sheet's top view: a Motherlode model's own outline.json (D93), else the traced one."""
    p = os.path.join(WORK, key, 'outline.json')
    return load_json(p)['outline'] if os.path.exists(p) else ship_entry(key)['outline']


def sheet_group(method, out_dir, group, recs, per_sheet, tile):
    import cv2
    cols = ('L1', 'L2', 'L3', 'top', 'x-ray')
    for si in range(0, len(recs), per_sheet):
        rows = []
        for r in recs[si: si + per_sheet]:
            h = read_sch2(work(r['slug'], method + '.holo'))
            v, t, e = h['vertices'].astype(np.float64), h['triangles'], h['edges']
            yaw = 70.0 if is_long(v) else 45.0
            iso = Camera(v, *view('iso', yaw), tile)
            tiles = [hidden_line(iso, v, t, e[:n]) for n in (h['level1Count'], h['level2Count'], len(e))]
            # top view with the traced outline (D55) in red: a holo turned, mirrored or scaled wrong shows at once
            poly = np.array(sheet_outline(r['slug']), dtype=np.float64)
            poly3 = np.column_stack([poly, np.zeros(len(poly))])
            top = Camera(np.vstack([v, poly3]), *view('top'), tile)
            tiles.append(hidden_line(top, v, t, e[:h['level2Count']]))
            tiles.append(xray(iso, v, t))
            tiles = [cv2.cvtColor(im, cv2.COLOR_GRAY2BGR) for im in tiles]
            px, py, _ = top.project(poly3)
            cv2.polylines(tiles[3], [np.stack([px, py], axis=1).astype(np.int32)], True, (60, 60, 255), 1, cv2.LINE_AA)
            row = np.full((tile * 3 // 4 + 22, tile * len(tiles), 3), 18, dtype=np.uint8)
            for k, im in enumerate(tiles):
                im = im[: tile * 3 // 4, :tile]
                y0 = 22 + (tile * 3 // 4 - im.shape[0]) // 2
                row[y0: y0 + im.shape[0], k * tile: k * tile + im.shape[1]] = im
            verdict = 'not judged' if 'fails' not in r else 'ok' if not r['fails'] else 'NOT CLEAN: ' + ','.join(r['fails'])
            label = (f"{r['slug']}  budget {r.get('budget', r['target'])}  {r['triangles']} tris  edges {r['edges']}  "
                     f"F {r['edgeFscore']}  {verdict}")
            colour = (230, 230, 230) if r.get('fails') is not None and not r['fails'] else (80, 160, 255)
            cv2.putText(row, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)
            rows.append(row)
        head = np.full((22, rows[0].shape[1], 3), 18, dtype=np.uint8)
        for k, c in enumerate(cols):
            cv2.putText(head, c + (' (red: traced outline)' if c == 'top' else ''), (k * tile + 6, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(out_dir, f'{method}-{group}-{si // per_sheet + 1:02d}.png'), np.vstack([head] + rows))


def rejected_slugs(text):
    """Slugs of rejected.md: every top-level list line that starts with a slug in backticks."""
    import re
    return {m.group(1) for m in re.finditer(r'^- `([a-z0-9-]+)`', text, re.MULTILINE)}


def rejected_lines(recs):
    return [f"- `{r['slug']}`: not clean at {r['budget']}: {', '.join(r['fails'])}"
            for r in sorted(recs, key=lambda r: r['slug']) if r['fails']]


def write_rejected(method='PP'):
    """rejected.md from the judged ships; Martin removes a line to publish a ship anyway, or adds one to drop it."""
    recs = [load_json(os.path.join(WORK, s, method + '.json')) for s in sorted(os.listdir(WORK))
            if os.path.exists(os.path.join(WORK, s, method + '.json'))]
    text = ('# Rejected holograms\n\nShips left out of the release; the app shows their outline. Written by '
            '`holo_mesh.py rejected` from the metrics (thresholds in `judge`); a line removed by hand publishes the '
            'ship anyway, a line added by hand drops one.\n\n' + '\n'.join(rejected_lines(recs)) + '\n')
    atomic(os.path.join(HERE, 'rejected.md'), lambda f: f.write(text.encode()))
    print(json.dumps({'judged': len(recs), 'rejected': len(rejected_lines(recs))}))


def release(out_dir, data_version, generated_at, method='PP'):
    """Release folder: every judged ship not in rejected.md as <slug>.holo, NOTICE.md, manifest.json."""
    import shutil, subprocess
    rejected = rejected_slugs(read_bytes(os.path.join(HERE, 'rejected.md')).decode('utf-8'))
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))
    ships = {}
    for slug in sorted(os.listdir(WORK)):
        p = os.path.join(WORK, slug, method + '.json')
        if not os.path.exists(p) or slug in rejected: continue
        r = load_json(p)
        shutil.copyfile(os.path.join(WORK, slug, method + '.holo'), os.path.join(out_dir, slug + '.holo'))
        raw = os.path.join(HERE, 'legacy', 'raw', slug, 'holo.gltf')
        ships[slug] = {'rawSha256': hashlib.sha256(read_bytes(raw)).hexdigest(), 'budget': r['budget'],
                       'triangles': r['triangles'], 'edges': r['edges'], 'passed': r['passed'],
                       'metrics': {k: r[k] for k in ('errorM', 'topIou', 'sideIou', 'frontIou', 'topHausdorff',
                                                     'sideHausdorff', 'frontHausdorff', 'edgeFscore', 'holeRatio',
                                                     'windingShare', 'sliverShare')}}
    shutil.copyfile(os.path.join(HERE, 'release', 'NOTICE.md'), os.path.join(out_dir, 'NOTICE.md'))
    commit = subprocess.run(['git', '-C', HERE, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                            check=True).stdout.strip()
    tools = {'meshoptimizer': '1.3.0', 'gltf-transform': '4.5.1', 'node': '24.16.0', 'python': sys.version.split()[0],
             'numpy': np.__version__}
    m = build_manifest(out_dir, ships, data_version, generated_at, commit, tools)
    atomic(os.path.join(out_dir, 'manifest.json'), lambda f: f.write(json.dumps(m, indent=1).encode()))
    print(json.dumps({'ships': len(ships), 'rejected': len(rejected), 'pipelineCommit': commit}))


METRIC_KEYS = ('errorM', 'topIou', 'sideIou', 'frontIou', 'topHausdorff', 'sideHausdorff', 'frontHausdorff', 'edgeFscore',
               'holeRatio', 'windingShare', 'sliverShare')


def pipeline_commit():
    import subprocess
    return subprocess.run(['git', '-C', HERE, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                          check=True).stdout.strip()


def release_v2(out_dir, data_version, generated_at, map_csv, prev_dir, keep):
    """holo-v2 (session 4b, D93) and later tags: one <slug>.holo per slug of the model map, from its model's PP.holo in
    $HOLO_WORK; the ships kept (no model, or gone from the catalog) take their file and manifest entry from the previous
    release byte for byte, with its model label (holo-v1's entries have none: they are Fleetyards'). NOTICE.md comes
    from release-<v>/ for the tag holo-<v>. Nothing is rejected here: the contact sheet decides (as for holo-v1)."""
    import shutil
    models, shared = slug_models(read_map(map_csv))
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))
    ships = {}
    for slug, key in sorted(models.items()):
        r, flat = load_json(work(key, 'PP.json')), load_json(work(key, 'flat.json'))
        shutil.copyfile(work(key, 'PP.holo'), os.path.join(out_dir, slug + '.holo'))
        ships[slug] = {'model': key, 'rawSha256': flat['rawSha256'], 'budget': r['budget'], 'triangles': r['triangles'],
                       'edges': r['edges'], 'passed': r['passed'], 'metrics': {k: r[k] for k in METRIC_KEYS}}
    prev = {s['slug']: s for s in load_json(os.path.join(prev_dir, 'manifest.json'))['ships']}
    for slug in keep:
        shutil.copyfile(os.path.join(prev_dir, prev[slug]['file']), os.path.join(out_dir, slug + '.holo'))
        ships[slug] = dict({'model': 'fleetyards (holo-v1)'},
                           **{k: x for k, x in prev[slug].items() if k not in ('slug', 'file', 'bytes', 'sha256')})
    notice_dir = 'release-' + data_version.removeprefix('holo-')
    shutil.copyfile(os.path.join(HERE, notice_dir, 'NOTICE.md'), os.path.join(out_dir, 'NOTICE.md'))
    tools = {'meshoptimizer': '1.3.0', 'node': '24.16.0', 'python': sys.version.split()[0], 'numpy': np.__version__}
    m = build_manifest(out_dir, ships, data_version, generated_at, pipeline_commit(), tools)
    atomic(os.path.join(out_dir, 'manifest.json'), lambda f: f.write(json.dumps(m, indent=1).encode()))
    print(json.dumps({'ships': len(ships), 'fromModels': len(models), 'kept': len(keep), 'sharedSlugs': shared,
                      'bytes': sum(e['bytes'] for e in m['ships']), 'pipelineCommit': m['pipelineCommit']}))


def outlines_v2(map_csv, prev_outlines, out_path, generated_at, data_version, keep):
    """ship-outlines.json for the hologram release data_version (holo-v2, D93, and later): per slug of the model map its
    model's outline.json (metres, origin = the model's, with floorM); the ships kept (keep) their previous entry
    unchanged. Schema 1 stays (the app checks it)."""
    models, _ = slug_models(read_map(map_csv))
    entries = []
    for slug, key in models.items():
        o = load_json(work(key, 'outline.json'))
        entries.append({'slug': slug, 'className': key, 'lengthM': o['lengthM'], 'beamM': o['beamM'],
                        'heightM': o['heightM'], 'floorM': o['floorM'], 'outline': o['outline']})
    prev = {s['slug']: s for s in load_json(prev_outlines)['ships']}
    entries += [prev[slug] for slug in keep]
    doc = {'schemaVersion': 1, 'generatedAt': generated_at, 'dataVersion': data_version,
           'coordinateSystem': 'meters; x = bow (+), y = port (+); polygon closed implicitly. Entries with floorM: origin = '
                               f'the game model\'s origin (as hologram release {data_version}), floorM = the model\'s lowest point '
                               'below it. Entries without floorM: origin = center of the top-view bounding box (Fleetyards trace)',
           'source': 'Top views of the ship models from cryon.rocks (Motherlode), extracted from Star Citizen game files '
                     '(CIG assets): every triangle filled -> closed 0.1 m -> largest outer contour -> Douglas-Peucker '
                     'max(0.08 m, 0.4 % of length). Entries without floorM: top-view renders from fleetyards.net, traced',
           'ships': sorted(entries, key=lambda e: e['slug'])}
    atomic(out_path, lambda f: f.write(json.dumps(doc, separators=(',', ':')).encode()))
    print(json.dumps({'ships': len(entries), 'fromModels': len(models), 'kept': len(keep),
                      'points': sum(len(e['outline']) for e in entries), 'bytes': os.path.getsize(out_path)}))


def build_manifest(folder, ships, data_version, generated_at, pipeline_commit, tools):
    files = sorted(f[:-5] for f in os.listdir(folder) if f.endswith('.holo'))
    if sorted(ships) != files:
        raise ValueError(f'files and ships differ: {sorted(set(files) ^ set(ships))}')
    entries = []
    for slug in files:
        p = os.path.join(folder, slug + '.holo')
        data = read_bytes(p)
        entries.append(dict({'slug': slug, 'file': slug + '.holo', 'bytes': len(data),
                             'sha256': hashlib.sha256(data).hexdigest()}, **ships[slug]))
    return {'dataVersion': data_version, 'formatVersion': FORMAT_VERSION, 'generatedAt': generated_at,
            'pipelineCommit': pipeline_commit, 'tools': tools, 'ships': entries}


def verify(folder, outlines_path=None):
    m = load_json(os.path.join(folder, 'manifest.json'))
    outline_slugs = {s['slug'] for s in load_json(outlines_path or os.path.join(HERE, 'ship-outlines.json'))['ships']}
    problems = []
    files = {f for f in os.listdir(folder) if f.endswith('.holo')}
    for s in m['ships']:
        p = os.path.join(folder, s['file'])
        files.discard(s['file'])
        if s['slug'] not in outline_slugs: problems.append(f"{s['slug']}: not in ship-outlines.json")
        data = read_bytes(p)
        if len(data) != s['bytes'] or hashlib.sha256(data).hexdigest() != s['sha256']:
            problems.append(f"{s['slug']}: size or hash differs from the manifest")
        try:
            read_sch2(p)
        except ValueError as ex:
            problems.append(str(ex))
    problems += [f'{f}: not in the manifest' for f in sorted(files)]
    print(json.dumps({'ships': len(m['ships']), 'problems': problems}))
    return not problems


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'flatten': flatten(args[0])
    elif cmd == 'flatten-model': flatten_model(args[0], args[1])
    elif cmd == 'outline': outline(*args[:2])
    elif cmd == 'fit': fit(args[0], args[1], args[2], set(args[3:]))
    elif cmd == 'probe': probe(args[0], args[1], [float(x) for x in args[2].split(',')], args[3])
    elif cmd == 'cull': cull(args[0], *(int(a) for a in args[1:2]))
    elif cmd == 'export':
        slug, method, target, err, sloppy, ms = args[:6]
        export(slug, method, int(target), float(err), sloppy == 'true', int(ms),
               float(args[6]) if len(args) > 6 else None)
    elif cmd == 'sheet': sheet(args[0], args[1], set(args[2:]) or None)
    elif cmd == 'verify': sys.exit(0 if verify(*args[:2]) else 1)
    elif cmd == 'release-v2': release_v2(args[0], args[1], args[2], args[3], args[4], args[5:])
    elif cmd == 'outlines-v2': outlines_v2(args[0], args[1], args[2], args[3], args[4], args[5:])
    elif cmd == 'rejected': write_rejected()
    elif cmd == 'release': release(*args[:3])
    else: sys.exit(f'unknown command {cmd}')
