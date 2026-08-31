#!/usr/bin/env python3
"""Generate repository-visible inventory of DCM Python modules/classes/functions.

This is engineering inventory, not predictive validation. It intentionally uses
Python AST so agents can audit executable surfaces without relying on prose.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "artifacts" / "dcm_v6_workstream_ab"
OUT_JSON = ROOT / "docs" / "generated" / "CODE_INVENTORY.json"
OUT_MD = ROOT / "docs" / "generated" / "CODE_INVENTORY.md"

PATH_WORKSTREAMS = {
    "/ingest/": "P0",
    "/identity/": "P0",
    "/contracts/": "P0",
    "/research/": "P1",
    "/ml/": "P2",
    "/model/": "P2-P4",
    "/sports/": "P3",
    "/selection/": "P4",
    "/runtime/": "P5-P14",
    "/learning/": "P6",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def workstream(rel: str) -> str:
    probe = "/" + rel.replace("\\", "/")
    for needle, ws in PATH_WORKSTREAMS.items():
        if needle in probe:
            return ws
    return "UNMAPPED"


class Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.symbols: list[dict[str, Any]] = []

    def _add(self, node: ast.AST, kind: str, name: str) -> None:
        qualname = ".".join([*self.scope, name])
        doc = ast.get_docstring(node, clean=True) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else None
        self.symbols.append(
            {
                "kind": kind,
                "name": name,
                "qualname": qualname,
                "line": getattr(node, "lineno", None),
                "endLine": getattr(node, "end_lineno", None),
                "doc": (doc.splitlines()[0] if doc else None),
            }
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._add(node, "class", node.name)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._add(node, "method" if self.scope else "function", node.name)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._add(node, "async_method" if self.scope else "async_function", node.name)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def build() -> dict[str, Any]:
    modules = []
    parse_errors = []
    for path in sorted(PKG_ROOT.rglob("*.py")):
        if any(part in {"__pycache__", ".venv"} for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except Exception as exc:  # inventory must report, not hide, parse failures
            parse_errors.append({"path": rel, "error": f"{type(exc).__name__}:{exc}"})
            continue
        visitor = Visitor()
        visitor.visit(tree)
        modules.append(
            {
                "path": rel,
                "sha256": sha256(path),
                "workstream": workstream(rel),
                "classes": sum(s["kind"] == "class" for s in visitor.symbols),
                "functions": sum("function" in s["kind"] or "method" in s["kind"] for s in visitor.symbols),
                "symbols": visitor.symbols,
            }
        )
    payload = {
        "schema": "pillars_dcm.code_inventory.v1",
        "root": PKG_ROOT.relative_to(ROOT).as_posix(),
        "moduleCount": len(modules),
        "symbolCount": sum(len(m["symbols"]) for m in modules),
        "parseErrors": parse_errors,
        "modules": modules,
    }
    semantic = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["contentHash"] = hashlib.sha256(semantic).hexdigest()
    return payload


def render_md(inv: dict[str, Any]) -> str:
    lines = [
        "# Generated DCM code inventory",
        "",
        "Generated from Python AST. This is an executable-surface inventory, not a completion claim.",
        "",
        f"- Modules: **{inv['moduleCount']}**",
        f"- Symbols: **{inv['symbolCount']}**",
        f"- Parse errors: **{len(inv['parseErrors'])}**",
        f"- Inventory hash: `{inv['contentHash']}`",
        "",
        "| Workstream | Module | Classes | Functions/methods |",
        "|---|---|---:|---:|",
    ]
    for mod in inv["modules"]:
        lines.append(f"| {mod['workstream']} | `{mod['path']}` | {mod['classes']} | {mod['functions']} |")
    lines += ["", "## Symbols", ""]
    for mod in inv["modules"]:
        lines += [f"### `{mod['path']}`", ""]
        if not mod["symbols"]:
            lines.append("_No class/function symbols._")
        else:
            for sym in mod["symbols"]:
                doc = f" — {sym['doc']}" if sym.get("doc") else ""
                lines.append(f"- `{sym['kind']}` **{sym['qualname']}** L{sym.get('line')}{doc}")
        lines.append("")
    if inv["parseErrors"]:
        lines += ["## Parse errors", ""]
        for err in inv["parseErrors"]:
            lines.append(f"- `{err['path']}`: {err['error']}")
    return "\n".join(lines).rstrip() + "\n"


def serialize() -> tuple[str, str]:
    inv = build()
    return json.dumps(inv, indent=2, sort_keys=True) + "\n", render_md(inv)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="Fail if committed generated inventory is stale.")
    p.add_argument("--write", action="store_true", help="Write generated inventory files.")
    args = p.parse_args()
    json_text, md_text = serialize()
    if args.write or not args.check:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json_text, encoding="utf-8")
        OUT_MD.write_text(md_text, encoding="utf-8")
    if args.check:
        stale = []
        if not OUT_JSON.is_file() or OUT_JSON.read_text(encoding="utf-8") != json_text:
            stale.append(str(OUT_JSON.relative_to(ROOT)))
        if not OUT_MD.is_file() or OUT_MD.read_text(encoding="utf-8") != md_text:
            stale.append(str(OUT_MD.relative_to(ROOT)))
        if stale:
            raise SystemExit("CODE_INVENTORY_STALE:" + ",".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
