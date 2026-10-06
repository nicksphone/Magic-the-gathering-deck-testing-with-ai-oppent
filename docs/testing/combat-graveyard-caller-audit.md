# Combat Graveyard Caller Audit

Tests/report only; no combat, SBA, handler, keyword, cost, or API production edits.

## Frozen Composition

Published source: fc225406d56c1a2f177ccfa8fb0b6008448772f2, source-qualified.tar.gz
SHA256 75ba838e12ebde5414e42a71eb641aeeba0b851b2a5ba61c72a35ad50314e8d6.
Apply, in order:

1. Jason graveyard consumer production.patch, 7dce2be8e906b5d551f1f3c784900d9bb25492211513232bd2a7f7bee0716009.
2. Lagrange committed-entry emitter production.patch, 690317f8d373274114ed78eea64f0359e7e39d77159911ece9a12cf7e123f231.
3. Frozen keyword sacrifice product.patch, 6818a686e92586a9654030db8a342e28741e829f7802fbd33766a19522e35da3.

The emitter's integration artifact is sometimes called 4cee; that is not its
production patch hash. No moving parent source or unqualified retained-reference
shuffle helper is overlaid. Original22 consumer tests are copied unchanged.

## Episode Boundaries

All Oracle objects are full unchanged official frozen Scryfall bulk payloads.
The harness starts at an explicit retained main-phase position with canonical
cards in hand and library. Mana pools are explicitly funded fixture inputs;
this is not a naturally played land-development or AI performance benchmark.
Every relevant creature/enchantment/control-changing spell is actually cast,
paid, and resolved through checked priority actions. Normal attackers age through
real turn transitions; foreign-owned attackers use actual paid Act of Treason.
There is no manual summoning-sickness removal, damage mark, power rewrite,
keyword loss, or manufactured legal block.

Both seats execute checked attack, checked block, and automatic combat damage
through priority passing. Read-only wrapping of the real trigger collector
records LBF, actual entry, dies, LKI, and trigger collection without injecting
events. Snapshots and checked action histories are retained before and after
damage. Core checked actions prove caller-root immutability. Snapshot restoration
also runs in an independent Python subprocess. HTTP tests use actual ASGI routes
and isolated memory/file SQLite repositories, not a listening Uvicorn service;
they prove cold GET reload before/after damage and invalid request root/controller/
SQL invariance. They do not claim a causal external server restart episode.

## Strict Expected Semantics

Ordinary and Humility-suppressed deaths must enter the owner's graveyard with
one sequence advance and one real committed-entry event. Ordinary Traveler
produces one source/controller-correct dies trigger and Spirit after resolution.
Humility suppresses that reward without suppressing the actual zone transition.
Rest in Peace changes the actual destination to exile, advances the sequence,
and emits neither graveyard entry nor dies. Foreign ownership is established
by actual control-changing spell resolution, not an owner-field edit.

Paid Shadowspear is separately resolved on the opposing battlefield to remove
Darksteel Colossus's indestructible until end of turn. Canonical Deadly Recluse
then legally blocks and deals deathtouch combat damage. The printed library
replacement must survive keyword removal; there is no illegal Progenitus block.
Progenitus's full fixture is retained but no combat qualification is claimed.

## Inspected Caller Seams

Active damage reaches combat._remove_dead_creatures and apply_state_based_actions.
The current source has no _destroy_in_combat function. SBA's simultaneous lethal
batch uses replace_die_zone and directly assigns Zone.GRAVEYARD rather than the
shared validated graveyard executor. The individual SBA resume and older combat
resume have sibling direct assignments; reading them does not certify those
resume paths. This audit does not qualify legend rules, attachment death, combat
replacement choice protocols, handler migrations, or all-graveyard support.

Exact terminal outcomes and ordinary-red classifications belong in the frozen
REPORT.md. No xfail, skip, deselection, hard search cutoff, or weakened unknown
effect assertion is permitted in the authoritative whole-module audit.
