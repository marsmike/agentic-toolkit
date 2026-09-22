---
type: regex
target: {source: file, path: check.json}
match: not_contains
---
"misses":\s*\[\s*"
