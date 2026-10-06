# Ordinary Spell and Printed Cycling Trigger Surfaces

The ordinary Instant/Sorcery compiler excludes the printed self-cycling
trigger paragraph only when the submitted Oracle surface also includes a
printed Cycling keyword line. The original CardInstance Oracle is not changed.
This keeps trigger-only compiler proxies, delayed trigger creation instructions,
and ordinary conditional instructions intact. No event dispatcher, token parser,
or optional-payment handler is changed.

Canonical qualification uses unchanged offline bulk records, both seats,
checked actions, actual human HTTP, private-opponent rejection, and exact SQLite
controller/state restore. Renewed Faith normal casting gains 6, not 8;
cycling still draws one and optionally gains 2. Resounding Roar normal casting
still grants +3/+3. Its targeted cycling trigger currently compiles +6/+6 without
binding a target: the ordinary strict failure is retained, not worked around.
Slice and Dice qualifies surface separation only, not actual mass damage.
Sunset Revelry and Final Fortune qualify text preservation only, not their
conditional or extra-turn runtime semantics.

Remaining strict repros cover Shark Typhoon cast-trigger instruction leakage
(two Sharks from one noncreature cast), and targeted Resounding Roar cycling.
Paid optional Drake Haven / Faith of the Devoted triggers remain explicitly
unsupported and must not grant an uncharged reward, even with mana available.
See REPORT.md and receipts for exact commands, source hashes, and counts.
