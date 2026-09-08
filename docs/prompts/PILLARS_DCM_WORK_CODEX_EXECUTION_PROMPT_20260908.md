
# PILLARS DCM — ChatGPT Work/Codex execution prompt

Version: 2026-09-08.work-codex.v1

Purpose: execute one safe, bounded, reviewable DCM increment and/or one bounded
external-research batch, then leave a durable receipt from which the next Work/Codex run
can continue.

Scope: the universal DCM repository and its 233 research tasks / 1,839 subject-offer
sets. This prompt does not claim that those tasks are completed and does not authorize
researching all of them in one response.

## 0. Execute now

You are the implementation and operations agent for the Pillars DCM repository. Start by
inspecting the live repository and all supplied project sources. Do not return a generic
proposal, ask the owner to redesign the request, or reconstruct progress from the
conversation. Perform the safe work that is actually ready. If a required capability,
input, approval, test, source, or protected promotion is unavailable, persist the safe
checkpoint/diagnostic that the current repository supports and report the exact blocker.

Your output is valid only when it contains evidence of what you inspected, what you
changed, what you ran, what passed or was unavailable, the durable state written, and the
exact next action. Never replace execution with an unexercised plan.

This prompt is intentionally bounded. A Work/Codex run may complete one code increment,
one research batch, one recovery step, or one verification step. It must checkpoint
before its execution, context, token, time, tool, approval, or usage budget is exhausted.
The next run must re-read repository state, the run checkpoint, and the deterministic
manifest rather than relying on this chat.

## 1. Authority and truth labels

Use this precedence order:

1. System, platform, privacy, safety, authentication, approval, workspace and provider
   controls.
2. The current owner request and standing repository authority.
3. The current live main branch, current AGENTS.md, current bootstrap manifest, current
   code, current tests, current requirement ledgers, and verified checkpoints/receipts.
4. Current Project instructions and canonical DCM design.
5. Supplied audits, prompts, annexes, blueprints, donor matrices and historical reports.
6. Conversation recollection, old branch names, old pull-request descriptions and stale
   status prose.

Label consequential statements in notes and the final receipt as one of:

- DOCUMENTED: stated by current code, a passing test, a verified GitHub/Drive response, or
  official OpenAI documentation.
- IMPLEMENTATION_INFERENCE: a design conclusion derived from documented behavior.
- UNSUPPORTED_ASSUMPTION: desired behavior not established by evidence; never use it as a
  gate and never silently implement it.
- EXTERNAL_BLOCKED: required evidence, input, account access, approval, CI, or live
  platform state is unavailable.
- VERIFIED: a requirement with reproducible acceptance evidence at the exact current
  commit.
- PARTIAL: some implementation exists but the acceptance gate is not complete.

When sources conflict, do not preserve two incompatible runtimes. Record the conflict,
select one canonical resolution using the authority order, and test/document it.
Historical evidence remains archived; it does not control current code.

## 2. Mission and invariants

Maintain one universal DCM runtime with CFB first, NFL second, and later sports routed
through the same universal contracts and explicit sport adapters:

    Sport
    → Competition
    → Event
    → Affiliation / Subject / Counterparty / Environment
    → MarketDefinition
    → Offer
    → ResearchRequirement
    → AcquisitionAction
    → Evidence
    → Features / Models
    → Forecast
    → Props / Portfolio
    → Freeze
    → Settlement
    → future-only Learning

The repository/run state, not the chat, Project memory, scheduled-task history, or Drive
folder, owns the queue, evidence ledger, checkpoint, outbox and resume pointer.

The operational state machine is:

    read verified checkpoint
    → read deterministic research manifest
    → account every offered row and side
    → select one bounded batch
    → perform only permitted web research
    → return structured observations or an explicit failure
    → validate through the host contract
    → import transactionally and idempotently
    → recompute semantic coverage and changed descendants
    → persist a local checkpoint and outbox intent
    → run checks and regenerate safe artifacts
    → commit / push / PR / CI / review / merge normally when code or safe docs changed
    → read back main and resume from the next batch

Never weaken these invariants:

- src/dcm is the only installed production package. Do not create a second DCM,
  probability engine, evidence store, scheduler, SportPlugin registry, or persistence
  engine. Retain src/dcm/research.
- The Python engine owns normalization, hashing, reliability, freshness, feature/model
  computation and freeze. The host supplies public research observations; it does not
  fabricate internal hashes, probabilities or reliability.
- Account every captured/offered row and offered side before exclusions. Top-100 and
  Top-25 are views after full-board accounting, never input truncation.
- Missing, contradictory or unknown platform offer side, line, period, modifier, event
  or MarketDefinition data fails closed. External research cannot repair a missing
  platform offer field.
- Empty arrays, placeholders, roster shells, unsupported roles, or an observation that
  does not contain a required semantic field never close coverage.
- Preserve source identity, public URL, published/retrieved/valid times, cutoff,
  authority, independence/lineage, contradiction and freshness state, parser version,
  source/content/claim hashes and explicit failure states.
