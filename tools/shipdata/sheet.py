"""Contact sheets of the render gate (T12.2, P5): per ship one row - default view old | new, view from above old | new -
hologram and racks as ShipPictureTests renders them (app D92), six ships to a sheet. Martin reads them on the draft
release (PR path) or after a red gate.

Ported from sc-ship-outlines/motherlode_sheet.py (aeb6af7, SHA-256 077b8189..., docs/provenance.md): tile size, labels
and the picture lookup are the same; new are the old/new pairs and the order given by the gate (unexpected ships first,
then the stops). A run with a baseline saves only pictures that differ, so a "new" picture it did not save is the old
run's picture."""
from pathlib import Path

import cv2
import numpy as np

TILE_W, TILE_H = 480, 360
ROWS = 6               # ships per sheet, one row each
LABEL_H = 26
VIEWS = ('fit', 'above')


def picture(folders: list[Path], ship: str, view: str) -> np.ndarray | None:
    """The first saved picture of a ship and view: hologram shaded, or the outline for a ship without hologram."""
    names = [f'{ship}.holo-shaded.800x600.{view}.png', f'{ship}.outline.800x600.{view}.png']
    for folder in folders:
        for name in names:
            path = folder / 'png' / name
            if path.exists():
                return cv2.imread(str(path), cv2.IMREAD_COLOR)
    return None


def tile(image: np.ndarray | None, text: str) -> np.ndarray:
    canvas = np.full((TILE_H + LABEL_H, TILE_W, 3), 255, np.uint8)
    if image is not None:
        canvas[LABEL_H:, :] = cv2.resize(image, (TILE_W, TILE_H), interpolation=cv2.INTER_AREA)
    else:
        cv2.putText(canvas, 'no picture', (10, LABEL_H + TILE_H // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)
    cv2.putText(canvas, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    return canvas


def sheets(ships: list[str], old: Path, new: Path, out: Path, marks: dict[str, str]) -> list[tuple[Path, list[str]]]:
    """contact-sheet-<n>.png in `out`, ships in the given order; returns each sheet with its ships."""
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for number, start in enumerate(range(0, len(ships), ROWS), 1):
        chunk = ships[start:start + ROWS]
        rows = []
        for ship in chunk:
            label = ship + (f' [{marks[ship]}]' if marks.get(ship) else '')
            cells = []
            for view in VIEWS:
                name = 'default' if view == 'fit' else view
                cells += [tile(picture([old], ship, view), f'{label} - {name}, old'),
                          tile(picture([new, old], ship, view), f'{label} - {name}, new')]
            rows.append(np.hstack(cells))
        path = out / f'contact-sheet-{number}.png'
        cv2.imwrite(str(path), np.vstack(rows))
        made.append((path, chunk))
    return made
