# Generated engineering inventories

Generated files in this directory are derived engineering metadata.

Run:

```bash
python scripts/build_code_inventory.py --write
```

After Python code changes, regenerate and commit:

- `CODE_INVENTORY.json`
- `CODE_INVENTORY.md`

CI runs `python scripts/build_code_inventory.py --check` after the canonical snapshot is committed.

The inventory enumerates modules, classes, functions/methods, source hashes and workstream mapping. It is not evidence that a symbol is production-complete; completion state remains in the program-status registry and implementation matrix.