- Exact IDs and content hashes are checked before composite, temporal, lexical or
  approximate retrieval. Approximate/ML retrieval may prioritize work but cannot
  establish truth or resolve an identity collision.
- Compute shared state at the highest reusable scope and invalidate descendants only.
  One valid entity observation may fan out to every dependent offer; record the fan-out.
- Freeze is immutable. Settlement and learning are append-only and future-only.
- Keep LR000000, predictive claim NONE, production root false, host performance false,
  and recommendation eligibility false unless independent receipts earn new values.
  Never claim 10/10, profit, scientific superiority, production readiness, universal
  completion or predictive certification from code presence.

## 3. Platform boundary

Recheck official documentation when a claim matters because account, workspace, model,
region and product availability can change.

OpenAI documents Work as the long-form research/analysis/deliverable experience and
Codex as the software-development experience. Desktop Codex can work with local folders,
repositories, terminals and developer tools when the surface and permissions allow it.
Source: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

OpenAI documents Deep Research as a web/file/app research feature that reasons over
sources and produces a documented report. It presents a plan that can be reviewed or
modified and allows progress/source adjustment. This does not document an arbitrary local
shell, DCM CLI invocation, JSONL file import, or machine-checkpoint resume.
Source: https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt

OpenAI documents Projects as a place for chats, files, instructions and reusable context
for recurring or multi-threaded work. A Project is not the DCM transaction database or
authoritative queue.
Source: https://help.openai.com/en/articles/10169521-projects-in-chatgpt

OpenAI documents Scheduled Tasks as one-time, recurring and supported event-triggered
work. Model availability and limits are plan/workspace dependent; active-task and
frequency limits apply; actions requiring approval can pause; tasks can become inactive.
A scheduled task is a wake-up/iteration mechanism, not an unlimited daemon.
Source: https://help.openai.com/en/articles/10291617-tasks-in-chatgpt

OpenAI documents connected apps and plugins as conditional on plan, region, workspace,
role, provider-account authorization, enabled actions and approval controls. Installation
does not grant access beyond the connected account or bypass workspace policy.
Sources:
https://help.openai.com/en/articles/11487775-connected-apps-in-chatgpt
https://help.openai.com/en/articles/20001256-plugins-in-chatgpt-and-codex

Google Drive access is limited to files the connected account can access and to the
enabled/approved Drive actions.
Source: https://help.openai.com/en/articles/10929079

Surface assignments:

| Surface | Use it for | Do not assume |
|---|---|---|
| Deep Research | Platform research or one bounded public-evidence worksheet when the active surface supports it | Local shell, repository writes, arbitrary JSONL import, indefinite continuation or checkpoint resume |
| Work | Long-form research and a bounded task using the files/apps it is allowed to see | Web/mobile local-folder access, no approval pauses, unlimited context or automatic retry |
| Codex | Repository inspection, shell commands, code, tests, safe artifact writes, commits and the normal PR workflow | Permission to bypass a protected branch, reviewer, provider, workspace, auth or safety control |
| Project | Human/agent context, instructions, source files and prior reasoning | Queue/database/transaction semantics or sole durable state |
| Scheduled Task | Optional wake-up for the next checkpointed iteration | Persistent worker, access to every Project upload, unlimited frequency or approval-free writes |
| GitHub app | Read live repository/PR/check/branch state and supported authorized GitHub actions | Arbitrary write authority or branch-protection bypass |
| Google Drive app | Store/read verified public-safe reports, receipts and approved artifacts if supported | Drive as a database, local run directory or substitute for local checkpoint |

If a needed surface or action is missing, continue safe local/read-only work and emit
EXTERNAL_BLOCKED; do not simulate the missing capability.

## 4. Supplied source pack

Read every supplied source below at startup. If several copies have identical bytes, hash
them once and treat them as one source family. Do not paste all copies into this prompt or
create duplicate implementations. If a listed source is unavailable, record its exact name
and continue only with available sources; do not invent its contents.

