# Global As-Though-Flash Permission

## Frozen Baseline

This incremental product qualifies the copied baseline recorded by
`canonical-global-flash-audit-jjKHhn`, not the current parent or latest main.
Its captured source manifest SHA-256 is
`c22bf1a767d9a3e7a6d2747e89fa6ee4d84bca6febaf9975264bc291c66a4ec0`.
Initial parent-before/after-copy manifests matched; every captured copied byte
was verified. The recorded end-parent difference was only `card_data/tactical.py`:
copied `6c7af95f58d010a7e324c7c037f54824818aad12aaf115fd7fd2c0e7e8774195`,
end-parent `e1e488873e2594f0e7761a9dbaa2e047a3cabfe86b59ecf42b1f15ad46edfd48`.
No subsequent parent read or whole-parent equivalence claim is made.

## Product Scope

Only `rules_engine/restrictions.py` and `rules_engine/move_generator.py` change.
Their before SHA-256 pins are respectively
`16a727ea58d73c9438b11f9377bc6d24b00810da53301af37db7c67d54618773` and
`37732dd71fb55783245830ce4e9cdf4e4dbbf01545110336d48f0c59c8ec1aab`.

`has_global_flash_permission(state, player_id) -> bool` is a pure shared query
for the unconditional standalone canonical static sentence granting all spells
as-though-flash timing. It reuses the current static Oracle filter and printed
ability suppression query. It checks battlefield location and current controller,
not owner. It creates no keyword, type, permission flag, cache record, or effect.
Existing `can_cast_in_current_timing(..., during_resolution=False)` ABI remains
unchanged. The move generator's preliminary timing floor consults the same grant;
the authoritative query still enforces its existing prohibitions afterward.

Intrinsic flash detection no longer treats any Oracle substring mentioning
flash (including a grant printed on a card still in hand) as intrinsic flash.
Explicit supplied-view keyword/standalone flash remains available; the timing
query does not look up the physical front card's keywords for a selected face.
The move generator's existing effective-flash check is unchanged. The existing
combat restriction now also checks the conjunctive
`on your turn` qualifier. No card-name branch is introduced.

Lands, loyalty, activated ability timing, priority, zones, targets, physical mana,
and additional costs retain their existing checked execution paths. This is not
a general permission to take actions at instant speed.

## Canonical Evidence

The unchanged original audit and nine full raw fixtures/provenance entries are
dependencies, not rewritten Oracle. Leyline of Anticipation and Vedalken Orrery
admit funded off-turn Grizzly Bears and Divination for both seats. Actual paid
Krosan Grip removes the source; split second still prevents response casts.
Savage Beating remains limited to combat on its controller's turn.

Official rules reviewed from the [Wizards rules page](https://magic.wizards.com/en/rules)
and its linked [September 25, 2026 rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt):
101.2, 307.5, 601.2e, 609.4, and 702.8a. These distinguish a timing grant from
prohibitions, casting legality, action-specific restrictions, and other uses of
an object's characteristics. No quoted rule text or fabricated card data is used.

New controller-transfer and ability-loss/expiry cases call existing effect APIs
directly on canonical cards. They certify the timing query's integration with
those model transitions, not that a particular control/removal spell executes
correctly. Full canonical animation-plus-suppression combinations are not claimed.

## Gates And Limits

Unchanged original audit plus restrictions: 79 ordinary passes. New controls:
40 ordinary passes, including 24 actual ASGI HTTP cases across both seats,
both sources, both spell types, funded/unfunded. These verify public legal views,
hidden AI hand exclusion, actual payment, exact checked-execution snapshots,
atomic 422 memory/DB rejection, and SQLite-backed cache eviction/restore.
SQLite is isolated in-memory; no application lifespan or public live server.
Restore is in-process persistence restore, not a cold server/process certificate.
Eight paid-response cases additionally start with an opponent's actually paid
Opt on the stack. Native priority passes admit the off-turn response; actual
HTTP payment preserves the existing stack object and matches checked execution.

Final product revision removes an unnecessary physical-card effective-keyword
lookup from the authoritative query, preserving the supplied selected-face view.
Its fresh unified gate passed all 558 original/initial-new/neighbor cases with
zero skips. The unchanged complete new-control module, extended only by the
eight real-response cases, then passed 40 cases on a separate fresh source/DB.
Together these cover 566 distinct checks; 32 new controls are repeated in the
40-case follow-up, not counted twice. The first product candidate and its
failure ledgers remain archived separately; it is superseded by this revision.

Ten complete neighbor modules cover 447 unique cases. Initial run: 446 passes,
one migration-test guard failure because basetemp was outside the allowed source
root. The unchanged whole 22-case face module then passed with basetemp inside
the owned root; this repeats 21 passed cases and resolves the guarded case.
New-control first attempt: 16 passes, 16 import/setup errors due to a missing
shipped SVG runtime asset. Both original failure ledgers remain immutable.
No assertion weakening, case filtering, xfail promotion, or skip override.

The runtime SVG is a declared ancillary dependency recovered from a verified
older owned archive, SHA-256
`a3114095c760517186807f8753d109000174460a20ee72693ff9b9a69efc5e85`.
It is not a gameplay patch or proof of omitted parent asset equality.

Conditional, scoped, quoted, activated, and triggered flash permissions are not
implemented by this query. Unrecognized text remains unsupported, not proof of
absence of a rules effect. Existing unsupported prohibitions are not newly
implemented or certified. No all-card, trained competence, AI skill, win-rate,
general layer correctness, deployment, or live database claim follows.
