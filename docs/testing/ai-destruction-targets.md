# Productive Destruction Targeting

## Behavior

AI target materialization excludes indestructible and friendly permanents for supported pure single-target destruction clauses. It can redirect to a vulnerable opposing target, or conserve its card, sacrifice cost or loyalty. This applies to instant/sorcery casts, a selected single destroy mode, activated abilities and loyalty abilities. It reads the current continuous-effect keyword evaluator rather than assuming printed keywords are permanent.

The later [winning self-removal increment](ai-self-removal.md) allows a friendly target when actual rules projection finds an unanswered win. This is an AI policy exception, not a waiver of cost, timing, indestructible or target legality. Ordinary nonwinning self-removal remains conservative.

After filtering, a selected mode must still have actual target candidates; an old count of available modes cannot authorize a targetless action. Human legality is unchanged: Naturalize can legally target Darksteel Myr, resolve without destroying it, and go to the graveyard.

Full-clause matching and effect inference limit the guard to supported destruction, with optional regeneration prohibition. Recognized secondary-effect verbs prevent classifying a compound spell as pure removal. Slice in Twain can resolve its draw after destruction fails against indestructible. This is not a claim that its removal component has value or that every compound clause is understood. Friendly self-removal synergies are not planned by this conservative policy.

## Evidence

The baseline agent at `810a964` casts Naturalize at a sole Darksteel Myr on an empty stack. Updated play passes instead on the same full snapshot and legal moves. Repeated decisions are tested across Control, Tempo, Midrange and Aggro at casual, strong and master difficulty. Other fixtures cover Doom Blade redirecting away from Darksteel Colossus, a productive Mind Stone target, preselected targets, Abrade's selected destroy mode, Thrashing Brontodon's sacrifice ability, Vraska the Unseen's loyalty and legal human casting. Secondary draw is tested through actual stack resolution, not only AI classification.

Six new Scryfall-ID/Oracle-ID-backed fixture records supplement the prior removal fixtures. Production logic has no card-name branches. The isolated focused AI/regression run passes 134 tests; the exact final source passes 1,650 backend tests. Frontend lint/build/unit and the full Chromium action/recovery/BO3 harness pass.

Eight verbose games use Midrange/Drain Deck seeds 810-811 and Tokens/Ramp seeds 820-821 with both seat orders. All finish without timeout, logged cast-time target/cost rejection or missing effect inference. Midrange wins four of four; Tokens/Ramp split two wins each. These are smoke/trace results, not a statistically meaningful balance test or proof of improved strategic strength. They did not necessarily exercise these new indestructible interactions; canonical fixtures provide that evidence.

The decision metrics retain unavailable values: Midrange blocking, one Drain lethal line, Ramp/Tokens blocking and one Ramp redundant-removal aggregate cannot all be certified by the existing bounded validators. Raw zero counts are not substituted for that missing evidence. A three-game seeded BO3 replay reports zero determinism failures and drift labels.

Artifacts, before/after state and traced games are retained locally under `/tmp/mtg-ineffective-destroy.vOcfG9/`, not shipped as a permanent training corpus. Tests run against copied source and isolated SQLite state rather than the live match database.

## Known Limitations and Next Upgrades

Pure destruction is only one interaction family. Conditional or multi-sentence destruction text, temporary protection responses, replacement effects, modal bundles, multiple targets, profitable self-removal and arbitrary secondary effects need board-aware valuation and golden semantic coverage. The guard does not perform a complete opponent search, certify every ability-face combination or make heuristic difficulty labels evidence of seasoned-player ability. Wider archetype matrices and manual competitive-play review remain open.
