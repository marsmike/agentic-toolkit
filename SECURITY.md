# Security policy

If you find a vulnerability in this toolkit, please **do not open a public issue**.

Instead: email `mike@objektarium.de` with details. I aim to acknowledge within 72 hours.

## Disclosure timeline

- 90-day responsible disclosure target from confirmed acknowledgment.
- Critical issues may be embargoed for less depending on user impact.
- Coordinated disclosure with credit (if you'd like) on resolution.

## Scope

In scope: code in this repository — `core/`, `crates/`, and every plugin.

Out of scope: third-party services plugins integrate with — report to those vendors directly. A user's own vault content is theirs; the toolkit's contract is that tests, evals, and CI never read or write vaults outside `./vault`.