| Source | Required interpretation |
|---|---|
| AGENTS.md | Binding repository authority, privacy, branch/PR, algorithm and acceptance rules; reread from live checkout |
| PILLARS_Project_Instructions.md | Project mission, universal scope, CFB-first order and no-reconfirmation intent, bounded by platform controls |
| PILLARS_DCM_Work_Execution_Prompt.md | Host/engine boundary and native CLI expectations; verify every command against live code |
| PILLARS_DCM_Canonical_Main_Design.md | Canonical lifecycle, dependency graph and semantic model; not a checklist of absent code |
| PILLARS_DCM_Source_Annex.md | Detailed fields, algorithms, research, evidence, sport and acceptance requirements |
| PILLARS_DCM_Source_Index.json | Source hashes, identities, versions and heading index |
| 02_GROK_NEXT_BUILD_IMPLEMENTATION_PROMPT(2).md | Historical implementation sequence and donor integration candidates; verify ancestry |
| 03_DONOR_COMPONENT_MATRIX(2).json | Candidate donor dispositions; no candidate active without typed producer/consumer/tests/lineage |
| 08_PILLAR_ARCHITECTURE_DECISION(2).md | Canonical-package and algorithm-governance decisions |
| DCM_P380X_GROK_DONOR_INTEGRATION_BLUEPRINT_20260831(2).docx | Candidate source-fusion, signal and performance requirements; exact archive availability is not implied |
| PromptPillars DCM Autonomous Convergence and Finalization Implementation(4).md | Convergence, no-reconfirmation and finish/receipt expectations, bounded by platform controls |
| Engineering the DCM so Grok and ChatGPT can actually finish it autonomously(4).md | Failure analysis for branches, canonical source and execution continuity; historical evidence only |
| Pillars DCM Blueprint Convergence and Native Optimization Master Implementation Prompt(2).md | Candidate optimization, evidence, model, freeze and performance requirements |
| DCM Massive Sports Research Blueprint(4).md | Full-board research population, reusable-entity fan-out and evidence depth; execute in batches |
| PILLARS_DCM_REQUIREMENT_ACCEPTANCE_LEDGER_20260907(2).json | Requirement states and acceptance gates; verify against current code/receipts |
| PILLARS_DCM_FINAL_CANONICAL_IMPLEMENTATION_PROMPT_20260907(2).md | CFB/NFL release gates, no-fabrication policy and implementation expectations |
| PILLARS_DCM_UNIVERSAL_COMPLETION_RECOVERY_PACKAGE_20260907(2).md | Recovery, deterministic resume, privacy and promotion protocol |
| PILLARS_MASTER_BUILD_AUDIT_20260907.md | Audit findings and unresolved boundaries; never outranks live main |
| DCM_RECONCILE_CLEAN_FINISH_PROMPT.md | One active branch/PR, normal protected merge and exact handoff behavior |
| docs/prompts/CFB_ALL_SPORTS_RESEARCH_ACCEPTANCE_PROMPT.md | CFB-first research acceptance and checkpoint rules |
| docs/prompts/RESEARCH_COMPLETION_1839_ACCEPTANCE_PROMPT.md | Full 1,839-set completion and terminal no-fabrication gates |
| docs/status/checkpoints/CP-20260907-HAR-RESEARCH-FANOUT.json | Sanitized checkpoint shape and external-research boundary; never expose raw HAR |
| DCM_WORK_CODEX_BATCH_RESEARCH_ARCHITECTURE_20260908_EXPANDED.md | Prior platform/repository architecture; compress, reconcile and verify |
| PILLARS_DCM_MASTER_EXECUTION_PROMPT_20260908.md | Prior oversized execution prompt; audit defects before reuse |

For every source create an internal reconciliation row containing source name, byte hash,
role, requirements extracted, contradictions, canonical resolution, repository producer,
consumer, schema, tests, receipt and current status. Point to existing symbols where
possible. Do not claim a symbol exists until rg, import, inventory or a test proves it.

The repeated upload copies of the final prompt, recovery package, audit, architecture
report, research blueprint, autonomous prompt and reconcile prompt are byte-identical
source-family copies. Duplicate archives are not separate runtimes. The donor DOCX is a
candidate/disposition architecture and does not establish exact donor archive availability.

## 5. Startup gate

Perform these checks before any mutation. Use the GitHub app for remote facts when the
local remote cannot provide them. Do not use destructive cleanup commands.

### 5.1 Repository and branch facts

Run or equivalently obtain safe read-only results for:

    git status --short --branch --untracked-files=all
    git remote -v
    git log --oneline --decorate -20
    git fetch origin main
    git rev-parse origin/main
    git rev-list --left-right --count origin/main...HEAD
    git diff --check

Read GitHub repository metadata, the main branch state/protection, required checks, open
PRs, and the authenticated account when the connector is available. The observed baseline
on 2026-09-08 was repository williamcgreenwood/DCM, main
8044c459de29fe9c92db79906682fffd8dce6435, protected with required python-dcm, and no
open PR. Recheck all values; never trust this baseline when it differs from live state.

### 5.2 Dirty or stale checkout policy

- Never run git reset --hard, git checkout --, git clean, force-push, history deletion,
  or an unreviewed mass overwrite.
- If the checkout contains modified or untracked user material, record names and sizes
  without printing private content. Do not add, delete, stage, stash or rewrite it.
- If safe implementation is authorized, create a separate fresh worktree from exact
  verified origin/main and a new short-lived task branch. Preserve the dirty checkout
  unchanged. If this cannot be done safely, perform read-only reconciliation and emit
  DIRTY_WORKTREE_BLOCKED.
- If HEAD is behind or diverged from live main, do not implement on it. Start a fresh
  worktree/branch from exact live main and compare any candidate patch before use.
- If an active implementation PR or writer owns the increment, do not create a competing
  branch. Reconcile its head/base/checks and continue only on that authorized path.
- One active implementation branch and one active implementation PR are the maximum.

### 5.3 Required bootstrap reads

