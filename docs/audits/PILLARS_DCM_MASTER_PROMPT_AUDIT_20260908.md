# PILLARS DCM master-prompt audit

**Audit date:** 2026-09-08  
**Audited prompt:** `PILLARS_DCM_MASTER_EXECUTION_PROMPT_20260908.md`  
**Audited prompt SHA-256:** `ca4678fed616541a2cd392712ef1bb17eb6b1ae5d676c8c84edc3b5946542e12`  
**Audited prompt size:** 2,462,907 bytes; 6,289 lines; 355,743 words  
**Expanded architecture source:** `DCM_WORK_CODEX_BATCH_RESEARCH_ARCHITECTURE_20260908_EXPANDED.md`  
**Expanded source size:** 2,451,335 bytes; 6,188 lines; 354,183 words  
**Live repository:** `williamcgreenwood/DCM`  
**Live `main` verified:** `8044c459de29fe9c92db79906682fffd8dce6435`  

This audit is an implementation input. It does not claim that the DCM has completed
the 233 research tasks or 1,839 subject-offer sets.

## Executive result

The master prompt contains the right safety and architectural intent, but it is not a
reliable Work/Codex execution instruction in its current form. It is too large for a
single agent context, repeats 60 bounded-batch scenarios, names commands that are not
registered by the live CLI, embeds a historical architecture report as if it were the
current repository contract, and gives no sufficiently strict decision tree for a dirty
or stale checkout. Its strongest material should be retained as policy; its repeated
examples and stale operational assertions should be removed.

The correct replacement is a compact, repository-bound execution prompt that:

1. verifies live `main`, branch protection, open PRs, dirty state, runtime, inputs, and
   checkpoint before mutation;
2. reads every supplied source family while collapsing byte-identical duplicates;
3. treats current code, current tests, current ledgers, and verified receipts as the
   implementation truth;
4. uses the existing `dcm.chat` command surface and existing producer/consumer graph;
5. selects one bounded increment and writes a receipt before the Work/Codex run ends;
6. lets Codex execute repository code and lets Work/Deep Research supply permitted
   public-source observations only where the active surface supports that action; and
7. stops with a typed blocker instead of fabricating completion when a platform,
   approval, source, input, test, or protected-promotion boundary is unavailable.

## Evidence inventory and duplicate handling

The supplied folder includes repeated copies of several files. Repeated copies with the
same SHA-256 are one source family, not independent evidence and must not be pasted into
the execution prompt multiple times. The supplied materials were reconciled as follows.

