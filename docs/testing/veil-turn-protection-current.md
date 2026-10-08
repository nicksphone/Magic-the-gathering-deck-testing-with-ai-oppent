# Conditional Draw And Turn Protection

The generic complete-body compiler supports the full canonical Veil of Summer
instruction using existing ordered effects, draw replacements and retained
keyword effects. It has no card-name branch or partial-reward fallback.

Actual spell casts retain color history; copies do not count as casts. The
temporary counter prohibition follows the resolving controller's spells,
including later spells, but not activated abilities or an opponent's copy of
the same physical source. Player hexproof is checked against source colors.
Permanent hexproof applies to the cohort present at resolution, not later
entries or new incarnations. Existing cleanup removes the effects.

Strict snapshot fields preserve history and turn protection. Legacy snapshots
with missing color history and prior casts are explicitly unknown; resolving
an unproven conditional draw rejects without partial reward instead of guessing.

Qualification on isolated parent `9d43c1a` plus the unchanged 24-case audit:
eight whole modules, 232 ordinary passes, 26.51 seconds, exit 0. All source
hashes before/after match. Nine native SQL/socket/child negative controls were
denied before collection; application I/O attempts were empty, descriptor maps
matched, no extra threads remained, and no database existed.

The unchanged audit's previous 16 failures now pass. New goldens cover both
seats and JSON restore, real counter/bounce/black-source payments, fixed
permanent cohorts and cleanup, genuine opponent Twincast copies, actual paid
Thought Reflection, and an actual draw pause with deliberate canonical dredge.
Compiler and malformed-snapshot checks are explicitly protocol tests, not
invented canonical cards. Some battlefield/graveyard setup is declared fixture
state; it is not certified as a paid cast or discard episode.

The preceding same 232 tests passed in 27.03 seconds, but the wrapper exited 1
because bytecode-cache writes were denied. That ledger is retained. The final
run used `PYTHONDONTWRITEBYTECODE=1`; no test, product or guard changes were
made between those two runs. Earlier 224/220/218/24 cohorts remain separate.

Rules reference: official Comprehensive Rules, September 25, 2026,
<https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt>.
The fixed permanent cohort and later-spell rule distinction follows 611.2c.

This is pure component qualification, not final-parent integration, native
HTTP/SQLite, browser acceptance, coverage-warning removal, or complete support
for arbitrary continuous-effect layers and all cards.

The subsequent current-parent integration independently passed the same eight
whole modules and all 232 ordinary cases in 25.93 seconds, exit 0. Native
SQL/socket/child denials were installed before collection; application I/O was
empty, descriptor maps and source hashes matched, no extra threads remained,
and the existing local database hash was unchanged. This establishes current
pure integration, not the separate native/browser and release requirements.
