# /compile Quick Start

## Default — all renderers with code

```
/compile
```

## Pptx only

```
/compile pptx
```

## Dry run — show diff, write nothing

```
/compile --dry-run
```

## Drift check only (HTML ↔ catalog label sync)

```
/compile --check
```

Exits non-zero on drift. Used as the CI gate via `tests/test_compile_drift.py`.