| Supplied source | Role in the canonical design | Treatment in the replacement prompt |
|---|---|---|
| `AGENTS.md` | Standing repository authority, privacy, one-path Git, algorithm and acceptance law | Binding runtime authority; reread from live checkout |
| `PILLARS_Project_Instructions.md` | Project mission, universal DCM scope, CFB-first delivery, research and freeze invariants | Preserved as project-level constraints; current repository wins on conflict |
| `PILLARS_DCM_Work_Execution_Prompt.md` | ChatGPT-native execution boundary and host/engine split | Preserved as host contract; exact live CLI verified first |
| `PILLARS_DCM_Canonical_Main_Design(1).md` | Canonical DCM lifecycle and universal dependency chain | Preserved as semantic architecture; not treated as a list of missing modules |
| `PILLARS_DCM_Source_Annex.md` | Detailed field, algorithm, evidence, sport and acceptance requirements | Used as a requirement source; no wholesale prompt embedding |
| `PILLARS_DCM_Source_Index.json` | Source identity, hashes, and heading index | Used to identify duplicate/versioned sources and provenance |
| `02_GROK_NEXT_BUILD_IMPLEMENTATION_PROMPT(2).md` | Earlier implementation sequencing and donor integration intent | Historical implementation evidence; verify against `main` |
| `03_DONOR_COMPONENT_MATRIX(2).json` | 58-candidate donor disposition map | Candidate catalog only; no donor self-activation or copied engine |
| `08_PILLAR_ARCHITECTURE_DECISION(2).md` | One canonical package/branch and algorithm-governance decision | Preserved; superseded integration-only details are not executable |
| `DCM_P380X_GROK_DONOR_INTEGRATION_BLUEPRINT_20260831(2).docx` | Donor architecture, evidence fusion, signal governance, performance concepts | Read as candidate requirements; exact archive bytes remain unavailable |
| `PromptPillars DCM Autonomous Convergence and Finalization Implementation(4).md` | Autonomous convergence and finish-line behavior | Preserved as no-reconfirmation and receipt policy, bounded by platform controls |
| `Engineering the DCM so Grok and ChatGPT can actually finish it autonomously(4).md` | Branch/canonical-source and execution failure analysis | Preserved as failure lessons, not as current branch truth |
| `Pillars DCM Blueprint Convergence and Native Optimization Master Implementation Prompt(2).md` | Algorithm, source, feature, freeze and performance requirements | Preserved only where producer, consumer, test and lineage are explicit |
| `DCM Massive Sports Research Blueprint(4).md` | Full-board research population, reusable-entity fan-out and evidence depth | Preserved as future research scope; one bounded batch per run |
| `PILLARS_DCM_REQUIREMENT_ACCEPTANCE_LEDGER_20260907(2).json` | Requirement states and acceptance gates | Current ledger/status must be compared to ancestry and tests |
| `PILLARS_DCM_FINAL_CANONICAL_IMPLEMENTATION_PROMPT_20260907(2).md` | CFB/NFL release and implementation gates | Preserved as gate definitions; no “complete” claim without receipts |
| `PILLARS_DCM_UNIVERSAL_COMPLETION_RECOVERY_PACKAGE_20260907(2).md` | Recovery, deterministic resume, privacy and promotion package | Preserved as recovery protocol |
| `PILLARS_MASTER_BUILD_AUDIT_20260907.md` | Audit findings and unresolved boundaries | Used to select work, never trusted over live main |
| `DCM_RECONCILE_CLEAN_FINISH_PROMPT.md` | One active branch/PR, normal merge, reconciliation rules | Preserved as Git execution policy |
| `docs/prompts/CFB_ALL_SPORTS_RESEARCH_ACCEPTANCE_PROMPT.md` | CFB-first research acceptance and HAR checkpoint behavior | Preserved as operational acceptance contract |
| `docs/prompts/RESEARCH_COMPLETION_1839_ACCEPTANCE_PROMPT.md` | Full 1,839-set completion and no-fabrication rule | Preserved as terminal acceptance; not a one-run workload |
| `docs/status/checkpoints/CP-20260907-HAR-RESEARCH-FANOUT.json` | Example sanitized external-research checkpoint | Used as checkpoint shape evidence; private payload remains excluded |
| `DCM_WORK_CODEX_BATCH_RESEARCH_ARCHITECTURE_20260908_EXPANDED.md` | Prior platform and repository architecture report | Reconciled and compressed; not embedded wholesale |

The duplicated upload copies of the final prompt, recovery package, audit, architecture
report, research blueprint, autonomous prompt, and reconcile prompt have identical bytes
within their families. The duplicate ZIPs and extraction archives are also not separate
implementations. The donor DOCX explicitly describes a candidate/disposition architecture;
it does not establish exact donor archive availability.

## Measured defects in the 2.46 MB master prompt

