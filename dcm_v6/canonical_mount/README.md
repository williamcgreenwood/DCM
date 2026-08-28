# v5.4.1 development-copy mount

Canonical Pillars DCM v5.4.1 must remain untouched. This directory is the only
legal place a **hash-verified copy** may land.

Expected:

```
SOURCE  bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474
LEDGER  a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a
```

If those files are not in this workspace, `MOUNT_STATE.json` stays
`ABSENT_IN_THIS_WORKSPACE`. That is the honest state. Do not fabricate a decoder
and label it v5.4.1.

Drop the three canonical files into `../INBOX/` or `/workspace/attachments/`
and run:

```
PYTHONPATH=artifacts/dcm_v6_workstream_ab python3 -m dcm.runtime.mount_v541
```

A matching hash copies bytes into `v5.4.1_copy/`. A mismatch refuses the copy.
Learning Revision stays `LR000000`.
