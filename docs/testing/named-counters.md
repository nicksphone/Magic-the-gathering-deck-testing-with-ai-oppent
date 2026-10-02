# Named counters, untap and private scry

## Engine changes

Permanent counter placement records a shared monotonic effect timestamp without
retiming the permanent or changing its battlefield incarnation. Adding another
counter of a kind retimes that kind; removing some does not retime the rest.
Snapshots persist the map, and older snapshots default to an empty map. Legacy
keyword counters use the permanent timestamp deterministically; their historical
placement time cannot be reconstructed from a snapshot that never stored it.
Ordinary zone resets clear timestamps together with counters; the existing
supported counter-persistence clause retains corresponding timestamps.

Keyword counters feed the same effective-keyword adapter used by combat,
targeting and public views. Their grants are interleaved with supported static
keyword effects by timestamp, with explicit can't-have overrides afterward.
Supported global creature keyword removal is included, so a newer flying counter
can restore flying after that older removal. Layer diagnostics include the
counter kind and timestamp. This is keyword-layer behavior, not full suppression
of every triggered, static or activated ability.

Stun uses one shared untap operation. A tapped battlefield permanent removes
one stun counter instead of untapping. Repeated untap instructions consume one
each. Already-untapped or off-battlefield objects do not spend counters. Turn
actions, explicit untap effects and supported counter-driven land animation use
this operation. Supported unconditional self-restrictions during the controller's
untap step prevent that turn-based attempt without spending stun; explicit spell
untaps can still attempt it. Entry into play untapped and AI scratch-state undo
operations are not untap events.

The Oracle parser accepts bounded unconditional named-counter clauses on an
announced target, the same recipient ('it'), or explicit 'this' objects. A plain
tap-and-put-counter instruction splits into two effects without promoting the
second half of a conditional or optional instruction. It preserves later
supported clauses. Impede Momentum's actual canonical text exposed a missing
scry path; it now resolves tap, three stun counters and scry in printed order.

## Scry and AI

Fixed-number scry creates a private choice for the affected player. Select any
bottom cards, including none, in bottommost-first order, then order remaining
cards topmost-first when necessary. The library changes only after both choices
are complete; IDs/ownership and the inspected library slice are checked before
commit. Choices and later effect continuations survive snapshots/restart. Scry
zero and empty/short libraries do not manufacture cards or cause a failed draw.
The operation emits a scried event after actual completion, including keeping
all inspected cards, but general Oracle scry-watchers/replacements remain gaps.

Both human seats use the existing selection/order controls; no alpha layout
redesign is included. AI uses the existing inspected-card ranking and keeps
lands needed for known curve/fixing rather than applying one threshold to every
deck. This is a bounded resource heuristic, not seasoned-player certification.
Proliferation compares keyword presence before/after engine-projected placement;
another redundant flying counter is not valued like a newly restored ability.

Empty spell Oracle data no longer produces invented damage/draw/counter effects
from names containing Bolt, Spike, Shock, Consider, Deluge or Counterspell.
Admission rejects missing Instant/Sorcery Oracle text (including required spell
faces), while legitimate empty vanilla-creature text remains allowed. Direct
engine callers receive an explicit missing-data diagnostic and no fabricated
effect. Canonical local seed/knowledge hydration continues to supply real text.

## Evidence and source

The rules reference is Wizards' [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
especially 122.1b/122.1d and 613.7c. The fetched reference is retained with test
evidence on RCHFiles rather than bundled in source. Eight canonical card fixtures
retain Scryfall IDs, API URLs and retrieval dates; fixtures are not invented
competitive decks or a claim that every clause of those cards is implemented.

`tests/test_named_counters.py` covers public keyword views, timestamps/removal,
can't-have overrides, zones/legacy snapshots, actual flying/reach block legality,
both-seat stun, canonical spell sequencing and missing-Oracle safeguards.
`tests/test_scry.py` covers owner validation, bad IDs, atomic ordered partitions,
snapshot continuation, empty/short libraries and AI decisions. The Chromium
fixture verifies seat-two private ordering, resumed draw and visible flying.

## Acceptance evidence

Final source checks on October 2, 2026:

- Isolated tracked-source checkout plus this milestone's changes: **2,578 backend
  tests passed**, with 283 deprecation warnings; no live database was used.
- Focused counters, scry, continuous effects, AI and hydration: **341 passed**,
  with 36 deprecation warnings.
- Frontend lint, unit contracts and TypeScript/Vite build passed. The sequential
  Chromium harness passed **104 scenario assertions**, including private seat-two
  scry ordering and continuation through a draw.
- Four-deck, six-pair seat-balanced smoke: **12 logical games**, each replayed
  twice, with zero reported determinism failures, timeouts or classified anomalies.
  This is repeatability evidence, not a balance or expert-play certificate.
- Evidence, including superseded failures and official rules provenance, is
  retained under the RCHFiles `diagnostics/named-counters/20261002T012221Z/`
  archive. Dependencies were reused rather than freshly installed; DOM-driven
  browser checks do not establish pointer ergonomics or visual quality.

## Known Limitations and Next Upgrades

- Shield counter consequences and their interaction with prevention, destruction,
  indestructible and competing affected-player replacements are next, not done.
- Decayed and Exalted keyword names are recognized, but their triggered effects
  and non-redundant ability-instance counts remain unsupported. Keyword variants,
  full non-keyword ability suppression and arbitrary layer dependencies remain
  unfinished; preflight reports these known families.
- Other untap restrictions, optional untap choices and competing untap replacements
  are not certified. No general counter movement/spending engine was added.
- Fixed-number scry is supported; dynamic X, replacements and arbitrary scry
  watchers are explicitly reported as gaps. Complex strategic scry decisions
  require deeper tactical evidence rather than heuristic win-rate claims.
- Metadata admission remains distinct from complete semantics and format legality.
  No-mana-cost casting and other unsupported families need independent fixtures.
- UI redesign, broad operational/security gates and expert AI remain open.