| Finding | Evidence | Consequence | Correction |
|---|---|---|---|
| Excessive context size | 2,462,907 bytes and 6,289 lines | A single Work/Codex run must spend context on repeated policy instead of the live task | Keep policy once; reference checked-in documents and attached sources by name |
| Repeated scenario fan-out | Exactly 60 `### Scenario` blocks; 60 nearly identical bounded-batch examples | Repetition increases token use without adding a new contract or test dimension | Replace all scenario blocks with one parameterized lifecycle and a table of test axes |
| Unregistered command | `research-validate` appears 66 times; live `src/dcm/chat/cli.py` registers no such subcommand | An executor following the prompt fails or invents a command | Use `evidence-import`; add a validator only if a live gap is proven and tested |
| Unregistered command | `checkpoint` is described as a CLI action; live CLI has no `checkpoint` subcommand | The repository checkpoint is an internal/runtime artifact, not a command in the current host interface | Use the existing run/checkpoint writer and verify generated artifacts; do not invent a CLI |
| Stale status assertion | Prompt and checked-in status call NFL league-keyed parity “next”; live first-parent history shows PR #57 merged and DCM61-08 `VERIFIED` | The agent may duplicate already-merged work | Reconcile status against live ancestry, ledger, tests, and receipts before choosing work |
| Stale branch assertion | Local checkout is `codex/host-terminal-contract-20260907`, ahead 2/behind 5, dirty; live `main` is `8044c459…` | Direct work risks overwriting user changes or building on obsolete code | Use a fresh worktree from verified live `main`, or stop and preserve the dirty checkout |
| Historical path assumptions | The prompt refers to symbols and file layouts from multiple generations | An agent can add a second engine or edit a noncanonical tree | Resolve every symbol with `rg` and the current inventory before coding |
| Oversized static batch examples | The embedded report suggests example caps such as 25 entities/500 offers while also describing platform limits | Examples can be misread as a platform guarantee | Treat caps as tunable repository defaults; select by measured budget and receipt |
| Platform overreach risk | The prompt blends Work, Deep Research, scheduled tasks, connected apps and Codex into one worker | A model may assume local shell, JSONL writes, indefinite continuation, or app writes are universal | Label documented capability, implementation inference, unsupported assumption, and blocker |
| Incomplete dirty-state decision tree | The prompt has stop language but does not prescribe a safe alternate worktree and preservation check | An executor may reset, clean, stash, or write into user work | Prohibit destructive cleanup; create a separate worktree from live `main` when safe |
| Completion ambiguity | “Execute to completion” appears beside many external gates | An agent may report documentation or partial evidence as full completion | Separate software, research, operational, recovery, performance, predictive and universal states |
| Prompt/repository mismatch | The prompt asks for a new batch backbone even though live code already contains `research_bridge`, source-aware import, coverage and checkpoint/outbox modules | Duplicate abstractions and unnecessary changes | Inspect producers/consumers first; repair or test existing code |

## Live repository reconciliation

The connected repository is public `williamcgreenwood/DCM`, default branch `main`.
GitHub readback verified:

- `main` currently points to `8044c459de29fe9c92db79906682fffd8dce6435`, a verified
  merge of PR #63.
- `main` is protected and requires the `python-dcm` status check.
- There is no open pull request at audit time.
- PR #57, `feat(nfl): route research through league-keyed contracts`, is merged;
  `DCM61-08` records that CFB/NFL routing is verified.
- PR #62 added the CFB-first all-sport research acceptance prompt and sanitized
  checkpoint; PR #63 added the 1,839-set completion prompt.

The current status and handoff files on `main` still contain older values including
canonical main `3b80d1c…` and “NFL league-keyed parity is next.” Those documents are useful
historical handoff evidence but are stale relative to the current first-parent history.
The replacement prompt therefore requires status reconciliation as an explicit task. It
must not claim that the operational CFB/NFL gates are closed: the release ledger still
marks CFB and NFL operational acceptance, typed evidence provenance, reuse/resume, and
the final release receipt as partial or externally blocked.

The live CLI exposes exactly these host commands:

```text
doctor, prepare, next-research, evidence-import, coverage, forecast, report,
resume, audit, archive, settle, cfb-launch
```

The current host implementation already contains these relevant producers and consumers:

