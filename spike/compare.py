"""spike/compare.py - question 4 of S12.0: which picture distance separates "same" from "different"? Throwaway measuring
code, numpy + cv2 (run locally with sc-ship-outlines' .venv and -I).

usage: python -I compare.py <label> <run A dir> <run B dir> [--only <ship id> | --without <ship id>]
Pairs every PNG that exists in both runs' png/ folders (a run with a baseline keeps only the pictures that differ from
it). Per pair:
  share   share of pixels with any BGRA byte different (as ViewPictures.Difference in the app's tests)
  share8  share of pixels whose largest channel difference is above 8
  ssim    SSIM of the grayscale pictures, Gaussian window 11x11, sigma 1.5, C1/C2 after Wang et al. 2004
Writes compare-<label>.csv next to this script's working directory and prints max/p99 and min/p1 of each measure.
"""
import csv, os, sys

import cv2
import numpy as np


def ssim(a, b):
    a, b = a.astype(np.float64), b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    blur = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)
    ma, mb = blur(a), blur(b)
    va, vb, cov = blur(a * a) - ma * ma, blur(b * b) - mb * mb, blur(a * b) - ma * mb
    return float((((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma * ma + mb * mb + c1) * (va + vb + c2))).mean())


def measure(pa, pb):
    a, b = cv2.imread(pa, cv2.IMREAD_UNCHANGED), cv2.imread(pb, cv2.IMREAD_UNCHANGED)
    if a is None or b is None or a.shape != b.shape:
        return None
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    gray = lambda x: cv2.cvtColor(x, cv2.COLOR_BGRA2GRAY if x.shape[2] == 4 else cv2.COLOR_BGR2GRAY)
    return float((d > 0).mean()), float((d > 8).mean()), ssim(gray(a), gray(b))


def main(label, a_dir, b_dir, *flt):
    only = flt[1] if len(flt) == 2 and flt[0] == '--only' else None
    without = flt[1] if len(flt) == 2 and flt[0] == '--without' else None
    pa, pb = os.path.join(a_dir, 'png'), os.path.join(b_dir, 'png')
    names = sorted(set(os.listdir(pa)) & set(os.listdir(pb))) if os.path.isdir(pa) and os.path.isdir(pb) else []
    names = [n for n in names if (not only or n.split('.', 1)[0] == only) and (not without or n.split('.', 1)[0] != without)]
    rows = []
    for n in names:
        m = measure(os.path.join(pa, n), os.path.join(pb, n))
        if m:
            rows.append((n, *m))
    with open(f'compare-{label}.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['picture', 'share', 'share8', 'ssim'])
        w.writerows(rows)
    print(f'{label}: {len(rows)} pairs ({a_dir} vs {b_dir})')
    if not rows:
        return
    arr = np.array([r[1:] for r in rows])
    for i, name in enumerate(('share', 'share8', 'ssim')):
        col = arr[:, i]
        print(f'  {name:6} min {col.min():.6g}  p1 {np.percentile(col, 1):.6g}  median {np.median(col):.6g}  '
              f'p99 {np.percentile(col, 99):.6g}  max {col.max():.6g}')
    print(f'  identical pixels in {int((arr[:, 0] == 0).sum())} of {len(rows)} pairs')


if __name__ == '__main__':
    main(*sys.argv[1:])
