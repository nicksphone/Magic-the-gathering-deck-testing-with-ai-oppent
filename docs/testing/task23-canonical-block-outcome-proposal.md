# Task 2.3: Checked Block Outcome Goldens

## Scope

Tests-only on immutable `4ff6a814cb3488ddd5062b8794a68bf4f7eeeb15`.
No AI, rules, weights, plan, corpus, or original test changes. These are checked
engine endpoints, not an independent winning reference plan, full AI decision
certificate, D13 capture, or paid creature-acquisition qualification.

The full canonical Atraxa, Sprite Dragon, and Thalia objects come from the
published 155-card JSONL, SHA256
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
Rumbling Baloth uses the existing pinned complete official RAW fixture. No
Oracle text, printed keyword list, projected endpoint, or winner is rewritten.

All creatures are explicit old-board fixtures. Baloth gets declared +1/+1
counters and a flying layer effect to block flying Atraxa. The trample control
grants Atraxa trample through the existing object-bound keyword-effect seam.
The first-strike control gives canonical Thalia five +1/+1 counters and flying.
The effective-keyword control removes Atraxa's deathtouch through that same
seam while retaining the full printed definition. These grants are not certified
paid effects, and Atraxa's unused ETB ability is not exercised or qualified.

## Observed Outcomes

Both defending seats start at 20 life. The attacker is genuine canonical 7/7
Atraxa with flying, vigilance, deathtouch, and lifelink. The default blockers are
canonical 1/1 Sprite Dragon and countered 6/6 Rumbling Baloth.

| Checked Declaration | Defender Life | Attacker Life | Material Result |
| --- | --- | --- | --- |
| No block | 13 | 27 | All three survive |
| Sprite alone, no trample | 20 | 27 | Sprite dies; Atraxa and Baloth survive |
| Baloth alone, no trample | 20 | 27 | Baloth dies; Atraxa and Sprite survive |
| Both, no trample | 20 | 27 | All three die through actual simultaneous combat/SBA |
| Either alone, Atraxa granted trample | 14 | 27 | Chosen blocker dies; Atraxa survives |
| Countered 7/6 first-strike Thalia | 20 | 20 | Atraxa dies before regular damage; all blockers survive |
| 8/8 Baloth, deathtouch still effective | 20 | 27 | Both attacker and blocker die |
| 8/8 Baloth, deathtouch effectively removed | 20 | 27 | Atraxa dies; Baloth survives |

No winner is forced; all observed endpoints remain nonterminal. Deathtouch plus
trample assigns only one lethal damage to either single blocker, so six damage
gets through even against the 6/6. The implementation's original damage
assignment validator remains authoritative. Production AI is used only for the
offered damage-allocation choice, not to manufacture a block or endpoint.

The existing `evaluate_board` ranks the checked Sprite-sacrifice endpoint above
the Baloth-sacrifice endpoint in both seats. This is a scoped existing-evaluator
observation, not new calibrated card values or a complete block-policy proof.
The single-block/no-trample results show why fixed largest-blocker acceptance
is unsound: it prevents no additional life damage, fails to kill Atraxa, and
sacrifices more retained material on this board. Both blockers together are a
distinct legal alternative, not suppressed to make the single-block comparison
look optimal. Its two-card-for-Atraxa trade requires separate policy valuation.

## Consumer Acceptance Proposal

Use these actual endpoints as acceptance inputs for future tactical consumers;
do not turn a printed size, profile scalar, or declared answerability tag into
an unconditional winning/block-selection oracle. Preserve the full offered
block menu and actual effective traits. Prefer cheaper single-block sacrifice
only when life prevention, threat survival, relevant triggers, and future value
really match. Account separately for trample/deathtouch leakage, first strike,
multi-block kills, effective keyword removal, and material retained.

This proposal changes no production policy and asserts no complete-game optimum.
Unsupported projections must remain unknown rather than being replaced with
these endpoints, fixed reference replay, or a forced outcome. Full 260-case,
52-root, 13-style D13 named-horizon and causal-quality obligations are unchanged.

## Evidence And Limits

`test_task23_canonical_block_outcomes.py`: 14 actual checked cases, both seats,
including complete root/snapshot replay and wrong-actor rejection. Initial
whole NEW module: 14 PASS in 4.19s; existing rules were already correct, so this
is not a production RED-to-GREEN repair.

Bounded whole three-module cohort: NEW14 plus unchanged original draw12 and
allocation24, 50 PASS in 9.01s, zero skips and unexpected denials. First-fence
actual SQL/socket/process canaries and provider import denial precede project
collection. No SQLite connections (including memory), networking, subprocess,
provider operations, D13 runtime, SDK root/caps, or hosted private inputs used.
Cooperative Python audit scope is not a kernel or hostile-code isolation claim.

Every one of the 3,076 original committed files is checked before and after the
gates. The only public additions are this document and the NEW test module.
Generated graph outputs are a separate owned AST-only maintenance artifact.
