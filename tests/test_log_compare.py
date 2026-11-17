"""Logger (checked / found / to do, numbers.tsv; pattern of spike/say.sh) and the judge's picture distance (spike/compare.py
without SSIM, S12.0 finding 4)."""
from pathlib import Path

import numpy as np
import pytest

from shipdata import compare
from shipdata.log import Reporter


def test_say_prints_three_lines_and_writes_the_step_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    Reporter(tmp_path / 'out').say('diff', '101 ships', '1 changed', 'none')
    printed = capsys.readouterr().out
    assert '=== diff' in printed and 'checked: 101 ships' in printed and 'found:   1 changed' in printed and 'to do:   none' in printed
    assert summary.read_text(encoding='utf-8') == '### diff\n- **checked:** 101 ships\n- **found:** 1 changed\n- **to do:** none\n\n'


def test_num_appends_to_numbers_tsv(tmp_path: Path) -> None:
    r = Reporter(tmp_path / 'out')
    r.num('fetch.api.calls', 1)
    r.num('fetch.models.unavailable', 0)
    assert (tmp_path / 'out' / 'numbers.tsv').read_text(encoding='utf-8') == 'fetch.api.calls\t1\nfetch.models.unavailable\t0\n'


def test_equal_pictures_have_distance_zero() -> None:
    a = np.zeros((4, 4, 4), np.uint8)
    assert compare.distance(a, a.copy()) == (0.0, 0.0)


def test_share_counts_any_byte_and_share8_only_above_8() -> None:
    a = np.zeros((2, 2, 4), np.uint8)
    b = a.copy()
    b[0, 0, 0] = 3       # differs, but not above 8
    b[1, 1, 2] = 200     # differs above 8
    assert compare.distance(a, b) == (0.5, 0.25)


def test_pictures_of_different_size_are_an_error() -> None:
    with pytest.raises(ValueError, match='size'):
        compare.distance(np.zeros((2, 2, 4), np.uint8), np.zeros((3, 2, 4), np.uint8))
