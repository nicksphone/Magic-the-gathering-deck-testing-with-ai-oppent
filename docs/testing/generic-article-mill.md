# Generic Article Mill

## Boundary

Compiler-only incremental qualification over the immutable entry-observer S2 source, not current main and not parent Index/Ponder library-reorder composition. Production scope: `backend/rules_engine/oracle_effects.py`, the prefix of `infer_effect_from_oracle`. Existing mill handler, event routing, costs, targeting validation, schema and AI are unchanged.

Full canonical raw objects for Altar of the Brood, Codex Shredder, Stifle, Rest in Peace and Thought Scour are retained in `backend/tests/fixtures/generic_article_mill/canonical.jsonl`. Provenance pins the official raw bulk source, complete unchanged selected objects, IDs, URI and SHA256. Gameplay tests use shared canonical hydration and original decks; no invented cards or edited Oracle.

A standalone article instruction (`target player mills a card`, `each opponent mills a card`, `you mill a card`, or `mill a card`) uses the existing count parser. `an` is accepted by that parser too. New article-first compound bodies are explicitly unsupported rather than partially granting a mill/life/turn reward. Existing numerical compound support is unchanged and is checked with actual paid Thought Scour.

A targeted compiler preview preserves `target_player=None`: it is not an announced executable action. Actual checked action and HTTP validation require an explicit player target before tapping/payment. The two-player engine computes each-opponent recipient from captured controller; this is not multiplayer support.

## Observed Qualification

New tests cover both seats, actual paid artifact cast without activation-on-cast, same-turn artifact tap, self/opponent target, pending receipt before resolution, actual paid Stifle, source departure/control seams, Rest in Peace replacement, empty library (not a draw loss), numeric compound compatibility, snapshots and repeated exact action results, rejected action root/database immutability, private information invariance and actual HTTP restart. Controlled source departure/control and private metadata perturbation are explicitly marked seams, not asserted legal spell episodes. Parser-only unknown compound probes are not claimed canonical cards.

Use the pinned main venv and isolated audit guard recorded in the archive. The guard blocks external socket connections and all SQLite files outside this exclusive local checkout. No tests use live games or NFS SQLite.

## Integration Dependency

S2 entry dispatch only permits full life/team-counter bodies. Consequently the four original unchanged Altar actual-entry HTTP golden cases remain RED even though the complete body now compiles correctly. No events.py edit or synthetic monkeypatch is included. Sagan must separately route the complete article-mill body and qualify those four tests plus token-entry/order cases. Existing Altar unsupported-noop expectations in `test_entry_observer_fix.py` then need an owner-reviewed positive replacement; Pandemonium/Political Trickery unsupported controls remain required.

Apply the surgical compiler hunk, never replace the full compiler file: parent has a separately qualified Index/Ponder reorder route and Meitner has an independent scheduler scope. This artifact does not certify all triggers, all mill instructions or complete Altar behavior.
