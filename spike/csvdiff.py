"""spike/csvdiff.py - hash equality of two ShipPictureTests runs (S12.0, questions 3 and 4). Stdlib only.

usage: python csvdiff.py <label> <run A dir> <run B dir> [<ship id to leave out>]
Compares pictures.csv (key -> SHA-256 of the pixels) and values.csv (holo offset, outline hash) of the two OUT folders.
"""
import os, sys


def read(path):
    rows = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8-sig'):
            line = line.rstrip('\r\n')
            # as ShipPictureTests.Split: a value line (2 separators) is keyed by the ship id, a picture by all but the hash
            parts = line.split(';', 1) if line.count(';') == 2 else line.rsplit(';', 1)
            if len(parts) == 2:
                rows[parts[0]] = parts[1]
    return rows


def main(label, a_dir, b_dir, leave_out=''):
    out = os.environ.get('SPIKE_OUT', 'out')
    report = []
    for name in ('pictures.csv', 'values.csv'):
        a, b = read(os.path.join(a_dir, name)), read(os.path.join(b_dir, name))
        keep = lambda k: not (leave_out and k.split(';', 1)[0] == leave_out)
        keys = sorted(k for k in set(a) | set(b) if keep(k))
        equal = [k for k in keys if k in a and k in b and a[k] == b[k]]
        differ = [k for k in keys if k in a and k in b and a[k] != b[k]]
        only = [k for k in keys if (k in a) != (k in b)]
        ships = sorted({k.split(';', 1)[0] for k in differ})
        with open(os.path.join(out, 'numbers.tsv'), 'a', encoding='utf-8') as f:
            f.write(f'csvdiff.{label}.{name}.equal\t{len(equal)}\ncsvdiff.{label}.{name}.differ\t{len(differ)}\n'
                    f'csvdiff.{label}.{name}.only-one\t{len(only)}\ncsvdiff.{label}.{name}.ships\t{",".join(ships)}\n')
        report.append(f'{name}: {len(equal)} of {len(keys)} equal, {len(differ)} differ ({len(ships)} ships: '
                      f'{", ".join(ships[:12])}{"…" if len(ships) > 12 else ""}), {len(only)} in one run only')
        for k in differ[:10]:
            print(f'  differs: {k}')
    found = '; '.join(report)
    step = f'Hash comparison {label}'
    checked = f'{os.path.basename(a_dir)} vs {os.path.basename(b_dir)}{", without " + leave_out if leave_out else ""}'
    todo = 'none' if ' 0 differ' in report[0] and ' 0 in one run only' in report[0] else 'pictures differ: pixel distances in compare.py (question 4)'
    print(f'\n=== {step}\n  checked: {checked}\n  found:   {found}\n  to do:   {todo}\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(f'### {step}\n- **checked:** {checked}\n- **found:** {found}\n- **to do:** {todo}\n\n')


if __name__ == '__main__':
    main(*sys.argv[1:5])