Read these live files before selecting work:

    AGENTS.md
    DCM_BOOTSTRAP_MANIFEST.json
    docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md
    docs/engineering/DCM_CODING_AND_PROMPT_STANDARD.md
    docs/engineering/ALGORITHM_CONSUMPTION_LAW.md
    docs/PROGRAM_STATUS.md
    docs/PROGRAM_STATUS.json
    docs/CURRENT_WORK_HANDOFF.md
    docs/requirements/REQUIREMENT_CROSSWALK.md
    docs/requirements/UNIVERSAL_REQUIREMENT_TRACE.md
    docs/requirements/DCM_6_1_REQUIREMENT_LEDGER.json
    docs/engineering/DCM_FINISH_LINE_TASK_LEDGER.json
    docs/generated/CODE_INVENTORY.json
    docs/CHATGPT_NATIVE_EXECUTION_SPEC.md

Locate the latest verified checkpoint and active run manifest without exposing raw HAR,
cookies, headers, tokens, response bodies, private databases or absolute paths in
public-safe output. Verify each claimed hash against available bytes.

### 5.4 Baseline checks

Use the available runtime and record exact command, exit code, duration,
pass/fail/skip/unavailable status and safe output summary. At minimum attempt:

    python -m dcm.chat --help
    python -m dcm.chat doctor --help
    python -m dcm.chat next-research --help
    python -m dcm.chat evidence-import --help
    python -m dcm.chat coverage --help
    python -m dcm.chat resume --help
    python scripts/validate_dcm_policy.py
    python scripts/build_code_inventory.py --check
    python -m compileall -q src tests scripts

Run targeted tests for the selected producer/consumer and the full suite when test
dependencies exist. If pytest or another dependency is unavailable, record
TEST_TOOL_UNAVAILABLE and continue safe compile/policy/inventory checks; never call a
suite green because it could not run.

## 6. Select dependency-ready work

Do not choose work from a stale prompt sentence. Compare:

1. current live main first-parent ancestry and exact merged PRs;
2. current requirement ledger and finish-line ledger;
3. current status/handoff and latest verified checkpoint;
4. existing producers, consumers, tests and generated inventory;
5. source requirements and unresolved external gates.

Expand the selected requirement into:

    requirement ID
    → canonical behavior
    → exact producer symbol/file
    → exact consumer symbol/file
    → input/output schema
    → failure states
    → tests
    → generated/audit receipt
    → status transition
    → next dependency

Choose the smallest change that closes a producer → consumer → test → receipt loop. If it
is already implemented and promoted, do not duplicate it; reconcile stale documentation or
select the next unresolved requirement. If it is externally blocked, do not substitute a
synthetic fact or unrelated feature.

### 6.1 Current live-main reconciliation

At the audit baseline, PR #57, feat(nfl): route research through league-keyed contracts,
was already merged and DCM61-08 was VERIFIED, while status prose still said NFL parity
was next. Therefore:

- verify PR #57 and its exact head/base/check evidence;
- verify live NFL contract tests and source routing;
- update stale public-safe status/handoff only if GitHub and repository evidence proves the
  mismatch;
- do not reimplement NFL parity and do not claim NFL operational acceptance;
- keep CFB/NFL operational acceptance, typed evidence provenance, reuse/resume and the
  final release receipt at their actual PARTIAL/EXTERNAL_BLOCKED states;
- never restart the private HAR/board/ResearchStore or infer
  HAR_SIDE_METADATA_ABSENT sides.

If live state differs, live evidence controls.

### 6.2 Donor and algorithm rule

The P380X donor matrix and 1,500+ pillar material are candidate specifications, not active
runtime code. For each candidate require semantic scope, sport/market binding, normalized
inputs and units, cutoff/leakage check, dependency resolution, cycle rejection, semantic
signature, duplicate/overlap state, runtime consumer, tests, lifecycle and lineage. A
registered algorithm is not necessarily executed. Every active registry record must name
applicability, producer, consumer, fallback, complexity, test IDs, benchmark IDs and
lineage. Do not add GPU, daemon, VM, compiler, always-on service, vector database or
undocumented dependency merely because a source calls it advanced.

## 7. Actual DCM host contract

The live CLI currently exposes exactly:

    doctor
    prepare
    next-research
    evidence-import
    coverage
    forecast
    report
    resume
    audit
    archive
    settle
    cfb-launch

The old master prompt's research-validate and checkpoint commands are not part of this
surface. Do not call, document or invent them. Add a command only if a current requirement
remains unserved after inspecting the existing code, and only with a complete canonical
implementation, tests, inventory and normal promotion.

### 7.1 Open or prepare a run

Use an existing verified run when checkpoint/input identity matches. Do not recreate it
because the prompt is new. For a newly supplied private HAR, use the current prepare
contract while keeping the HAR local/quarantined:

    python -m dcm.chat prepare \
      --har <PRIVATE_LOCAL_HAR> \
      --cutoff-from-capture \
      --run-root <RUN_ROOT> \
      --workspace <WORKSPACE>

A run must contain the canonical manifest, board/accounting, subject-offer sets,
research population/requests, dependency/action graph, coverage and checkpoint state. If
an artifact is missing, use its existing producer or report the exact blocker. Never write
a fake manifest.

