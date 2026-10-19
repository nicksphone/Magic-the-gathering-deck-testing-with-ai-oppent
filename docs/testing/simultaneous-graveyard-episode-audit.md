# Simultaneous graveyard episode audit

Tests-only audit on immutable fc225406d56c1a2f177ccfa8fb0b6008448772f2
source plus consumer 34c662 (production 7dce2b), emitter 4ceec5,
reference lifecycle f30fd2, keyword 4eb754 and handlers 76767d.
Original22 b8f7b6 and direct-audit 25bef5 are unchanged test dependencies.
No moving parent source, production edits or main/live database access.

## Actual terminal evidence

- Both NEW whole modules: 22 passed, 2 strict failures, 234 warnings,
  21.12 seconds, exit 1. No exclusions, skips or expected failures.
- Four whole neighbors (discard history, entry product seams/episodes,
  reference lifecycle): 138 passed, 143 warnings, 25.08 seconds, exit 0.
- Initial attempt: 10 passed, 2 strict failures, 12 missing base_client
  fixture errors, 9.43 seconds. The import was corrected in NEW tests only.
- Before adding saved observational traces: 22 passed, 2 strict failures,
  20.96 seconds. All attempt logs remain separate.

## Selected simultaneous discard

Canonical Delirium Skeins is actually paid, cast and resolved. Both players
deliberately select three own hand cards, including two Kozileks each.
No cards move while the other player's selection is pending. Public trigger
ordering preserves APNAP, deliberate reversed orders and snapshot restart.
Wrong actor/duplicate selections reject without root mutation; memory/file
HTTP wrong-actor rejection also preserves controller and complete SQL facts.

The two strict failures observe real enters_graveyard collection, without
injecting events or replacing collector behavior. At successive receipts,
only 1, 2, 3, 4, 5, then 6 selected cards have committed. Deterministic checked
action replay repeats that sequence. Trigger publication staging does not
make early collection a completed simultaneous batch. Current independent
APNAP/private/restart controls pass; no additional trigger semantic failure
is claimed from this observation alone.

Proposed narrow followup: retain exact trusted per-card PRE/POST receipts,
defer collection until all validated batch moves commit, then publish the
genuine batch under existing staging/APNAP. Preserve single-entry execution,
replacement/static-cause ordering and actual destination filtering. Product
scope and all sibling batch callers require separate review and qualification.

## Whole-graveyard departure

Full canonical Desecrated Tomb grammar is recognized and actually executes:
Sickening Dreams pays a deliberate two-card creature discard, making a real
Kozilek trigger. Its whole-graveyard shuffle yields ONE Tomb receipt and ONE
canonical 1/1 black flying Bat. A genuine paid Cremate response followed by
the remaining graveyard shuffle yields TWO separate receipts and TWO Bats.
Both seats, core replay/restart and memory/file HTTP episodes pass. The paid
Dreams spell remains below the resolved triggers; its eventual damage is not
part of this bounded Bat-count qualification.

Full unchanged Scryfall responses for Delirium Skeins and Desecrated Tomb,
URLs, timestamps and hashes accompany the fixture. Waste Not was retrieved
but is not used or qualified. Existing Kozilek, Blood Artist, Doomed Traveler,
Sickening Dreams and Cremate use unchanged inherited canonical fixtures.

## Limits

Restarts comprise snapshot roundtrip in a fresh subprocess and owned-repo
cold HTTP controller restore, not restarting a live server. Invalid-action
atomicity is scoped to the tested actual requests. No general multiplayer,
all replacement/batch, arbitrary departure grammar or release-readiness claim.