| Contract | Live producer | Live consumer/receipt |
|---|---|---|
| Batch planning | `dcm.research.batch.build_next_research_batch` | `dcm.chat.research_bridge.next_research_batch`, `host_research_batch.json` |
| Source-aware observation conversion | `dcm.research.observation_typed.observation_to_typed_claim` | `dcm.research.observation_execute.execute_source_aware_observations` |
| Import command | `dcm.chat.evidence_import.import_observations` | `evidence_bundle.jsonl`, `evidence/claims.json`, coverage and conflict files |
| Semantic completion | `dcm.research.coverage.coverage_report` / `evaluate_request` | `evidence_coverage.json`, modeling/selection gates |
| Changed descendant recompute | `dcm.research.observation_execute` | ablation, fan-out and parameter snapshot artifacts |
| Local checkpoint | `dcm.runtime.checkpoint.write_checkpoint` | `checkpoint.json`, `checkpointHash` |
| Sync intent | `dcm.runtime.checkpoint_outbox.enqueue_checkpoint_sync` | append-only `checkpoint_outbox.jsonl` |
| Remote reconciliation | `dcm.runtime.checkpoint_reconciliation.reconcile_checkpoint_outbox` | `checkpoint_reconciliation.json` |
| Resume | `dcm.chat.session.HostSession.resume` and canonical runner | deterministic resume result |

The source-aware observation input is intentionally simpler than the internal claim
schema. The host should provide `actionId`/`requestId` where available, `entityRef`,
`sourceUrl`, `sourceLabel` or `sourceId`, `publishedAt`, `retrievedAt`, optional validity
interval and state/correction metadata, `evidenceType`, and non-empty semantic `data` or
typed `claims` with field/unit/provenance entries. The host must not invent internal
reliability, freshness, source hashes, claim hashes, canonical scopes, or coverage.

## Canonical resolution of conflicts among sources

1. System/platform/privacy/approval controls remain binding.
2. The current owner request and `AGENTS.md` standing authority govern normal work.
3. Live `main`, current code, current tests, current ledger, and verified receipts outrank
   stale status prose and historical branch claims.
4. Project instructions and canonical designs define semantic invariants.
5. Donor documents provide candidate ideas and requirements, not active runtime code.

The following decisions are therefore canonical:

- One installed `src/dcm` package; no second probability engine, evidence store, or
  research scheduler.
- CFB first, NFL second, and remaining sports through universal contracts/adapters;
  research-only or unsupported routes fail closed.
- Full-board accounting precedes exclusions and presentation limits; Top-100/Top-25 are
  views, not truncation of the population.
- Evidence is source-aware, field-level, content-addressed, temporal, conflict-aware and
  imported through the host contract. Empty fields never close coverage.
- Exact/hash lookup precedes structured indexes, deterministic grouping, and bounded
  set-cover/CELF selection. Approximate retrieval may rank candidates but cannot establish
  truth.
- Checkpoint state is repository/run state, not conversation memory, Project memory,
  scheduled-task history, or a Drive folder.
- A freeze is immutable; settlement and learning are append-only and future-only.
- `LR000000`, predictive claim `NONE`, production root `false`, and host performance
  `false` remain unchanged until independent gates earn new values.

## Official platform boundary used by the replacement prompt

These are current documented facts, not repository implementation promises:

- OpenAI documents Work as a longer multi-step work surface and Codex as the software
  development surface. Desktop Codex can work with local folders, repositories, terminals
  and developer tools; local-file access depends on the allowed surface and permission.
  Source: <https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex>.
- OpenAI documents Deep Research as a feature that reasons over public web, uploaded
  files and eligible enabled apps to produce a documented report. It presents a plan that
  can be reviewed/modified and allows progress/source adjustment. This does not document
  an arbitrary local shell, DCM importer, JSONL file write, or machine-checkpoint resume.
  Source: <https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt>.
- OpenAI documents Projects as a place for chats, files, instructions and recurring or
  multi-threaded context. That is useful context, not a transactional queue or database.
  Source: <https://help.openai.com/en/articles/10169521-projects-in-chatgpt>.
- OpenAI documents scheduled tasks as one-time/recurring/event-triggered work with
  plan/workspace-dependent limits. Actions requiring approval may pause; scheduled tasks
  are not an always-on worker; active task and frequency limits apply. Source:
  <https://help.openai.com/en/articles/10291617-tasks-in-chatgpt>.
- OpenAI documents connected apps and plugins as conditional on account, provider,
  workspace, role, supported actions and approval controls. Installation does not grant
  permissions outside the connected account. Sources:
  <https://help.openai.com/en/articles/11487775-connected-apps-in-chatgpt>,
  <https://help.openai.com/en/articles/20001256-plugins-in-chatgpt-and-codex>.