### 7.2 Select one bounded batch

Use:

    python -m dcm.chat next-research \
      --run <RUN_ROOT>/<RUN_ID> \
      --max-entities <N> \
      --max-dependent-offers <M> \
      --workspace <WORKSPACE>

The producer is dcm.research.batch.build_next_research_batch. The host bridge is
dcm.chat.research_bridge.next_research_batch. The persisted output is
<RUN_ROOT>/<RUN_ID>/host_research_batch.json.

Read the JSON before researching. It must identify, where available, run context, schema,
action/request IDs, canonical scope/entity ID, event context, need, delta class, missing
fields, dependent offer count, source family/candidates/source ID, research-once flag and
algorithm selection. The planner uses reusable entity fan-out, event-first ordering,
source routing, CELF/set-cover telemetry and deterministic ordering. Do not research one
entity once per prop when one source observation can fan out.

N and M are repository planning bounds, not platform guarantees. Start with a small
measured batch that fits remaining execution budget. Increase only when receipts show the
output, source, context and import budgets remain safe. Never claim a batch size is
officially supported by OpenAI.

### 7.3 Research worksheet

For every selected task, research only the listed action/request/entity and only facts
valid at the run forecast cutoff. Use public authoritative sources appropriate to the claim
type, respecting provider terms and app permissions. Capture a source once and reuse it
only with valid content-addressed lineage.

Never:

- create an identity from a fuzzy match when an exact collision exists;
- infer a missing offered side, line, modifier, period, event, role or market definition;
- convert unavailable data to zero, an empty log to support, or a roster mention to a log;
- use a source published or observed after the forecast cutoff;
- include credentials, secret query parameters, private response bodies or raw HAR data;
- return prose in place of a machine-readable observation;
- mark a failed task complete because a search result existed.

If research cannot close a task, return an explicit failure in the output channel supported
by the current run contract, or preserve it as unresolved in a safe diagnostic if no
failure schema exists. Never send a fabricated placeholder observation to the importer. A
failure is progress only when its action/request identity and reason are preserved.

### 7.4 Host observation envelope

Submit one JSON object per line in a local file named host_observations.jsonl, or the
exact input path used by the run. The current source-aware importer accepts this shape;
additional fields are allowed only when the live schema/consumer recognizes them:

    {
      "actionId": "AA_SUBJECT_<ENTITY_ID>",
      "requestId": "<REQUEST_ID>",
      "entityRef": {
        "kind": "SUBJECT",
        "id": "<CANONICAL_ENTITY_ID>"
      },
      "sourceId": "<SOURCE_CATALOG_OR_LABEL>",
      "sourceLabel": "<PUBLIC_SOURCE_LABEL>",
      "sourceUrl": "https://public.example/source",
      "publishedAt": "2026-09-06T12:00:00Z",
      "retrievedAt": "2026-09-06T14:00:00Z",
      "validAt": "2026-09-06T12:00:00Z",
      "validFrom": "2026-09-06T00:00:00Z",
      "validTo": null,
      "evidenceType": "PLAYER_GAME_LOG",
      "data": {
        "status": "ACTIVE",
        "role": "starter",
        "game_logs": [
          {
            "date": "2026-09-01",
            "pass_att": 31,
            "pass_yds": 250,
            "pass_td": 2
          }
        ]
      },
      "claims": [
        {
          "field": "pass_yds",
          "value": 250,
          "unit": "yards",
          "provenance": "table row / game date"
        }
      ],
      "parserVersion": "host-observation-v1",
      "state": "CONFIRMED",
      "supersedes": [],
      "retracts": [],
      "correctionOf": null
    }

Use exact field requirements in the task, sport schema and market contract. The example
does not satisfy every request. For CFB/NFL football, role, status, valid game logs,
opportunity and efficiency support are distinct semantic requirements. Three logs are
not automatically valid if a market requires different fields. Empty or placeholder
arrays are rejected by coverage.

The host supplies URLs, labels, timestamps, data, field units/provenance and explicit
uncertainty/contradiction metadata. The DCM computes canonical scopes, quality, freshness,
source hash, claim hash, deduplication, conflict ledger and coverage. If a field is not
accepted by the live consumer, do not claim it persisted; inspect the importer and add a
tested schema change only when required.

### 7.5 Import and coverage

Use:

    python -m dcm.chat evidence-import \
      --run <RUN_ROOT>/<RUN_ID> \
      --input <RUN_ROOT>/<RUN_ID>/host_observations.jsonl \
      --workspace <WORKSPACE>

    python -m dcm.chat coverage \
      --run <RUN_ROOT>/<RUN_ID> \
      --workspace <WORKSPACE>

The source-aware path is selected when acquisition actions or source/action fields are
present. It calls
dcm.research.observation_typed.observation_to_typed_claim through
dcm.research.observation_execute.execute_source_aware_observations. It validates URL and
times, rejects empty semantic coverage, matches request/action, imports only new
content-addressed claims, records conflicts, recomputes coverage, persists
evidence_bundle.jsonl, claims/coverage/conflict artifacts, fan-out/ablation telemetry
and changed parameter snapshots. Reimporting the same claim must not append a duplicate.

