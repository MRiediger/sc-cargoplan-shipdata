"""Picture distance for the judge ("how much did it change?"), from spike/compare.py without SSIM: S12.0 finding 4 - the
gate itself is hash-exact, SSIM separated "same" from "different" only in the 6th decimal; the pixel share did."""
import numpy as np


def distance(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """(share, share8) of two BGRA pictures: share of pixels with any byte different (as ViewPictures.Difference in the
    app's tests), share of pixels whose largest channel difference is above 8."""
    if a.shape != b.shape:
        raise ValueError(f'picture size differs: {a.shape} vs {b.shape}')
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    return float((d > 0).mean()), float((d > 8).mean())
