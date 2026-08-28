"""Default workspace mount stays ABSENT until canonical bytes appear."""

from dcm.runtime.mount_v541 import EXPECTED_LEDGER, EXPECTED_SOURCE, mount_default


def test_workspace_mount_is_absent_and_expected_hashes_are_frozen():
    state = mount_default()
    assert state["expected_source_sha256"] == EXPECTED_SOURCE
    assert state["expected_ledger_sha256"] == EXPECTED_LEDGER
    assert state["state"] == "ABSENT_IN_THIS_WORKSPACE"
    assert state["har_decoder"] == "NOT_MOUNTED"
    assert state["copied"] is False