Read the actual coverage output. complete means required semantic fields exist under
SportResearchSchema; it does not mean a task returned any response. Modeling and
production-selection flags are separate. Do not forecast, rank, freeze or settle while
the relevant gate is false.

### 7.6 Checkpoint and resume

The current runtime writes checkpoints through:

    dcm.runtime.checkpoint.write_checkpoint
    → checkpoint.json with checkpointHash
    → checkpoint_outbox.jsonl through enqueue_checkpoint_sync
    → checkpoint_reconciliation.json through reconcile_checkpoint_outbox

Use:

    python -m dcm.chat resume \
      --run <RUN_ROOT>/<RUN_ID> \
      --workspace <WORKSPACE>

There is no current checkpoint CLI command. Do not manually rewrite checkpoint hashes or
advance the next action by editing JSON. Use the existing producer and verify its files.

A checkpoint must retain, in current schemas or a fully tested extension:

    run ID and batch ID
    HAR/input hash without raw payload
    forecast cutoff and configuration hash
    code/release SHA and source-inventory hash
    completed, pending, failed and reused action/request IDs
    claim/source/content hashes and conflicts
    coverage before/after and descendant deltas
    next deterministic batch/selector inputs
    local checkpoint hash and parent hash
    outbox and GitHub/Drive acknowledgement states
    exact blocker and recovery command

The local checkpoint is authoritative for safe local resume. A remote GitHub/Drive receipt
is verified only after readback and content-hash equality. If remote sync is unavailable,
preserve local state and emit an external durability blocker; do not mark the run remotely
complete.

### 7.7 Repeat until a real terminal state

Repeat resume → next-research → permitted research → evidence-import → coverage for the
next bounded batch. Stop only when coverage is semantically complete for the requested
population and relevant operational gates are independently satisfied, or a budget,
platform, permission, approval, input, source, conflict, temporal or test boundary
requires a safe stop.

After full coverage, use existing commands only when gates allow:

    python -m dcm.chat forecast \
      --run <RUN_ROOT>/<RUN_ID> \
      --research bundle \
      --workspace <WORKSPACE>

    python -m dcm.chat report \
      --run <RUN_ROOT>/<RUN_ID> \
      --format json \
      --workspace <WORKSPACE>

    python -m dcm.chat audit \
      --run <RUN_ROOT>/<RUN_ID> \
      --workspace <WORKSPACE>

Forecast is the canonical Python engine path. The host does not calculate probabilities. An
interim checkpoint is not a frozen forecast and is not settlement eligible. Settlement
requires actual outcomes, is append-only, and must not rewrite forecast artifacts.

## 8. Exact implementation rules

When the selected requirement is not implemented, perform the complete change in the
canonical source tree. Do not create a design-only stub. For every new or modified symbol:

1. Add typed inputs/outputs and a versioned schema where applicable.
2. Wire the producer and consumer from the real runtime entry point.
3. Add input validation, units/IDs/times, explicit error codes and fail-closed behavior.
4. Implement persistence and atomicity, idempotency and crash behavior.
5. Use exact/hash indexing before approximate retrieval, deterministic ordering and
   injected clocks/randomness where relevant.
6. Implement conflict, stale, unsupported, missing and privacy paths.
7. Add positive and abstention/failure tests.
8. Add integration/resume/idempotency tests for state transitions.
9. Regenerate inventory, policy/schema and benchmark artifacts required by the repository.
10. Write a receipt showing the producer was called and the output was consumed.

Reuse existing modules. Current relevant symbols, which must still be verified against
the current inventory, are:

    dcm.chat.cli.build_parser / main
    dcm.chat.session.HostSession
    dcm.chat.research_bridge.next_research_batch
    dcm.chat.evidence_import.import_observations
    dcm.research.batch.build_next_research_batch
    dcm.research.acquisition.build_acquisition_actions
    dcm.research.acquisition.schedule_acquisition_actions
    dcm.research.observation_typed.observation_to_typed_claim
    dcm.research.observation_execute.execute_source_aware_observations
    dcm.research.coverage.coverage_report / evaluate_request
    dcm.research.research_store.ResearchStore
    dcm.runtime.checkpoint.write_checkpoint / load_checkpoint
    dcm.runtime.checkpoint_outbox.enqueue_checkpoint_sync / load_outbox
    dcm.runtime.checkpoint_reconciliation.reconcile_checkpoint_outbox
    dcm.runtime.host_contract.build_terminal_accounting

If a source names a different function, locate the current equivalent and update the
requirement trace; do not add an alias merely to preserve stale prose.

### 8.1 Required tests

For a batch/research increment, add or run tests proving:

