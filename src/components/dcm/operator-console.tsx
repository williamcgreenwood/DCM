import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Download,
  FileJson,
  Lock,
  Play,
  ShieldOff,
  SquareStack,
} from "lucide-react";
import { CAPABILITIES } from "@/dcm/capabilities.ts";
import { DEMO_HAR } from "@/dcm/demo-board.ts";
import { runFromHar, verifyInstall } from "@/dcm/run.ts";
import type { DcmRun, ModeledProp } from "@/dcm/types.ts";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Tab = "qualified" | "ranked" | "population" | "accounting" | "capabilities" | "blockers";

function pct(n: number | null | undefined) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function num(n: number | null | undefined, d = 1) {
  if (n == null) return "—";
  return n.toFixed(d);
}

function GradeChip({ g }: { g: string | null }) {
  const map: Record<string, string> = {
    PLAYABLE: "bg-primary/20 text-primary",
    LEAN: "bg-brass/15 text-brass",
    PASS: "bg-surface-2 text-muted",
    TRAP: "bg-danger/15 text-danger",
  };
  if (!g) return <span className="text-muted">—</span>;
  return (
    <span className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide", map[g])}>
      {g}
    </span>
  );
}

function StateChip({ s }: { s: string }) {
  const ok = s === "MODELED";
  return (
    <span
      className={cn(
        "truncate rounded px-1.5 py-0.5 font-mono text-[10px]",
        ok ? "bg-primary/15 text-primary" : "bg-danger/10 text-danger",
      )}
    >
      {s.replaceAll("_", " ")}
    </span>
  );
}

