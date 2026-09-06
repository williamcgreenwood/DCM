import { useState } from "react";
import { AlertTriangle, CircleOff, Play, Shield, Upload } from "lucide-react";
import { runPythonDcm } from "@/lib/dcm/python-run";
import type { DcmView, SlimPick } from "@/lib/dcm/types";
import { cn } from "@/lib/utils";

const TABS = ["Integrity", "Board", "Research", "Population", "Ranked", "Card", "Freeze"] as const;
type Tab = (typeof TABS)[number];

export function OperatorConsole() {
  const [tab, setTab] = useState<Tab>("Integrity");
  const [paste, setPaste] = useState("");
  const [cutoffFromCapture, setCutoffFromCapture] = useState(true);
  const [version, setVersion] = useState("");
  const [research, setResearch] = useState<"fixture" | "file" | "bundle">("fixture");
  const [cutoff, setCutoff] = useState("");
  const [run, setRun] = useState<DcmView | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function execute(source: "synthetic" | "paste") {
    setBusy(true);
    setErr(null);
    try {
      const result = await runPythonDcm({ data: { source, paste, cutoff, cutoffFromCapture, version, research } });
      setRun(result);
      setTab(result.pythonAvailable ? "Ranked" : "Integrity");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Python DCM failed closed.");
    } finally {
      setBusy(false);
    }
  }

  const i = run?.integrity ?? {};
  return (
    <div className="min-h-dvh bg-bg text-fg" data-dcm-busy={busy ? "1" : "0"} data-dcm-has-run={run ? "1" : "0"}>
      <header className="border-b border-border px-4 py-5 sm:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="font-mono text-xs tracking-[0.18em] text-muted uppercase">Pillars · Python engine only</p>
          <h1 className="mt-1 text-3xl font-medium tracking-tight">DCM</h1>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Operator console for freeze artifacts. The browser never computes probabilities, grades, or cards.
          </p>
          <p className="mt-2 font-mono text-[11px] text-muted">
            Algorithmic Constitution DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903 · LR000000 · predictive NONE
          </p>
        </div>
      </header>
      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 sm:px-8 lg:grid-cols-[280px_1fr]">
        <aside className="h-fit rounded-xl border border-border bg-bg-elevated p-5">
          <h2 className="text-sm font-medium">Run Python</h2>
          <p className="mt-1 text-xs text-muted">Fixture research is not live evidence. Empty production card is legal.</p>
          <label className="mt-4 block text-xs font-medium text-muted uppercase">
            Forecast cutoff
            <input value={cutoff} onChange={(e) => setCutoff(e.target.value)} className="mt-1.5 h-11 w-full rounded-md border border-border bg-bg px-3 font-mono text-xs" />
          </label>
          <label className="mt-3 flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={cutoffFromCapture} onChange={(e) => setCutoffFromCapture(e.target.checked)} /> Derive cutoff from capture</label>
          <button type="button" disabled={busy} data-dcm-action="synthetic" onClick={() => void execute("synthetic")} className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-accent text-sm font-medium text-accent-fg disabled:opacity-50">
            <Play className="size-4" />
            {busy ? "Running Python…" : "Run synthetic board"}
          </button>
          <textarea value={paste} onChange={(e) => setPaste(e.target.value)} placeholder='{"log":{"entries":[...]}}' className="mt-4 min-h-28 w-full rounded-md border border-border bg-bg px-3 py-2 font-mono text-xs" />
          <button type="button" disabled={busy || !paste.trim()} onClick={() => void execute("paste")} className="mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-md border border-border text-sm disabled:opacity-40">
            <Upload className="size-4" />
            Ingest paste via Python
          </button>
          {err ? <p className="mt-3 text-xs text-danger">{err}</p> : null}
        </aside>
        <section className="min-w-0">
          {!run ? (
            <div className="rounded-xl border border-border bg-bg-elevated p-8">
              <Shield className="size-6 text-muted" />
              <h2 className="mt-4 text-xl font-medium">No Python freeze yet</h2>
              <p className="mt-2 text-sm text-muted">The browser will not model a board.</p>
              <button type="button" onClick={() => void execute("synthetic")} disabled={busy} data-dcm-action="synthetic-empty" className="mt-6 h-11 rounded-md bg-accent px-5 text-sm font-medium text-accent-fg disabled:opacity-50">
                {busy ? "Running Python…" : "Freeze synthetic via Python"}
              </button>
            </div>
          ) : (
            <>
              {!i.productionSelectionReady ? (
                <div className="mb-4 flex items-start gap-3 rounded-lg border border-border px-4 py-3">
                  <AlertTriangle className="mt-0.5 size-4 text-warn" />
                  <p className="text-sm text-muted">Production selection is blocked. Fixture P values are displayed from the Python freeze and are not authorized for a card.</p>
                </div>
              ) : null}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                {([
                  ["Raw", i.rawRows],
                  ["Modeled", i.modeled],
                  ["Goblin", i.goblins],
                  ["Unresolved", i.unresolved],
                  ["Playable", i.playable],
                  ["Prod card", i.cardSize],
                  ["Engine", run.pythonAvailable ? "PYTHON" : "DOWN"],
                ] as const).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-border px-3 py-3">
                    <div className="text-xs text-muted uppercase">{k}</div>
                    <div className="mt-1 font-mono text-lg tabular-nums">{v == null ? "—" : String(v)}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex gap-1 overflow-x-auto">
                {TABS.map((t) => (
                  <button key={t} type="button" onClick={() => setTab(t)} className={cn("h-10 shrink-0 rounded-md px-3 text-sm", tab === t ? "bg-bg-elevated text-fg" : "text-muted")}>
                    {t}
                  </button>
                ))}
              </div>
              <div className="mt-3 rounded-xl border border-border bg-bg-elevated p-4 sm:p-6">
                {tab === "Integrity" && <Integrity run={run} />}
                {tab === "Board" && <Board run={run} />}
                {tab === "Research" && <p className="text-sm text-muted">Requested {run.research.requested} · incomplete {run.research.incomplete} · {run.research.mode || "—"}. Fixture claims never authorize production.</p>}
                {tab === "Population" && <Table rows={run.population} caption="Python full_population.jsonl — Goblins extracted, never selected" />}
                {tab === "Ranked" && <Table rows={run.ranked} caption="Python top25_ranked.json — display only" />}
                {tab === "Card" && (
                  <div>
                    <h3 className="text-sm font-medium">Production card (Python)</h3>
                    <p className="mt-1 text-xs text-muted">Never padded. Empty is a legal freeze.</p>
                    {run.card.length === 0 ? (
                      <div className="mt-4 flex items-center gap-2 rounded-lg border border-border px-3 py-4 text-sm text-muted">
                        <CircleOff className="size-4" /> Empty card · legal
                      </div>
                    ) : (
                      <ol className="mt-3 space-y-2 font-mono text-xs">{run.card.map((p) => <li key={p.projectionId}>{p.player} {p.direction} {p.line} {p.market}</li>)}</ol>
                    )}
                  </div>
                )}
                {tab === "Freeze" && (
                  <pre className="max-h-96 overflow-auto rounded-lg bg-bg p-4 font-mono text-xs text-muted">{JSON.stringify({ engine: run.engine, dest: run.dest, freezeHash: run.freezeHash, dag: run.dag, schema: run.schema, mount: run.mount }, null, 2)}</pre>
                )}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function Integrity({ run }: { run: DcmView }) {
  const i = run.integrity;
  const rows: [string, string][] = [
    ["Engine", run.pythonAvailable ? "PYTHON" : "NOT MOUNTED"],
    ["Run state", String(i.runState ?? "—")],
    ["Production selection ready", String(i.productionSelectionReady ?? false)],
    ["Production research complete", String(i.productionResearchComplete ?? false)],
    ["Software researchComplete", String(i.researchComplete ?? false)],
    ["v5 decoder", String(run.mount?.harDecoder ?? i.v5Decoder ?? "NOT_MOUNTED")],
    ["Schema", String(run.schema?.state ?? i.schemaState ?? "UNVERIFIED")],
    ["Learning revision", String(i.learningRevision ?? "LR000000")],
    ["Predictive claim", String(i.predictiveClaim ?? "NONE")],
  ];
  return (
    <ul className="divide-y divide-border">
      {run.blocker ? <li className="py-2 text-sm text-danger">{run.blocker}</li> : null}
      {rows.map(([k, v]) => (
        <li key={k} className="flex justify-between gap-4 py-2 text-sm">
          <span className="text-muted">{k}</span>
          <span className="font-mono text-xs">{v}</span>
        </li>
      ))}
      {run.blockers.map((b) => (
        <li key={b.code} className="font-mono text-xs text-muted py-1">{b.code} · {b.count}</li>
      ))}
    </ul>
  );
}

function Board({ run }: { run: DcmView }) {
  if (!run.board.length) return <p className="text-sm text-muted">No board.json from Python.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="text-xs text-muted uppercase"><tr>{["Player","Mkt","Line","Offered","Mod"].map((h) => <th key={h} className="pb-3">{h}</th>)}</tr></thead>
        <tbody>
          {run.board.map((row) => (
            <tr key={row.projectionId} className="border-t border-border">
              <td className="py-2.5">{row.playerName}<div className="font-mono text-xs text-muted">{row.eventLabel}</div></td>
              <td className="font-mono text-xs">{row.market}</td>
              <td className="font-mono text-xs tabular-nums">{row.line}</td>
              <td className="font-mono text-xs text-muted">{row.offeredHigher ? "H" : "—"}/{row.offeredLower ? "L" : "—"}</td>
              <td className="font-mono text-xs">{row.modifier}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function pct(v: number | null) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function Table({ rows, caption }: { rows: SlimPick[]; caption: string }) {
  if (!rows.length) return <p className="text-sm text-muted">Python list is empty.</p>;
  return (
    <div className="overflow-x-auto">
      <p className="mb-3 text-xs text-muted">{caption}</p>
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="text-xs text-muted uppercase"><tr>{["#","Player","Pick","P","Grade","State","Selectable"].map((h) => <th key={h} className="pb-3">{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((p, idx) => (
            <tr key={p.projectionId || String(idx)} className="border-t border-border">
              <td className="py-2.5 font-mono text-xs text-muted">{p.rank ?? "—"}</td>
              <td>{p.player}<div className="text-xs text-muted">{p.event}</div></td>
              <td className="font-mono text-xs">{p.direction || "—"} {p.line ?? "—"} {p.market}</td>
              <td className="font-mono text-xs tabular-nums">{pct(p.selectedP)}</td>
              <td className="font-mono text-xs">{p.grade ?? "—"}</td>
              <td className="font-mono text-xs text-muted">{p.state || "—"}</td>
              <td className="text-xs text-muted">{p.productionSelectable ? "YES" : "NO"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
