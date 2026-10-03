# Conditional attack and static block costs

## Implemented Scope

The shared declaration-payment reader now recognizes fixed mana block taxes and
supported source/controller-relative conditions on attack and block taxes. This
is application-code logic; SQLite persists snapshots, never evaluates rules.

Source status predicates (tapped, untapped, attacking and blocking) use current
battlefield state, not last-turn logs or a card-name exception. Full/short self
references and current Oracle "this creature" references use the same predicate
reader. Recognized controller land/graveyard/counter/color-permanent and global
land predicates also compose with these mana tax bodies. Recipient-characteristic
and defending-player predicates are deliberately not admitted as source conditions.
Unknown conditions and unsupported payment grammar remain explicit coverage gaps.
Parsed tax clauses retain their condition for a following supported "Otherwise"
restriction, preserving coverage/runtime parity instead of losing the branch.

Static block taxes may apply globally, to creatures the source's controller
controls, or to that controller's opponents. Costs charge once per distinct
chosen blocker. Conditions, current controller and printed-ability suppression
are checked before the cost is locked. Tapping or sacrificing mana sources during
payment does not re-price the declaration. Existing optional-payment requirement
scoring, restricted mana and explicit hybrid/life choices are reused.

Canonical Archangel of Tithes exercises both families: its untapped condition
taxes attacks on its controller or that controller's planeswalkers; its attacking
condition taxes blockers globally, not just creatures blocking the Archangel.
Departure, suppression or removal from combat changes future declarations, not
costs already paid or blockers already declared. Resolution-created costs remain
independent of their source and add to applicable static costs.

All AI difficulties use the existing shared declaration finalizer/affordability
path. Actual agent decisions are checked against engine legality, without forcing
an attack or block merely to improve a test's card-use count. This batch does not
prove optimal resource spending, holding an untapped tax source or expert play.

Expanded controlled decisions exposed a separate Master/Master+ search defect:
the search's internal blocker-to-attacker mapping was passed directly to the
engine's attacker-to-blockers contract. The search now simulates the declaration
it returns, with rejection enabled; final AI declarations normalize blocker lists
even when no static cost or requirement is present. Canonical lethal-flyer versus
profitable-ground-trade cases verify survival by resolving actual combat, with
and without taxes, in both seats. This is a shared projection repair, not a
special preference for flying creatures or a claim of global optimality.

No competitive deck changed. Existing canonical fixture provenance is reused;
scoped/conditional grammar cross-products are explicitly test boundaries, not
invented Magic cards. Supporting these clauses does not certify arbitrary cards.

## Acceptance

- Both-seat player/planeswalker attack costs, attacking-source block costs on
  another attacker, source suppression/departure and snapshot recovery.
- Shared source-status and full/short self references; unsupported conditions stay
  visible rather than becoming unconditional rules.
- Static block scopes, additive resolved costs, all-difficulty actual AI choices,
  and both-seat HTTP hints/atomic rejection/SQLite startup restoration.
- Real App controls reject unaffordable declarations without changing revision;
  legal attacks and tapping-to-pay blockers commit exactly once.
- Canonical preflight now uses Stormtide Leviathan's still-unimplemented qualified
  subject; no simulator job starts without exploratory admission.

Frozen-source validation: 3,060 backend tests passed (326 deprecation warnings),
370 focused combat/AI checks and 68 final continuation checks passed. Frontend
lint/unit/build and the full Chromium suite passed. Twelve logical seat-balanced
template games repeated twice resolved without determinism failures, drift labels
or reported anomalies. These games establish repeatability, not mechanic use or
competitive balance.

Thirty-two controlled actual AI scenarios produced six paid attacks, six paid
blocks and twenty passes, including appropriate passes in losing positions and
Casual passes in the positive positions. Four Master/Master+ decisions changed
from the ground trade to blocking the lethal flyer; separate unit regressions
resolve actual combat to verify survival. Public-board/hand snapshots and legal
actions are retained, not only a final win rate. This is bounded tactical evidence.

Verified evidence and closed source copies, including failed fixture/locator runs
and before/after AI traces, are archived on RCHFiles under
`diagnostics/conditional-combat-costs/20261003T000956Z`. The first fixtures incorrectly
assumed an unchosen Elf could not pay and that GET lazily restores matches; these
were corrected without changing those existing engine/API contracts. A browser
locator was made attacker-label-specific rather than weakening payment checks.
Tests use isolated local databases, not live state or SQLite on NFS; no fresh
dependency installation, visual UI audit or general network-release test was done.

## Known Limitations and Next Upgrades

- Qualified creature subsets, recipient-dependent tax conditions, nonmana costs,
  optional additional costs and interrupted payment choices remain unfinished.
- Granted nonkeyword costs/requirements and arbitrary type/ability/dependency
  layers are not complete. Source-status support is not general layer fidelity.
- General pre-declaration priority and simultaneous payment triggers/replacements
  require broader acceptance than these bounded fixtures.
- Requirement search and tax-resource planning need arbitrary-board latency and
  decision-quality evidence. Deterministic template games do not measure balance.
- Alpha UI redesign and visual usability remain deferred; operational gates in
  `plan.md` remain open.

References: [official Thunder Junction release notes](https://magic.wizards.com/en/news/feature/outlaws-of-thunder-junction-release-notes)
and [Comprehensive Rules](https://magic.wizards.com/en/rules), 508.1 and 509.1.