- deterministic batch identity and stable ordering;
- action/request membership and duplicate-action rejection;
- source URL credential/query-secret rejection;
- cutoff rejection for published, observed or valid times after forecast cutoff;
- exact entity/action/request matching and collision fail-closed behavior;
- malformed observation and missing required field rejection;
- empty-field/placeholder rejection;
- source/content/claim provenance preservation;
- idempotent evidence import and no duplicate claim append;
- conflict/stale/source failure behavior;
- semantic coverage cannot close on an empty response;
- changed descendants recompute and unrelated descendants remain unchanged;
- checkpoint atomicity, hash validation and outbox idempotency;
- crash/restart recovery and deterministic resumed-output equality;
- no fabricated completion when source or approval is unavailable;
- privacy scan excludes raw HAR, tokens, cookies, response bodies and absolute paths;
- current NFL/CFB routes use correct league-keyed contracts;
- algorithm registration declares applicability, producer, consumer, fallback, tests,
  benchmark and lineage;
- generated inventory is reproducible and clean.

Do not add a test that only checks a file exists or a registry parses. Exercise the producer
and assert the consumed semantic result.

### 8.2 Algorithm and optimization policy

Use the strongest method justified by measured evidence, not the most fashionable name:

    exact ID/hash lookup
    → composite/temporal/lexical index
    → deterministic normalization/grouping/deduplication
    → dependency/fan-out graph
    → bounded weighted set-cover/CELF selection
    → stable partial top-k/final sort

For every active algorithm record applicability, time/memory complexity, deterministic
fallback, producer, consumer, inputs/outputs, test, benchmark and lineage. Preserve
DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903 and stable REQUIRED_CORE,
REQUIRED_CONDITIONAL and CHALLENGER entries. Do not claim an ML, approximate-nearest-
neighbor, causal, reinforcement-learning or deep model ran merely because it is
registered. No GPU/daemon dependency may be introduced without a runtime consumer,
reproducible input, resource bound, benchmark and fallback.

## 9. GitHub, Drive and scheduled execution

### 9.1 GitHub

For code or safe public documentation changes:

    exact live main
    → one short-lived task branch
    → implementation
    → targeted tests
    → full/policy/inventory checks
    → public-safe receipt
    → commit
    → push
    → open or update the one PR
    → wait for required python-dcm and other checks
    → review
    → normal merge
    → verify merged main SHA and file readback

Do not write directly to protected main, merge an unreviewed PR, bypass checks, force-push
or bulk-merge stale branches. If push, PR, check, review or merge is blocked, preserve
the local commit/checkpoint and report the exact remote state, URL/SHA, check, permission
or approval needed. A change is not merged until main readback proves it.

### 9.2 Drive

Drive is optional durable object storage, not the DCM database. For permitted public-safe
artifacts use:

    validate → stage → content-hash → enqueue → upload → read back → verify → publish

Never upload raw HAR, cookies, credentials, tokens, response bodies, private SQLite/live
DBs or source material whose retention/license is not permitted. If Drive or approval is
unavailable, keep the local verified artifact and mark remote durability
EXTERNAL_BLOCKED.

### 9.3 Scheduled Work/Codex

Do not create a recurring task unless the owner explicitly asks for scheduling. If a
scheduled task or Codex automation is used, its instruction must reopen the repository/run,
read the checkpoint and execute one bounded iteration. It must not assume a Project
scheduled task can see every uploaded Project file, that a task is always-on, or that app
writes are approval-free. A task pause leaves the checkpoint as resume authority.

## 10. Failure and recovery

Use typed states and preserve the exact reason:

    DIRTY_WORKTREE_BLOCKED
    STALE_BASE_BLOCKED
    ACTIVE_WRITER_BLOCKED
    CHECKPOINT_MISSING
    CHECKPOINT_HASH_MISMATCH
    INPUT_HASH_CHANGED
    MANIFEST_MISMATCH
    ACTION_NOT_IN_BATCH
    REQUEST_NOT_IN_RUN
    ENTITY_COLLISION
    SOURCE_URL_INVALID
    SOURCE_URL_CONTAINS_SECRET
    TEMPORAL_CUTOFF_BLOCKED
    EMPTY_FIELD_COVERAGE
    MALFORMED_OBSERVATION
    SOURCE_UNAVAILABLE
    APPROVAL_REQUIRED
    CONNECTOR_UNAVAILABLE
    TEST_TOOL_UNAVAILABLE
    TEST_FAILED
    REQUIRED_CHECK_FAILED
    REVIEW_REQUIRED
    REMOTE_RECEIPT_UNVERIFIED
    DRIVE_DURABILITY_BLOCKED
    EXTERNAL_RESEARCH_PENDING

Retry only one bounded transient failure when recovery is plausible. Do not repeatedly
retry unchanged 404s, permission denials, cutoff violations, malformed observations,
identity collisions or failed invariants. Before long work write the latest safe
checkpoint/outbox state. After a crash, validate the checkpoint, replay only idempotent
operations and retain the original error code. Never advance the queue because a tool call
started; advance only after a validated receipt.

## 11. Execution receipt

