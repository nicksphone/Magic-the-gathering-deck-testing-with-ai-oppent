# Private Library Reorder

The compiler admits only complete look-at-top/put-back-in-any-order instructions,
optionally followed by shuffle and draw. Counts use the existing number parser;
dispatch never uses card names. Canonical full Index and Ponder API responses and
intake hashes/URLs/times are tracked under `backend/tests/fixtures/library_reorder`.
Both current "You may shuffle" and canonical older "your library" wording work.

Players explicitly order all inspected cards, topmost first, then separately
choose keep or shuffle if offered. No priority is granted in the middle of
resolution. Draw uses the shared effect handler, not raw zone movement. The
existing continuation/snapshot machinery retains spell departure and subsequent
effects. Empty-library loss happens on an attempted draw, not merely looking.
Singleton/empty ordering has no meaningful permutation; optional shuffle remains
a choice. Countered spells never inspect or reorder.

AI receives only legally inspected identities and the submitted-deck prior, not
hidden remaining order or opponent hands. The new policy is a bounded next-draw
heuristic, not evidence of seasoned-player strength. Nonmodal spells/abilities
cannot replace their Oracle instructions through caller mode fields.

Final acceptance: 516 ordinary passes across 16 whole backend modules, 777
warnings,216.80s,exit0; no skipped/expected failures. Fresh npm ci, full frontend
tests, lint and build pass. Four two-process HTTP flows (both cards/both seats)
restore pending order/shuffle with exact snapshot/config/RNG before completing.
Eight additional memory/file HTTP flows cover wrong-seat root/SQL purity and
durable-loader restore. Core cases cover ordered choices, deterministic shuffle,
zero/short libraries, counters, stale/duplicate/foreign choices and private AI.

The corrected pre-change baseline has six ordinary failures. Historical draft
fixture failures (zone placement, inherited library size, counter helper default,
missing paired write headers) and two obsolete failclosed Ponder expectations
remain in archival evidence, not release results. Prior admission snapshots/logs
are immutable. Only assertions contradicted by real newly implemented behavior
were transitioned; unsupported turn/phase/control procedures still reject.

Remaining: shuffle-specific triggers/replacements, other reorder/search grammars,
broader copied/replaced effect interactions and natural-match policy validation.
No arbitrary-card, long-session GUI, full-suite or network-release certification.
