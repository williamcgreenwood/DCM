from dcm.runtime.host_contract import build_terminal_accounting


def test_terminal_accounting_is_complete_and_deterministic():
    rows = [{"projectionId": "b"}, {"projectionId": "a"}]

    def classify(row):
        return ("MODELED", None) if row["projectionId"] == "a" else ("UNSUPPORTED", "NO_CONTRACT")

    accounting, receipt = build_terminal_accounting(rows, classify, run_id="R1")
    assert receipt.state == "ACCOUNTED"
    assert receipt.raw_rows == receipt.terminal_rows == 2
    assert [r["projectionId"] for r in accounting["records"]] == ["a", "b"]
    assert accounting["counts"] == {"MODELED": 1, "UNSUPPORTED": 1}