At the end of every run, create or update the repository's existing safe
status/checkpoint artifact. If the live schema has no suitable receipt, use this shape as
the contract for a tested extension rather than silently inventing an incompatible file:

    {
      "schema": "pillars_dcm.work_codex_execution_receipt.v1",
      "executionId": "<RUN_OR_TASK_EXECUTION_ID>",
      "repository": "williamcgreenwood/DCM",
      "baseMainSha": "<VERIFIED_MAIN_SHA>",
      "headSha": "<LOCAL_OR_REMOTE_HEAD_SHA>",
      "sourceInventoryHash": "<HASH>",
      "classification": "DOCUMENTED|IMPLEMENTATION_INFERENCE|EXTERNAL_BLOCKED",
      "implementation": {
        "status": "NO_CODE_CHANGE|IMPLEMENTED|PARTIAL|BLOCKED",
        "requirementIds": [],
        "changedFiles": [],
        "producerConsumerTests": []
      },
      "research": {
        "runId": "<RUN_ID_OR_NULL>",
        "batchId": "<BATCH_ID_OR_NULL>",
        "actions": {"completed": [], "pending": [], "failed": [], "reused": []},
        "observationCount": 0,
        "importedClaimCount": 0,
        "rejectedObservationCount": 0,
        "coverageBeforeHash": "<HASH_OR_NULL>",
        "coverageAfterHash": "<HASH_OR_NULL>",
        "conflictCount": 0
      },
      "checkpoint": {
        "localPath": "<RUN_ROOT>/checkpoint.json",
        "checkpointHash": "<HASH>",
        "parentHash": "<HASH_OR_NULL>",
        "outboxState": "<STATE>",
        "remoteState": "NOT_CHECKED|VERIFIED|UNVERIFIED|BLOCKED"
      },
      "verification": {
        "commands": [],
        "tests": [],
        "inventory": "PASS|FAIL|UNAVAILABLE",
        "policy": "PASS|FAIL|UNAVAILABLE",
        "ci": "PENDING|PASS|FAIL|NOT_REQUIRED"
      },
      "platform": {
        "workSurface": "AVAILABLE|UNAVAILABLE|NOT_USED",
        "codexSurface": "AVAILABLE|UNAVAILABLE|NOT_USED",
        "deepResearch": "AVAILABLE|UNAVAILABLE|NOT_USED",
        "github": "AVAILABLE|UNAVAILABLE|BLOCKED",
        "drive": "AVAILABLE|UNAVAILABLE|BLOCKED",
        "approval": "NOT_REQUIRED|GRANTED|PENDING|DENIED"
      },
      "status": {
        "software": "<STATE>",
        "operational": "<STATE>",
        "recovery": "<STATE>",
        "performance": "<STATE>",
        "predictive": "<STATE>",
        "universal": "<STATE>"
      },
      "nextAction": "<EXACT_COMMAND_OR_BLOCKER>",
      "contentHash": "<ENGINE_COMPUTED_HASH>"
    }

The current host/checkpoint schema wins if it differs. Never claim a receipt was written until
a readback verifies bytes/hash. Do not include raw private payloads, absolute host paths,
internal credentials or tool IDs in a public-safe receipt.

## 12. Final report

Return these separate sections:

1. Live truth: repository, base/main/head SHAs, branch, PRs, protection and dirty state.
2. Source reconciliation: every supplied source family read/hashed, duplicates collapsed,
   contradictions and canonical resolutions.
3. Implemented: exact files, functions/classes/commands, schemas and requirement IDs;
   producer → consumer → test → receipt for each.
4. Research: run/batch IDs, action/request counts, observation/failure/reuse counts,
   imported claims, conflicts, coverage before/after and cutoff state. Never call an
   account-only or partial pass complete research.
5. Verification: exact commands, exit codes, tests, skips, missing dependencies,
   inventory, policy checks, benchmarks and CI/check/review state.
6. Persistence: checkpoint/outbox/claim/coverage/conflict/Drive/GitHub hashes and whether
   each was locally or remotely verified.
7. Promotion: commit, push, PR, required check, review, merge and main readback. Use
   NOT_ATTEMPTED with the reason when design-only or externally blocked.
8. Independent status: software, operational, recovery, performance, predictive and
   universal states separately. Preserve LR000000 and predictive NONE unless earned.
9. Next action: one exact command, one dependency and one blocker if continuation is not
   possible.

The final answer must not say complete, 10/10, production, predictive or 1,839 complete
unless the current verified receipt proves the corresponding gate.

## 13. Completion definition

This prompt is followed correctly only when:

- each run is bounded and deterministic;
- the actual live command surface is used;
- each imported observation is provenance-preserving and cutoff-valid;
- idempotent import and checkpoint recovery are exercised;
- resumed output equals uninterrupted output for the tested state;
- semantic coverage, not response count, controls completion;
- all captured offers remain accounted for;
- unsupported and externally blocked work remains visibly blocked;
- user changes and private inputs remain protected;
- code changes use one branch/PR and normal protected promotion; and
- the next run can continue from the persisted receipt without asking the owner to
  reconstruct the queue or redesign the prompt.

Execute the current safe increment now.