function PropTable({ rows, showState }: { rows: ModeledProp[]; showState?: boolean }) {
  if (!rows.length) {
    return <p className="px-4 py-10 text-center text-sm text-muted">EMPTY — a legal card. Nothing padded.</p>;
  }
  return (
    <div className="w-full max-w-full overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-xs">
        <thead className="sticky top-0 bg-surface text-[10px] uppercase tracking-wider text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">Player</th>
            <th className="px-3 py-2 font-medium">Market</th>
            <th className="px-3 py-2 font-medium">Ln</th>
            <th className="px-3 py-2 font-medium">Dir</th>
            <th className="px-3 py-2 font-medium">Grade</th>
            {showState ? <th className="px-3 py-2 font-medium">State</th> : null}
            <th className="px-3 py-2 font-medium">P</th>
            <th className="px-3 py-2 font-medium">LCB</th>
            <th className="px-3 py-2 font-medium">μ</th>
            <th className="px-3 py-2 font-medium">Opp</th>
            <th className="px-3 py-2 font-medium">Why / risk</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p, i) => (
            <tr key={p.row.projectionId} className="border-t border-border/80 hover:bg-surface-2/60">
              <td className="px-3 py-2 font-mono tabular text-muted">{p.rank ?? i + 1}</td>
              <td className="px-3 py-2">
                <div className="font-medium">{p.row.playerName}</div>
                <div className="text-[10px] text-muted">
                  {p.row.team} vs {p.row.opponent} · {p.row.league}
                </div>
              </td>
              <td className="px-3 py-2">{p.row.marketLabel}</td>
              <td className="px-3 py-2 font-mono tabular">{p.row.line}</td>
              <td className="px-3 py-2 font-mono">{p.row.side}</td>
              <td className="px-3 py-2">
                <GradeChip g={p.grade} />
              </td>
              {showState ? (
                <td className="px-3 py-2">
                  <StateChip s={p.state} />
                </td>
              ) : null}
              <td className="px-3 py-2 font-mono tabular">{pct(p.selectedP)}</td>
              <td className="px-3 py-2 font-mono tabular">{pct(p.lowerBound)}</td>
              <td className="px-3 py-2 font-mono tabular">{num(p.mean)}</td>
              <td className="px-3 py-2 font-mono tabular">{num(p.opportunityMean)}</td>
              <td className="max-w-[280px] px-3 py-2 text-muted">
                <div className="truncate text-fg/90">{p.primaryReason}</div>
                <div className="truncate text-[10px]">{p.primaryRisk}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OperatorConsole() {
  const [run, setRun] = useState<DcmRun | null>(null);
  const [tab, setTab] = useState<Tab>("qualified");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("Drop a HAR or run the synthetic slate. Goblins never enter the card.");
  const fileRef = useRef<HTMLInputElement>(null);
  const started = useRef(false);
  const install = useMemo(() => verifyInstall(), []);

  async function execute(raw: unknown) {
    setBusy(true);
    try {
      const next = await runFromHar(raw);
      setRun(next);
      setTab("qualified");
      setNote(
        next.gates.BOARD_COMPLETE && next.gates.RANK_COMPLETE
          ? `Freeze ${next.integrity.freezeHash.slice(0, 18)} · ${next.integrity.playableCount} PLAYABLE · card ${next.card.length}`
          : "INCOMPLETE_CHECKPOINTED",
      );
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Run failed closed.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void execute(DEMO_HAR);
  }, []);

  async function onFile(f: File | undefined) {
    if (!f) return;
    const text = await f.text();
    try {
      void execute(JSON.parse(text));
    } catch {
      void execute(text);
    }
  }

  const i = run?.integrity;
  const tabs: { id: Tab; label: string }[] = [
    { id: "qualified", label: "Top 25 qualified" },
    { id: "ranked", label: "Top 25 ranked" },
    { id: "population", label: "Full board" },
    { id: "accounting", label: "Accounting" },
    { id: "capabilities", label: "Capabilities" },
    { id: "blockers", label: "Blockers" },
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-bg">
      <header className="border-b border-border bg-ink">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-brass">
              Pillars · LR000000 · NONE · not optimized 6.0
            </p>
            <h1 className="text-lg font-semibold tracking-tight">DCM v6 operator</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="brass"
              className="whitespace-nowrap"
              data-testid="run-dcm"
              aria-label="Run DCM"
              onClick={() => void execute(DEMO_HAR)}
              disabled={busy}
            >
              <Play className="size-4" />
              Run DCM
            </Button>
            <Button variant="outline" className="whitespace-nowrap" onClick={() => fileRef.current?.click()}>
              <FileJson className="size-4" />
              Upload HAR
            </Button>
            {run ? (
              <Button
                variant="outline"
                className="whitespace-nowrap"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(run.boardJson, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${run.integrity.runId}_board.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                <Download className="size-4" />
                board.json
              </Button>
            ) : null}
            <input
              ref={fileRef}
              type="file"
              accept=".har,.json,application/json"
              className="hidden"
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
          </div>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-[1400px] gap-4 px-4 py-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-3">
          <section className="rounded-lg border border-border bg-surface p-4">
            <h2 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">Install</h2>
            <dl className="space-y-1 font-mono text-[11px]">
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Version</dt>
                <dd>6.0.0+WSAB.HARSPINE</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">LR</dt>
                <dd>{install.learningRevision}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">v5.4.1</dt>
                <dd className="text-warn">{install.v5Source}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">v5 decoder</dt>
                <dd className="text-warn">{install.v5Decoder}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">HAR spine</dt>
                <dd>{install.harSpine}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Schema</dt>
                <dd className="text-warn">UNVERIFIED</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Lifecycle</dt>
                <dd>INTEGRATED_DEV</dd>
              </div>
            </dl>
          </section>
          <section className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
            <p className="mb-2 font-medium text-fg">Doctrine</p>
            <ul className="space-y-1.5 text-xs leading-relaxed">
              <li className="flex gap-2">
                <ShieldOff className="mt-0.5 size-3.5 shrink-0 text-danger" />
                Goblins extracted, never selected.
              </li>
              <li className="flex gap-2">
                <Lock className="mt-0.5 size-3.5 shrink-0 text-brass" />
                Offered sides only. Unknown → fail closed.
              </li>
              <li className="flex gap-2">
                <SquareStack className="mt-0.5 size-3.5 shrink-0 text-primary" />
                Every HAR row is accounted before ranking.
              </li>
              <li className="flex gap-2">
                <Check className="mt-0.5 size-3.5 shrink-0 text-primary" />
                Empty card is success. Never force six.
              </li>
            </ul>
          </section>
          <p className="px-1 font-mono text-[11px] leading-relaxed text-muted">{note}</p>
        </aside>

        <div className="min-w-0 space-y-4">
          <section className="rounded-lg border border-border bg-surface p-4">
            <h2 className="mb-3 font-mono text-[10px] uppercase tracking-wider text-muted">Run integrity</h2>
            {i ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ["Raw rows", i.rawRows],
                  ["Goblins out", i.goblinExcluded],
                  ["Modeled", i.modeledRows],
                  ["Blocked", i.blockedRows],
                  ["Events", i.uniqueEvents],
                  ["Players", i.uniquePlayers],
                  ["PLAYABLE", i.playableCount],
                  ["Card", i.cardSize],
                ].map(([k, v]) => (
                  <div key={String(k)} className="rounded-md bg-surface-2 px-3 py-2">
                    <div className="font-mono text-[10px] uppercase text-muted">{k}</div>
                    <div className="font-mono text-xl tabular">{v}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">No freeze yet. Run DCM on the synthetic HAR to produce a RUNS directory.</p>
            )}
            {i ? (
              <div className="mt-3 space-y-1 font-mono text-[10px] text-muted">
                <div>adapter {i.sourceAdapter} · parser {i.parserVersion}</div>
                <div className="break-all">HAR SHA-256 {i.harSha256}</div>
                <div className="break-all">board {i.boardHash}</div>
              </div>
            ) : null}
            {i ? (
              <div className="mt-3 flex flex-wrap gap-2 font-mono text-[10px]">
                {Object.entries(run!.gates).map(([g, ok]) => (
                  <span
                    key={g}
                    className={cn(
                      "rounded px-2 py-1",
                      ok ? "bg-primary/15 text-primary" : "bg-danger/15 text-danger",
                    )}
                  >
                    {g} {ok ? "PASS" : "OPEN"}
                  </span>
                ))}
              </div>
            ) : null}
          </section>

          <section className="overflow-hidden rounded-lg border border-border bg-surface">
            <div className="flex flex-wrap gap-1 border-b border-border p-2">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "rounded-md px-3 py-2 text-xs font-medium",
                    tab === t.id ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {!run ? (
              <p className="px-4 py-12 text-center text-sm text-muted">Waiting for a run.</p>
            ) : tab === "qualified" ? (
              <PropTable rows={run.top25Qualified} />
            ) : tab === "ranked" ? (
              <PropTable rows={run.top25Ranked} />
            ) : tab === "population" ? (
              <PropTable rows={run.population} showState />
            ) : tab === "accounting" ? (
              <ul className="divide-y divide-border">
                {Object.entries(run.accounting).map(([k, v]) => (
                  <li key={k} className="flex items-center justify-between px-4 py-2.5 text-sm">
                    <span className="font-mono text-xs text-muted">{k}</span>
                    <span className="font-mono tabular">{v}</span>
                  </li>
                ))}
              </ul>
            ) : tab === "blockers" ? (
              <ul className="divide-y divide-border">
                {run.blockers.map((b) => (
                  <li key={b.code} className="flex items-start justify-between gap-3 px-4 py-3 text-sm">
                    <div>
                      <div className="font-mono text-xs text-brass">{b.code}</div>
                      <div className="text-muted">{b.detail}</div>
                    </div>
                    <div className="font-mono tabular">{b.count}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="w-full max-w-full overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-muted">
                    <tr>
                      <th className="px-3 py-2">League</th>
                      <th className="px-3 py-2">Market</th>
                      <th className="px-3 py-2">Selection</th>
                      <th className="px-3 py-2">Reboot</th>
                      <th className="px-3 py-2">Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {CAPABILITIES.map((c) => (
                      <tr key={`${c.league}-${c.market}`} className="border-t border-border">
                        <td className="px-3 py-2 font-mono">{c.league}</td>
                        <td className="px-3 py-2">{c.market}</td>
                        <td className="px-3 py-2">
                          <StateChip s={c.productionSelection} />
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px]">{c.reboot}</td>
                        <td className="max-w-md px-3 py-2 text-muted">{c.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {run ? (
            <section className="rounded-lg border border-border bg-surface p-4">
              <h2 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">
                Card (PLAYABLE only)
              </h2>
              {run.card.length === 0 ? (
                <p className="text-sm text-muted">EMPTY CARD — valid outcome.</p>
              ) : (
                <ol className="space-y-2">
                  {run.card.map((p) => (
                    <li key={p.row.projectionId} className="flex items-center gap-3 text-sm">
                      <ChevronRight className="size-4 text-brass" />
                      <span className="font-medium">{p.row.playerName}</span>
                      <span className="text-muted">
                        {p.row.side} {p.row.marketLabel} {p.row.line}
                      </span>
                      <GradeChip g={p.grade} />
                      <span className="ml-auto font-mono tabular text-xs">{pct(p.selectedP)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          ) : (
            <section className="flex items-start gap-3 rounded-lg border border-border bg-surface p-4 text-sm text-muted">
              <AlertTriangle className="mt-0.5 size-4 text-brass" />
              Synthetic HAR is a contract fixture. It does not prove live PrizePicks compatibility or predictive skill.
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
