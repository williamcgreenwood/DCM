# INBOX

Put one current PrizePicks or Outlier HAR here as `current.har`.

Raw HAR never ships in the canonical release. Cookies, Authorization,
Set-Cookie, CSRF, access/refresh tokens, session and device ids are redacted
from every persisted artifact.

Optional canonical drop (hash-verified copy only):

- `Pillars_DCM_v5.4.1_COMPLETE_PROJECT_SOURCE.txt`
- `Pillars_DCM_v5.4.1_Learning_Ledger.xlsx`
- `Pillars_DCM_v5.4.1_INSTALL_SHA256.txt`

Command:

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runtime.har_run --inbox dcm_v6/INBOX/current.har --out dcm_v6/RUNS
```

`--synthetic` runs the contract fixture. That does not prove live HAR compatibility.
