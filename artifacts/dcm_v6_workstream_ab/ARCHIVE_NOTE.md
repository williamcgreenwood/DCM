# Archive note

As of the `refactor/src-dcm-package-layout` change, the **installable production
Python package** lives at `src/dcm` (and `src/pillars_dcm`), discovered via
repo-root `pyproject.toml` (`where = ["src"]`).

This directory remains a **historical archive** for fixtures, workstream docs,
schemas copies, and configs referenced by path. It is **not** the installed
package root. Do not add new production modules here.
