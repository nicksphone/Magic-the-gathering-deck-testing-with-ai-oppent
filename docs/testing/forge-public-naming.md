# Native Public-Information Naming

This is an isolated evaluation correction, **not a live app engine or strong-AI
certificate**. Forge is pinned at `61e9442c433711a82258daca3236f936a1d6f70e`.
The Forge Team/Card-Forge contributors supplied the engine, controllers and card
programs. Our GPL-3.0-or-later subclass/probes retain explicit source credit and
[the original license notices](../../THIRD-PARTY-NOTICES.md).

## Reproduced And Corrected

Two 60-card positions had identical public deck inventories and actor-projected
inputs, with only the opponent's unseen hand/library partition changed. Actual
native payment, stack and resolution produced different blind names for both
Cabal Therapy and Predict, on both seats. This demonstrated private-state
dependence, not merely a suspicious accessor.

The first eight-case cohort had **2 passes and 6 failures**: four partition
witnesses, two missed authorized top-card viewing controls, and two passing
revealed-hand controls. These tests force declared spells through native paid
paths, not autonomous cast selection. The unchanged full card programs were
checked against the hash-verified official Scryfall bulk records.

`PublicNameController` corrects opponent `NamedDiscard`,
`MostProminentInHumanDeck` and unguided naming. It uses immutable lists explicitly
disclosed by the host, native reveal callbacks and permitted observations, not
live hidden-library contents. Legal-name predicates remain enforced. Other
dedicated heuristics and self-discard planning remain unchanged and unqualified.

Reveals maintain conservative per-name lower bounds. Partial reveals merge facts
without double-counting. Public completed exits subtract the observed name;
concealed exits reduce every guaranteed bound by one. Review first exposed two
knowledge-retention regressions, then verified corrections using the committed
zone-change event rather than the earlier removal notification.

The final **seven whole native classes passed 181 tests**, zero failures/skips,
in 22.677 seconds: our naming/information 16, actor boundary 26, human token cases
2, and unchanged upstream simulation 124, replacement 1, protocol 1 and
named-discard 11. This is not the whole Forge suite. Original eight case bodies
were retained. New cases include paid Peek above paid Brainstorm, concealed
put-backs and a paid Counterspell response before another Therapy. Controlled
scene/reveal fixtures are not claimed full human games or HTTP workflows.

## Actual Full Series

Four open-list BO3s used Ramp and a diagnostic Dimir Control variant replacing
four Consider with four Cabal Therapy. Sideboards are constructed diagnostic
lists, not tournament-provenance lists. Each matched pair shares decks, seed
and settings; only the naming-controller selection differs.

| Seed | Baseline Control | Corrected Control |
| --- | --- | --- |
| `4391731612967343281` | Won 2-1 | Won 2-1 |
| `873109261490271` | Won 2-1 | Lost 0-2 |

All **11 games finished naturally**, without timeout-to-draw fallback. Combined
main/sideboard inventories were conserved. The runner captured **5,729 actor-view
priority observations** and separate private native logs. The first seed's
observations are semantically identical across policies. Nine actual Therapy
naming choices occurred; an initial substring counter also counted generic spell
summaries, and its corrected metadata was retained without rerunning games.

These development seeds do **not** demonstrate improved playing strength. The
unfavorable pair is retained. Monte Carlo and filtered hands were off; shuffle
assistance was disabled. That does not certify every native information path.
These observations are not the app's exact action-replay format, complete
choice telemetry or expert training labels. Generated game traces stay private.

## Remaining Work

The legal uninformed fallback is not a competitive closed-list prior. Probability
calibration, dedicated native heuristics and wider strategy remain unverified.
Forge's flat-Monte-Carlo rollouts already resample hidden hands/library order;
this heuristic series did not use that path. XMage also has a separate resampling
MCTS implementation, whereas its release-configured mad bot retains exact copied
hidden state. These are source findings, not matched runtime fairness certificates.

Next: test existing native search and broader play, and build the real UI/IPC
plus save/restart integration. No live backend, saved match, frontend or model
weights were changed. See [credited code and invocation](../../tools/engine_evaluation/README.md#public-information-naming)
and [the earlier boundary prototype](forge-native-boundary.md).
