# Beneficiary Polarity and Complete Damage/Life Instructions

Status: independent candidate, not deployed. Local source and printed card data
are preserved; pending gates below are not release claims.

## Implemented

- Shared tactical roles recognize life gain. Original conditional pump spells
  derive friendly recipients from parsed branches, not card names. Unknown
  history supplies only common beneficial polarity, never a guessed amount.
- Player targeting distinguishes a target player gaining life from the caster
  gaining life after damaging a different recipient. A broad card-role tag is
  not sufficient to decide which player a targeted instruction benefits.
- A complete fixed-damage/simple-target instruction joined with `and you gain`
  becomes the existing effect sequence: damage its declared recipient, then gain
  the printed amount for the spell controller. No new SQL gameplay or per-card
  dispatch. Complex qualified, conditional or variable joined forms are not
  certified by this exact structural family.
- Paid copies retarget the damage clause without retargeting untargeted caster
  gain. Choice reloads preserve the original and the copied controller. If the
  sole target becomes illegal, the entire spell fails to resolve, including gain.
  Prevented damage does not change the separate fixed gain. Self-targeting at
  three life completes both instructions before the tested loss check.

## Decision Evidence

Two stages use byte-identical 60-card manifests and the same two seeds in both
seat orders. Each stage has four logical games, eight repeat executions and eight
matching checked reconstructions; all complete packets repeat exactly without
timeouts or reported determinism failures.

| Stage | Logical decisions | Rest casts | Groundswell casts | Twincast casts | Beneficial originals targeting opponents |
| --- | ---: | ---: | ---: | ---: | ---: |
| Before original-recipient repair | 3,008 | 6 | 2 | 5 | 8 |
| After original-recipient repair | 3,081 | 8 | 2 | 8 | 0 |

These counts come from authoritative recorded actions, not card names in hands or
internal legality projections. The observer verifies the full recorded decision
count and complete reconstruction. Initial observer mistakes (void return and
counting nested/projection calls) are retained as diagnostic failures, not game
defects. The comparison supports this recipient repair only: no expert-strength,
balanced matchup or unrestricted Magic certification. Neither manifest contains
the subsequently added damage/caster-gain cards.

## Regression Gates

- Original-recipient repair: 36 canonical cases produce 27 failures/nine passes
  before correction. A 97-check selection passes afterward. The frozen full gate
  passes 7,797 tests in all 318 recursive files exactly once; all 603 backend
  source/fixture files match the isolated integration. Its full browser gate
  passes natural BO3 in AI/AI, human/AI and human/human modes.
- Subsequent damage/caster gain: two verbatim Scryfall fixtures expose 16 failures
  before semantic recipient selection. The first target fix still loses the gain
  clause; complete instruction parsing repairs it. A 151-check overlapping
  selection passes, including 68 beneficiary-family cases and older interaction
  checks. Intermediate prevention failures used nonexistent fixture fields;
  the corrected test calls the real shield helper, with no engine weakening.
- Twelve focused paid-copy Chromium cases pass both seats, ordinary/enhanced
  alternatives and joined damage/gain spells. They verify selection, reload,
  payment, unchanged original and actual copied effect results.
- Latest full backend/browser gates and the new Boros/Dimir capability matrix
  remain running. Earlier green gates and before/after games must not be renamed
  as qualification of this subsequent instruction repair.

## Remaining Work

Complete the latest exact-source gates and strictly reconstruct fresh natural
casts of the damage/gain family, including useful removal, caster benefit and
copies. Inspect the new life-trigger and control interactions rather than tuning
decks to a desired win rate. Reconcile the isolated integration before deployment;
retain unsupported planeswalker-dependency and wider targeting/layer boundaries.
Strategic beneficiary selection under adverse life replacements, competing
effects and complex modes needs public outcome planning beyond this basic repair.

Canonical fixture hashes and URLs are retained in
`backend/tests/fixtures/beneficiary_roles/provenance.json`. Private complete
game hands, boards, observations and evidence are archived on the verified NFS
share, not posted to external review services.
