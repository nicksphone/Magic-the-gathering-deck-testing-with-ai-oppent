# Damage Source Controller Audit

Tests-only, on Jason's own numeric prevention + public graveyard inventory adapter +
legacy player shield veto composition. This is not the moving parent composition.

## Rules And Canonical Intake

Full Scryfall JSON was fetched before offline collection for Soul-Scar Mage,
Lightning Bolt, Twincast, Counterspell, Healing Salve, Prodigal Sorcerer,
Ray of Command and Torrential Gearhulk. See `source-controller-audit/raw/` for
complete records, URLs, intake time and hashes; no abbreviated invented Oracle.
The current official rules page linked the September 25, 2026 Comprehensive Rules:
https://magic.wizards.com/en/rules
https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt

CR 113.8 determines an activated ability's controller. That is distinct from
its damage source: CR 120.2b and 120.7 identify the object dealing damage;
608.2h uses current information for a source still in its expected public zone,
otherwise its last known information. CR 707.10 makes a spell copy a spell
controlled by the copier, without an associated physical spell card. CR 614.1
and 616.1/616.1e govern applicability and affected-player selection among
these competing conversion/prevention effects. Frame fields alone are not
rules proof; assertions check actual controlled permanents, paid actions,
competing options, resulting counters/damage and unspent shield quantities.

## Fixtures And Execution Boundary

Two finite families, both seats: opposing paid Twincast copying paid Bolt
(keep/retarget, including original paid Counterspell and physical source already
in graveyard); and real Ray control changes to a Prodigal Sorcerer before or
after its paid tap activation. Real prowess triggers above Ray/Twincast/counter
resolve via priority passes. Targets and Mage begin as declared canonical
retained-board objects, with explicitly funded pools and ready initial Sorcerer;
this is not a natural game or fresh-cast summoning-sickness claim. Before-activation
Ray supplies genuine haste. No synthetic StackItem, manual event or controller
assignment advances the tested episode. Standalone paid Bolt with/without Salve
and friendly copied damage are independent controls.

`inventory-adapter/run_pure.py` installs audit denial for sqlite3.connect and
all socket.* events before importing pytest, including native aliases. No HTTP,
SQL, dependency installation or production modification is used. Each gate has
an outer 600-second bound; helper priority loops have fixed fixture termination
checks, not search limits. Checked actions assert full original snapshot purity,
negative replacement choices retain full-root equality, cold snapshots restore
exactly, and decision views verify opponent hand/library opacity. Action traces
and full boundary snapshots are evidence, not a public training export.

## Ledgers

Initial 20: 8 PASS / 12 FAIL, 14.97s. Eight failures were a fixture assertion that
Twincast had departed before its pending target choice completed. The original
file/log/XML/traces are preserved. Only this assertion was moved after the real
checked target choice; no runtime repair or desired damage assertion changed.

Corrected 20 plus two unchanged control modules (46 numeric receipt cases,
30 control-frame cases): 92 PASS / 4 FAIL, 42.66s; no errors/skips/xfails.
Added two former-controller false-positive probes and two copy-keep controls.
Final whole NEW audit24: 18 PASS / 6 FAIL, 23.73s; no errors/skips/xfails.
The two unchanged modules remain 76/76 ordinary PASS in the prior whole gate;
no repeat of the historical 494-case campaign. These are 100 distinct cases,
not 196 distinct because some audit nodes were repeated.

## Actual Failure And Narrow Proposal

Four after-activation Ray rows: source ownership and pending ability controller
remain original seat, but the battlefield source is genuinely controlled by the
opponent. Its damage to the original seat's Gearhulk has new-controller Mage
conversion and a real numeric Salve shield eligible. Stack pre-query incorrectly
forces `source_controller=item.controller`, sees only the shield and does not
pause. Execution queries the real source controller and automatically converts:
one -1/-1 counter, numeric shield still three, no affected-player choice.

Two reverse rows: target and source are both currently controlled by the Ray
caster; the only Mage is controlled by the former source controller. The same
pre-query falsely offers that former-controller Mage alongside the numeric
shield. The strict test stops at this invalid offer; it does not force execution
of an inapplicable replacement or claim a tested stale-choice rejection.

Relevant frozen functions: stack_engine.resolve_top_of_stack replacement_options
pre-query, replacement._noncombat_damage_counter_candidates, and
handlers.deal_damage. The latter's current-source execution and copy LKI
normalization explain why all eight copied-Bolt checks pass on this source.
Proposal only: stop treating ability controller as damage-source controller
in the stack pre-query. Use a shared readonly source-characteristic/controller
projection consistent with execution: genuine spell copy's resolving controller,
live permanent source's current controller, retained last-known characteristics
when the source has legitimately departed. Preserve amount, prevention lock,
selected/used sources, numeric ordering, frame identity and physical PRE refs.
No production ownership or implementation is inferred from this report.

This audit does not cover copied activated abilities, arbitrary effect sequences,
combat multi-source allocation, every damage modifier, or all source departures.
