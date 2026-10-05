# Consolidated Backend Qualification

Date: 2026-10-05. Frozen runtime: `91b5dff8280d40d9a97ceacd37e29a21ff606308`.
Integrated into main after documentation-only reconciliation; backend/frontend
source remained identical to that frozen runtime.

## Verified

- 8,878 backend tests pass. All 359 recursive test files run exactly once across
  four isolated source copies, with initially absent SQLite databases.
- 738 Python/JSON/SVG source hashes match in every copy.
- Complete browser suite passes, including natural AI-vs-AI, human-vs-AI and
  human-vs-human best-of-three games. Both-seat cost/graveyard controls pass.
- Frontend unit tests, lint and production build pass.
- Eight existing matches restore against a copied live database; saved deck
  rows remain unchanged. Live backend health passes after automatic reload.
- The original failed gate is retained: three lightweight AI views lacked
  Oracle metadata. The shared compatibility repair has an explicit regression.

Logs, manifests, source archives and recovery evidence are retained under the
project's private RCHFiles diagnostics storage. User databases and retained
hands are not committed as public test evidence.

## Known Limitations And Next Upgrades

This establishes integration correctness within the exercised tests, not
arbitrary-card completeness, expert AI, balance or network release readiness.
Broader conditional/compound cost semantics, permission durations and layered
characteristics remain unfinished. Natural candidate reviews already running
continue without replacement runs. The next AI work uses retained positions to
reduce repeated read-only queries and nested forecasting without removing
legal responses, changing card data or exposing hidden information.
