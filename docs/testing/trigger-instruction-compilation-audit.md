# Trigger Instruction Compilation Audit

## Pinned Source And Scope

NEW tests/fixtures/report only, on immutable `mill-annihilator-committed-batches-L0056Y/qualified-source.tar.gz`
SHA256 `6ac24f42677c0de1f2b7c9b0a02b4089b4e5c677320b6c523f0b1da75658b80e`.
No production edits, moving parent source, live database, external network during tests,
injected event, fabricated stack item, or altered Oracle instruction.

Production SHA256 pins:

| File | SHA256 |
| --- | --- |
| `rules_engine/events.py` | `890f0d1d23d62a17607f7437f302a0a4216fd1a49eacbcc6599dda5673a638e3` |
| `rules_engine/oracle_effects.py` | `87eff1e4cf87f0d20c8329e0f56debdd517f31ac81acb0902e8107f03926c9a5` |
| `rules_engine/ability_model.py` | `bf06315d6e304eca6c17cf099970cf5c02aab6cddc5c0e0288515dc770154ea6` |
| `effects/handlers.py` | `6e2eefed1c1e7e0c5b671a4cb4f5fd422682194ca01c97898805c72a96540f91` |
| `rules_engine/engine.py` | `f0b1a06afa5e5272564685f8cce009a037f0c3c40a85053cbcddce14646139f0` |

## Evidence

The final two whole NEW modules execute **60 cases: 24 strict semantic FAIL,
36 PASS, 410 warnings, 35.77s, exit 1**. No exclusions, skips, expected failures,
or harness errors. Both seats pay the actual canonical mana costs through
`checked_action`; HTTP controls use separate owned memory/file SQLite repositories.
Triggers resolve through both genuine priority responses. Snapshot subprocess
round trips and HTTP cold restoration preserve the pending and resolved state.

The 24 failures are eight printed draw-count/replacement cases, four actual
compiled-payload cases, four independent Cloudblazer life-gain cases, and eight
actual HTTP effect-resolution cases. The 36 independent controls cover paid
admission/controller/pending privacy, invalid actor/underpayment full root and
SQL invariance, full canonical Visionary draw/Thought Reflection replacement,
and real paid Stifle responses that counter only the trigger. Casting Kozilek
still leaves the creature spell below its cast trigger; Cloudblazer is already
on the battlefield when its ETB trigger resolves.

Four whole unchanged neighbors execute **107 PASS / 1 FAIL, 83 warnings,
55.11s, exit 1**. Retained failure:
`test_cast_trigger_targets.py::test_cast_trigger_survives_countering_source_spell`.
Its direct counter helper produces a real graveyard-shuffle trigger above the
still-retained cast destruction trigger. After one resolution the shuffle has
resolved, while destruction remains on the stack. The diagnostic records that
ordering; it is not a new genuine paid HTTP counterspell episode or proof that
the cast trigger was lost. The existing test remains unchanged.

Historical ledgers remain separate: initial setup exited 1 after successful
archive verification/extraction because of a wrong compiler path; first pytest
attempt had 52 basetemp setup errors in 4.59s; corrected draft 52 had 20 FAIL /
32 PASS in 20.15s. These are not the final 60-case result.

## Actual Compiler Seam

The observational wrapper calls the unmodified `_trigger_from_oracle` and
`build_ability_spec`, retaining genuine event/controller/source and returned
effect payloads. Both audited instructions return `noop` with an empty body
payload. No successful `EffectSpec` compilation of either body is observed.

Kozilek's matched cast instruction is `draw four cards`; the legacy fallback
only special-cases `draw a card` and the later generic-compiler keyword gate
does not admit draw alone. Cloudblazer's ordinary self-entry clause is not the
entry-or-transform helper, and does not match the `a/an/another` observer
predicate. The observer body's allowlist is therefore NOT its causal path.
The fallback fails to compile its complete life/draw instruction.

`oracle_effects` already has `DRAW_RE`, `_parse_count_token`, `_infer_clause_effect`,
and `effect_sequence`. `_split_clauses` does not split a general life-and-draw
conjunction. Simply sending the compound to substring-based draw inference
could recognize draw while silently dropping life. Merely broadening the event
keyword gate or observer allowlist is insufficient.

## Minimal Proposal, Not Implemented

1. In `events._trigger_from_oracle`, reuse actual matched cast instruction and
   add exact current-source self-entry recognition alongside existing special
   entry/transform, flashback, kicker, paid/optional and targeted delegation.
   Preserve the full trigger clause, controller and resolution context, rather
   than compiling all permanent Oracle lines as one body or matching card names.
2. In the shared instruction compiler, reuse the existing count parser and IR.
   Anchor admission to the COMPLETE simple draw body, or COMPLETE unconditional
   life-then-draw body. Compile the latter as ordered `gain_life`, `draw_cards`
   effects. Existing replacement-aware handlers remain authoritative; no new
   draw/life resolver is needed.
3. Unknown trailing clauses, conditionals, optional payments, multiple unmatched
   instructions or unresolved targets must retain an explicit unsupported
   instruction receipt and no fabricated partial reward. Do not let a search
   match imply full-body support. Existing genuinely supported special routes
   must continue to delegate without being blanket-demoted.

The independent trigger must survive later source-spell countering, and draws
must retain normal replacement/continuation semantics. Those are boundaries
for any later authorized product patch, not certified fixes from this audit.

## Canonical Provenance And Limits

Four fixture files are unchanged complete Scryfall public API response bytes,
with URLs, hashes, Oracle IDs and capture timestamps in `provenance.json`.
The primary families are Kozilek and Cloudblazer; Visionary and Thought Reflection
are independent controls. Stifle reuses the inherited hash-verified complete
canonical fixture and provenance. Canonical battlefield controls are trusted
retained positions, not claims of naturally casting every observer.

An unchanged Notion Thief API response is archived as intake only. Its opponent
draw-redirection grammar is not one of the observed replacement handlers and
was NOT qualified by this audit. Thought Reflection is the actual exercised
replacement. This is not a global trigger, compound-instruction, draw-replacement,
or full-release readiness claim; parent newer sources were not consumed.
