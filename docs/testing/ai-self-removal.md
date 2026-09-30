# Winning Self-Removal

## Implemented Behavior

Before ordinary development/attack heuristics, AI considers legal friendly battlefield targets for destruction-bearing spell, activated and loyalty actions. Target materialization can temporarily bypass the friendly-target strategy guard for this probe. An isolated state copy admits the fully declared action through the shared legality and cost checks, then resolves announced stack objects through the real engine. Only a projected win for the acting player promotes the action; the real match still announces it on the stack and permits responses normally.

Projection sets target/order choices as explicit for both seats. A separate AI instance with the same configured difficulty and archetype resolves only the actor's own choices; the authoritative state and actor's decision history remain untouched. Undeclared opposing choices stop projection. A change to either library or the opposing hand makes the result unknown, even if the engine reported a winner, rather than exploiting actual hidden card contents. Resolution is bounded to 128 actions. This is a pass-only response assumption, not a forced-win or complete opponent-search claim.

Candidate victims use the existing sacrifice-loss estimate. Recurring drain, draw and token clauses add retention value, derived from their own printed paragraphs after reminder-text removal. Entry-token rewards are not mistakenly counted as recurring just because another paragraph contains a death trigger. These are heuristic weights, not complete permanent valuation.

## Reproduced Comparison

Baseline agent: `da4dcf3`. Both agents receive the same canonical full-state fixture and legal moves on the updated engine. An opposing indestructible Darksteel Myr leaves no productive conventional destruction target. The actor controls Bastion of Remembrance and Sprite Dragon, holds Murder and has sufficient mana; the opponent has one life.

- Baseline: pass priority, conserving all friendly-target destruction.
- Updated: cast Murder on the friendly Sprite Dragon; its death queues Bastion's normal drain trigger and an unanswered line wins.

The fixture survives snapshot restore, and a legal actual cast plus priority passes verifies the game result. Fifteen parameter combinations cover Drain, Aristocrats, Midrange, Tempo and Control at casual, strong and master difficulty. Own Blood Artist target/order choices preserve a valid winning line; sacrificing Thrashing Brontodon as an activation cost and paying Vraska the Unseen's loyalty also work through the same projection path. Costs, indestructible and opposing Leyline of the Void are not waived. Opposing Blood Artist choices and hidden library movement remain unknown. Nonwinning self-removal remains conserved.

Four new Scryfall-ID/Oracle-ID-backed records supplement the existing canonical fixtures. Production changes contain no card-name rules or strategy exceptions. The isolated self-removal test file has 25 cases, including actual spell, activated-cost and loyalty execution, state preservation, replacements, uncertainty and source-retention valuation.

## Validation and Match Traces

The isolated backend full suite passes 1,675 tests. Frontend lint/build/unit and the complete Chromium action/recovery/BO3 harness pass. A three-game replay reports zero determinism failures or drift labels.

Eight traced games use Midrange/Drain seeds 830-831 and Tokens/Ramp seeds 840-841 with both seat orders. All finish without timeout, logged cast-time target/cost rejection or missing effect inference. Midrange wins four of four; Tokens/Ramp split two wins each. No game actually chooses the new self-removal line: these runs are regression smoke, not feature exercise, measured strategic improvement or balance evidence. Canonical fixtures establish the new behavior. Several blocking aggregates remain unavailable rather than being reported as measured zero.

State/action comparison and trace artifacts are retained locally under `/tmp/mtg-self-removal.VAGVMj/`, not shipped as a permanent training dataset. Test and simulation databases are isolated source copies, not the live user database.

## Known Limitations and Next Upgrades

Nonterminal self-removal value, alternative non-destruction targets, multi-action combo setup, exhaustive victim/action ranking, temporary protection and meaningful opposing replies remain open. The hidden-zone gate deliberately rejects some lines whose public payoff might be provable without knowing the moved cards. Own choices follow a configured heuristic, not an exhaustive optimal choice solver. An unanswered winning projection is only as correct as the supported engine effects; it does not certify arbitrary Oracle semantics or seasoned-player play. Wider seat-balanced archetype matrices and manual competitive-play review remain required.
