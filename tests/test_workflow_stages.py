"""The workflow's own stages (T12.2): version, hygiene, previous, draft, publish, heartbeat, pr. gh and git are replaced
by a recorder (shipdata.github), so these tests run without GitHub."""
import datetime as dt

import pytest

from shipdata import workflow


def rel(tag: str, draft: bool = False, latest: bool = False) -> dict:
    return {'tagName': tag, 'isDraft': draft, 'isLatest': latest}


# ---------------------------------------------------------------- version (SD4)

@pytest.mark.parametrize('tags, expected', [
    ([], 'ships-2026.11'),
    (['ships-2026.11'], 'ships-2026.11.1'),
    (['ships-2026.11', 'ships-2026.11.1'], 'ships-2026.11.2'),
    (['ships-2026.11', 'ships-2026.11.9', 'ships-2026.11.10'], 'ships-2026.11.11'),
    (['ships-2026.10', 'ships-2026.10.1', 'holo-v3'], 'ships-2026.11'),
])
def test_next_version_counts_up_within_the_month(tags: list[str], expected: str) -> None:
    assert workflow.next_version(dt.date(2026, 11, 18), tags) == expected


def test_version_key_sorts_numerically() -> None:
    tags = ['ships-2026.11.10', 'ships-2026.11', 'ships-2026.12', 'ships-2026.11.9']
    assert sorted(tags, key=workflow.version_key) == ['ships-2026.11', 'ships-2026.11.9', 'ships-2026.11.10', 'ships-2026.12']


# ---------------------------------------------------------------- previous (E1)

def test_previous_is_the_highest_published_version_not_the_latest_flag() -> None:
    """E1: the latest flag can be set by hand or left wrong by a broken hygiene step; the version decides."""
    releases = [rel('ships-2026.11.9', latest=True), rel('ships-2026.11.10'), rel('ships-2026.11.11', draft=True),
                rel('holo-v3')]
    assert workflow.pick_previous(releases) == 'ships-2026.11.10'


def test_previous_without_a_data_release_is_an_error() -> None:
    with pytest.raises(workflow.WorkflowError, match='seed'):
        workflow.pick_previous([rel('ships-2026.11', draft=True)])


# ---------------------------------------------------------------- hygiene (SD4: the last two stay)

def test_hygiene_keeps_the_last_two_published_releases() -> None:
    releases = [rel('ships-2026.10'), rel('ships-2026.11'), rel('ships-2026.11.1'), rel('ships-2026.12', draft=True),
                rel('holo-v3')]
    assert workflow.to_delete(releases) == ['ships-2026.10']


def test_hygiene_deletes_nothing_with_two_releases() -> None:
    assert workflow.to_delete([rel('ships-2026.11'), rel('ships-2026.11.1')]) == []


def test_stale_drafts_are_every_data_draft() -> None:
    releases = [rel('ships-2026.11'), rel('ships-2026.11.1', draft=True), rel('other', draft=True)]
    assert workflow.stale_drafts(releases) == ['ships-2026.11.1']
