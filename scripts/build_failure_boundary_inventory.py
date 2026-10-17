"""Generate a deterministic static map of DCM exception and I/O boundaries.

This is a review queue, not a proof that a catch is semantically correct.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "dcm"
DEST = ROOT / "docs" / "audit" / "FAILURE_BOUNDARY_INVENTORY.json"
IO_METHODS = {
    "read_bytes", "read_text", "write_bytes", "write_text", "open", "replace",
    "mkdir", "unlink", "execute", "executemany", "commit", "rollback",
    "connect", "Popen", "run", "urlopen", "fetch", "upload",
}


def _call_name(node: ast.Call) -> str:
    target = node.func
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def inspect(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    catches: list[dict] = []
    operations: list[dict] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.depth = 0

        def visit_Try(self, node: ast.Try) -> None:
            for handler in node.handlers:
                caught = ast.unparse(handler.type) if handler.type else "bare"
                catches.append({"line": handler.lineno, "type": caught})
            self.depth += 1
            for statement in node.body:
                self.visit(statement)
            self.depth -= 1
            for statement in (*node.handlers, *node.orelse, *node.finalbody):
                self.visit(statement)

        def visit_Call(self, node: ast.Call) -> None:
            name = _call_name(node)
            if name in IO_METHODS:
                operations.append({"line": node.lineno, "operation": name, "insideTry": self.depth > 0})
            self.generic_visit(node)

    Visitor().visit(tree)
    return {
        "module": str(path.relative_to(ROOT)),
        "functions": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree)),
        "catches": catches,
        "boundaryCalls": operations,
        "unhandledCallSitesForReview": sum(not op["insideTry"] for op in operations),
    }


def build() -> dict:
    modules = [inspect(path) for path in sorted(SOURCE.rglob("*.py"))]
    return {
        "schema": "pillars_dcm.failure_boundary_static_inventory.v1",
        "interpretation": "Static review candidates only; a surrounding caller or supervisor may own the catch. No runtime safety certification is implied.",
        "summary": {
            "modules": len(modules),
            "functions": sum(row["functions"] for row in modules),
            "catchSites": sum(len(row["catches"]) for row in modules),
            "broadCatchSites": sum(
                catch["type"] in {"Exception", "BaseException", "bare"}
                for row in modules for catch in row["catches"]
            ),
            "boundaryCallSites": sum(len(row["boundaryCalls"]) for row in modules),
            "callsOutsideLocalTry": sum(row["unhandledCallSitesForReview"] for row in modules),
        },
        "modules": modules,
    }


if __name__ == "__main__":
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