- OpenAI documents Google Drive access as limited to files the connected account can
  access and to enabled/approved actions. Source:
  <https://help.openai.com/en/articles/10929079>.

The replacement prompt must never turn these facts into a guarantee of indefinite
execution, unattended app writes, exact task quotas, or automatic continuation after a
token/context/runtime boundary.

## Required replacement behavior

The optimized Work/Codex prompt must enforce this run:

```text
verify live repository and permissions
→ read sources, ledger, status, checkpoint
→ protect dirty user work and reconcile ancestry
→ choose one dependency-ready increment
→ run existing producer
→ research/import only within the returned bounded contract
→ compute semantic coverage and changed descendants
→ write/verify local checkpoint and outbox
→ run tests/inventory/policy checks
→ commit/push/PR/CI/review/merge normally if code or safe docs changed
→ read back main and report exact next action
```

It must use the current command surface. A future `research-validate` or `checkpoint`
command may be introduced only after the agent proves a missing contract, implements it
in the canonical package, adds tests and inventory, and promotes it through the normal
protected workflow. The prompt must not direct the agent to call an unregistered command.

The first live execution after the audit should reconcile stale status/handoff metadata
against the verified main ancestry and ledger. It may update public-safe documentation in
one normal PR if the mismatch is confirmed. It must not restart the private HAR or current
CFB run, fabricate NFL operational evidence, or duplicate PR #57.

## Execution record for the optimized prompt

The optimized prompt was executed from a fresh worktree based on the verified live
`main`, not from the user's dirty historical checkout. The following results are
observed execution facts, not inferred platform capabilities:

- `dcm-host --help` exposed the current command set and confirmed that
  `research-validate` and `checkpoint` are not registered commands.
- `dcm-host doctor` completed successfully and reported `PRODUCTION_ROOT_NOT_MOUNTED`,
  `LR000000`, `predictiveClaim=NONE`, `productionRootCertified=false`, and
  `hostPerformanceCertified=false`. The doctor rewrote its workspace-specific mount
  state; that generated path change was discarded and was not promoted.
- `compileall`, generated-inventory validation, policy validation and whitespace
  validation passed on the fresh worktree.
- The configured runtime does not provide `pytest`; this is recorded as
  `TEST_TOOL_UNAVAILABLE`, never as a passing test result.
- A read-only `next-research` probe against the only complete redacted repository run
  stopped at the existing readiness gate with
  `RESEARCH_MAY_BEGIN_DENIED: ResearchOSReadiness missing or false`.
- A read-only `resume` probe against that same historical run stopped because its
  checkpoint points to an unavailable historical absolute artifact root and a missing
  `board.json`. This is a stale-input/recovery blocker, not permission to recreate the
  run or upload private HAR material.
- The safe increment selected by the prompt is therefore public-safe status/handoff
  reconciliation plus the audit and Work/Codex prompt artifacts. No sports evidence,
  forecast, freeze, settlement, predictive claim, production-root certification or
  host-performance certification was created.

## Acceptance gates for the prompt itself

The improved prompt is acceptable only if a fresh Work/Codex run can answer all of these
without interpreting a 2.46 MB scenario archive:

- What is the current repo, branch, main SHA, dirty state, open PR state and required CI?
- Which exact commands exist, and which proposed commands are unsupported?
- What source files are authoritative, historical, duplicate or candidate-only?
- What is the one safe next increment after comparing live code and ledger evidence?
- How does a batch enter, exit, fail, retry and resume?
- Which observation fields are host-supplied and which fields are engine-computed?
- Where are checkpoint, outbox, claim, conflict, coverage and descendant receipts written?
- What is the exact no-fabrication result when a source, approval, test or input is absent?
- Which GitHub/Drive actions are optional and which must not block local correctness?
- How are implementation, operational, performance, recovery, predictive and universal
  statuses reported separately?

The companion file `docs/prompts/PILLARS_DCM_WORK_CODEX_EXECUTION_PROMPT_20260908.md`
is the corrected execution version produced from this audit.
