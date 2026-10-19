# Complete Compleated Loyalty Instructions

Status: approved implementation; final whole-module qualification recorded in
the surgical handoff packet. Immutable source is
`58c34d095737b5d9f42a9d50c6ffa1ba270d7e6a`. The full primary API response in
`backend/tests/fixtures/compleated_loyalty_full/tamiyo.raw.json` is retained
byte-for-byte, with provenance. Mana cost, type, loyalty, Oracle ID, and the
entire Oracle text match the existing `compleated_entry.json` fixture.

## Implemented Families

The compiler uses anchored complete instruction/reminder grammars, not card
names. The hybrid compleated reminder accounts for its two distinct colors,
life alternative, and two-counter entry reduction. Existing one-color
compleated companions and native payment/entry replacement behavior remain.

The new instruction nodes are `loyalty_tap_freeze`,
`loyalty_graveyard_exile_copy`, and `loyalty_named_artifact_token`. They retain
the native `effect_sequence` wrapper and complete ability targeting text.
Singular/list-one target slots, captured references, and announced X remain
native stack receipts. X is not compared to post-payment source loyalty.

Freeze permits zero or one artifact/creature target. Its prohibition follows
the permanent's incarnation, including controller transfers and source
departure. Ordinary untap effects do not consume it. The next untap step of
the permanent's current controller consumes all live locks even if the
permanent is already untapped, before the ordinary tapped/stun checks.
Serialized locks use the existing `loyalty_permissions` container; they are
not interpreted as flash permissions.

Graveyard-copy targeting checks controller-owned graveyard membership, zone,
nonland permanent types, and exact announced mana value. It exiles before
copying printed characteristics with existing token/entry helpers. The token
is not cast, so source Phyrexian-life payment does not reduce copied loyalty.
Copied Auras stage fresh off-state native token candidates after native token
replacement. The controller submits a non-target `loyalty_attachment` choice
for each candidate before the batch enters. Hexproof and ward do not forbid
non-target attachment; native enchant restrictions and protection still apply.
Attachment references and current legality are checked after snapshot/restart.
No legal attachment means no token entry or entry event, while the original
card remains legitimately exiled. Native token/counter entry and event batches
are reused without inventing a hand or battlefield producer.

The legendary colorless artifact family parses the token name, optional Book
subtype, generic spell reduction, and tap/draw amount from the full quoted
compound. The existing legendary SBA, spell-only controller-relative discount,
ability suppression, and genuine tap costs execute those printed abilities.
The older related token API type line is not substituted for Tamiyo's current
Oracle: the generated token has the printed Book subtype.

## Ownership

Production edits are restricted to the approved functions in
`loyalty_instructions.py`, `oracle_effects.inspect_target_hints`, and
`named_counters.untap_permanent`, plus three approved generic seams:
`action_validation.validate_action` rejects non-integer/negative loyalty X;
`handlers._offer_copy_target_choice` delegates only complete new single-node
loyalty ability sequences; `keyword_actions.finish_mechanic_choice` delegates
only the native `copy_target` slot and retains native publication/resume.
No engine, cost, state, serializer, stack, schema, SQL, browser, dependency,
frozen Aura, or `handlers.change_control` edits are included.
New fixtures and five test modules exercise real full canonical checked casts
in both seats, all mana/life branches, three loyalty resolutions, rejection
purity, incarnation/zone/controller boundaries, public turn progression,
paid permanent-spell copying, legendary replacement-created Notebook tokens,
spell discount removal, activated costs, and creature-only tap sickness.
Controlled layer/stun/declared-resident seams are labeled in tests; they are
not claimed as paid spell episodes.

## Observed Evidence

Initial red: 74 FAIL / 21 PASS, 9.03s, including two fixture lookup errors.
Corrected pre-production red: 72 FAIL / 23 PASS, 9.01s.
The first 21-whole-module focused run: 660 PASS / 6 FAIL, two dependency
deprecation warnings, 141.22s, with source pre/post hashes unchanged. All
existing loyalty and selected pure-neighbor modules passed. This is not a
full-backend, HTTP, SQL, browser, or Aura-619 certificate.

Additional checked boundary tests are retained as real failures, not skipped,
deselected, xfailed, or relabeled passing. Three pinned proposals require
approval before ownership expansion; all three were explicitly approved:

- Negative loyalty X: existing checked validation allows a logged engine no-op
  before the approved hint hook; add one typed nonnegative-X require to
  `action_validation.validate_action`.
- Paid loyalty-copy retargeting: the native copy chooser skips ability
  `effect_sequence` frames; add two narrow dispatcher hooks and owned helpers,
  preserving target count/shape, chosen X, and changed-slot-only receipts.
- Copied Aura entry: generic graveyard copies of canonical Pacifism currently
  create an unattached token that ceases; extend only the owned loyalty entry
  choice functions, reusing existing non-target attachment and token helpers.

Exact proposals, run logs/XML, and surgical pre/post ownership evidence are in
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/tamiyo-complete-58-implementation-20261009-bu1BCi/`.
The WIP packet remains immutable and must not be integrated. The subsequent
extended red was 120 PASS / 44 FAIL, 58.23s. Initial green attempts were
140 PASS / 24 FAIL, 53.68s, then 162 PASS / 2 FAIL, 66.72s. Native pause/choice
test precision was corrected without removing the original 126 test nodes or
weakening their gameplay postconditions. The substantive stale list-one
receipt failures were fixed in owned child compilation/resolution/retargeting;
`keep` retains stale references and explicit retarget refreshes only its slot.
All 170 new cases subsequently passed in 63.72s, including the original eight
strict reds, with zero forbidden I/O attempts. The final whole-module cohort
also uses the existing canonical printed ward creature for Aura non-target
attachment controls. Exact final logs, XML, guard receipts, pre/post AST pins,
and parent-protecting apply checks are in the final handoff packet, separate
from the WIP archive. No full-backend, SQL, HTTP, browser, or cross-composed
Aura/control-layer certificate is claimed by this isolated qualification.

Additional actual departed-walker controls retain the zero-loyalty death LKI,
check native graveyard restoration of printed loyalty, and pay to copy that
same departed source through the real loyalty-copy target choice. Both seats
and mana/life casting branches verify uncast copied loyalty without changing
the shared native characteristic-restoration implementation.
