import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { pythonUnavailable, viewFromPythonArtifacts } from "./artifact-reader";
import type { DcmView } from "./types";

function resolvePythonPkg(fs: typeof import("node:fs"), path: typeof import("node:path")): string | null {
  const candidates = [
    path.resolve(process.cwd(), "artifacts/dcm_v6_workstream_ab"),
    "/workspace/DCM/artifacts/dcm_v6_workstream_ab",
    "/workspace/artifacts/dcm_v6_workstream_ab",
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "dcm", "runner.py"))) return c;
  }
  return null;
}

function parseDest(stdout: string): string {
  const start = stdout.lastIndexOf("{");
  if (start < 0) return "";
  try {
    const obj = JSON.parse(stdout.slice(start)) as { dest?: string };
    return String(obj.dest || "");
  } catch {
    return "";
  }
}

export const runPythonDcm = createServerFn({ method: "POST" })
  .validator(
    z.object({
      source: z.enum(["synthetic", "paste"]),
      paste: z.string().optional(),
      cutoff: z.string().optional(),
      cutoffFromCapture: z.boolean().optional(),
      version: z.string().optional(),
      research: z.enum(["fixture", "file", "bundle"]).optional(),
    }),
  )
  .handler(async ({ data }): Promise<DcmView> => {
    const { spawnSync } = await import("node:child_process");
    const fs = await import("node:fs");
    const os = await import("node:os");
    const path = await import("node:path");

    const pkg = resolvePythonPkg(fs, path);
    if (!pkg) {
      return pythonUnavailable("Canonical Python DCM is not mounted in this host.");
    }

    const workspace = fs.existsSync("/workspace/DCM/pyproject.toml")
      ? "/workspace/DCM"
      : fs.existsSync("/workspace/pyproject.toml")
        ? "/workspace"
        : process.cwd();
    const outRoot = process.env.DCM_RUNS_DIR || "/tmp/dcm_v6/RUNS";
    fs.mkdirSync(outRoot, { recursive: true });
    const args = [
      "-m",
      "dcm.runner",
      "--research",
      data.research || (data.source === "synthetic" ? "fixture" : "file"),
      "--cutoff",
      data.cutoff || "",
      "--out",
      outRoot,
      "--workspace",
      workspace,
    ];
    if (data.version && data.version.trim()) {
      args.push("--version", data.version.trim());
    }
    if (!data.cutoff || !data.cutoff.trim()) {
      if (data.cutoffFromCapture || data.source === "synthetic") {
        const idx = args.indexOf("--cutoff");
        if (idx >= 0) args.splice(idx, 2);
        args.push("--cutoff-from-capture");
      } else {
        return pythonUnavailable("Forecast cutoff is required. Pass cutoff or enable cutoffFromCapture.");
      }
    }
    if (data.source === "synthetic") {
      args.push("--synthetic");
    } else {
      const text = data.paste?.trim();
      if (!text) return pythonUnavailable("HAR paste is empty.");
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "dcm-har-"));
      const inputPath = path.join(tmp, "input.har.json");
      fs.writeFileSync(inputPath, text, "utf8");
      args.push("--input", inputPath);
    }

    const proc = spawnSync("python3", args, {
      cwd: pkg,
      env: {
        ...process.env,
        PYTHONPATH: pkg,
        PYTHONDONTWRITEBYTECODE: "1",
        DCM_FAST_WORLDS: process.env.DCM_FAST_WORLDS || (data.source === "synthetic" ? "64" : "256"),
        DCM_SERIOUS_WORLDS: process.env.DCM_SERIOUS_WORLDS || (data.source === "synthetic" ? "64" : "2048"),
        DCM_MAX_WORLDS: process.env.DCM_MAX_WORLDS || (data.source === "synthetic" ? "64" : "8192"),
      },
      encoding: "utf8",
      timeout: 90000,
      maxBuffer: 8 * 1024 * 1024,
    });

    if (proc.status !== 0) {
      const err = (proc.stderr || proc.stdout || proc.error?.message || "python failed").slice(0, 2000);
      return pythonUnavailable(`Python DCM failed closed: ${err}`);
    }

    const dest = parseDest(proc.stdout || "");
    if (!dest || !fs.existsSync(dest)) {
      return pythonUnavailable("Python freeze directory missing.");
    }

    const readJson = (rel: string): unknown => {
      const p = path.join(dest, rel);
      if (!fs.existsSync(p)) return null;
      return JSON.parse(fs.readFileSync(p, "utf8"));
    };
    const readText = (rel: string): string => {
      const p = path.join(dest, rel);
      return fs.existsSync(p) ? fs.readFileSync(p, "utf8") : "";
    };

    return viewFromPythonArtifacts(
      {
        run_integrity: readJson("run_integrity.json"),
        frozen_forecast: readJson("frozen_forecast.json"),
        frozen_forecast_sha256: readText("frozen_forecast.sha256").trim(),
        board: readJson("board.json"),
        top25_ranked: readJson("top25_ranked.json"),
        top25_qualified: readJson("top25_qualified.json"),
        strict_card: readJson("strict_card.json"),
        blockers: readJson("blockers.json"),
        production_readiness: readJson("production_readiness.json"),
        full_population: readText("full_population.jsonl"),
        host_research_plan: readJson("host_research_plan.json"),
        coverage: readJson("evidence/coverage.json"),
        schema_state: readJson("SCHEMA_STATE.json"),
        mount_state: readJson("MOUNT_STATE.json"),
      },
      dest,
    );
  });
