// SPDX-License-Identifier: GPL-3.0-or-later
// Derived from Forge Team/Card-Forge PermanentAi; local Chalice knowledge correction.
package forge.ai.ability;

import forge.ai.*;
import forge.card.CardStateName;
import forge.card.CardType.Supertype;
import forge.card.GamePieceType;
import forge.card.mana.ManaCost;
import forge.deck.CardPool;
import forge.deck.DeckSection;
import forge.game.ability.AbilityUtils;
import forge.game.ability.ApiType;
import forge.game.card.*;
import forge.game.cost.Cost;
import forge.game.keyword.Keyword;
import forge.game.keyword.KeywordInterface;
import forge.game.mana.ManaCostBeingPaid;
import forge.game.phase.PhaseHandler;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.staticability.StaticAbility;
import forge.game.staticability.StaticAbilityMode;
import forge.game.trigger.Trigger;
import forge.game.trigger.TriggerType;
import forge.game.zone.ZoneType;
import forge.item.IPaperCard;
import forge.item.PaperCard;
import org.apache.commons.lang3.StringUtils;

import java.util.EnumSet;
import java.util.HashMap;
import java.util.Map;

public class PermanentAi extends SpellAbilityAi {

    /**
     * Checks if the AI will play a SpellAbility based on its phase restrictions
     */
    @Override
    protected boolean checkPhaseRestrictions(final Player ai, final SpellAbility sa, final PhaseHandler ph) {
        final Card card = sa.getHostCard();

        if (card.hasKeyword("MayFlashSac") && !ai.canCastSorcery()) {
            // AiPlayDecision.AnotherTime
            return false;
        }

        // Wait for Main2 if possible
        return !ph.is(PhaseType.MAIN1) || !ph.isPlayerTurn(ai) || sa.hasParam("WithoutManaCost") || ComputerUtil.castPermanentInMain1(ai, sa);
    }

    /**
     * The rest of the logic not covered by the canPlayAI template is defined
     * here
     */
    @Override
    protected AiAbilityDecision checkApiLogic(final Player ai, final SpellAbility sa) {
        final Card source = sa.getHostCard();

        // check on legendary
        if (!source.ignoreLegendRule() && ai.isCardInPlay(source.getName())) {
            // TODO check the risk we'd lose the effect with bad timing
            // TODO Technically we're not checking if same card in play is also legendary, but this is a good enough approximation
            if (!source.hasSVar("AILegendaryException")) {
                return new AiAbilityDecision(0, AiPlayDecision.WouldDestroyLegend);
            } else {
                String specialRule = source.getSVar("AILegendaryException");
                if ("TwoCopiesAllowed".equals(specialRule)) {
                    // One extra copy allowed on the battlefield, e.g. Brothers Yamazaki
                    if (CardLists.count(ai.getCardsIn(ZoneType.Battlefield), CardPredicates.nameEquals(source.getName())) > 1) {
                        return new AiAbilityDecision(0, AiPlayDecision.WouldDestroyLegend);
                    }
                } else if ("AlwaysAllowed".equals(specialRule)) {
                    // Nothing to do here, check for Legendary is disabled
                } else {
                    // Unknown hint, assume two copies not allowed
                    return new AiAbilityDecision(0, AiPlayDecision.WouldDestroyLegend);
                }
            }
        }

        if (source.getType().hasSupertype(Supertype.World)) {
            CardCollection list = CardLists.getType(ai.getCardsIn(ZoneType.Battlefield), "World");
            if (!list.isEmpty()) {
                return new AiAbilityDecision(0, AiPlayDecision.WouldDestroyWorldEnchantment);
            }
        }

        ManaCost mana = sa.getPayCosts().getTotalMana();
        if (mana.countX() > 0) {
            final int xPay = ComputerUtilCost.setMaxXValue(sa, ai, false);
            if (source.hasConverge()) {
                int nColors = -1;
                for (int i = 0; i <= xPay; i++) {
                    sa.setXManaCostPaid(i);
                    int newColors = ComputerUtilMana.getConvergeCount(sa, ai);
                    if (newColors > nColors) {
                        nColors = newColors;
                    } else {
                        sa.setXManaCostPaid(i - 1);
                        break;
                    }
                }
            } else if (xPay <= 0) {
                return new AiAbilityDecision(0, AiPlayDecision.CantAffordX);
            }
        } else if (mana.isZero()) {
            // if mana is zero, but card mana cost does have X, then something is wrong
            ManaCost cardCost = source.getManaCost();
            if (cardCost != null && cardCost.countX() > 0) {
                return new AiAbilityDecision(0, AiPlayDecision.CostNotAcceptable);
            }
        }

        if ("SacToReduceCost".equals(sa.getParam("AILogic"))) {
            // reset X to better calculate
            sa.setXManaCostPaid(0);
            ManaCostBeingPaid paidCost = ComputerUtilMana.calculateManaCost(sa.getPayCosts(), sa, ai, true, 0, false);

            int generic = paidCost.getGenericManaAmount();
            // Set PayX here to maximum value.
            int xPay = ComputerUtilCost.setMaxXValue(sa, ai, false);
            // currently cards with SacToReduceCost reduce by 2 generic
            xPay = Math.min(xPay, generic / 2);
            sa.setXManaCostPaid(xPay);
        }

        if ("ChaliceOfTheVoid".equals(source.getSVar("AICurseEffect"))) {
            int maxX = sa.getXManaCostPaid(); // as set above
            CardCollection otherChalices = CardLists.filter(ai.getGame().getCardsIn(ZoneType.Battlefield), CardPredicates.nameEquals("Chalice of the Void"));
            Map<Integer, Integer> ownCandidates = chaliceFutureCounts(ai, ai);
            Map<Integer, Integer> opponentCandidates = chaliceFutureCounts(ai.getStrongestOpponent(), ai);
            outer: for (int i = 0; i <= maxX; i++) {
                for (Card chalice : otherChalices) {
                    if (chalice.getCounters(CounterEnumType.CHARGE) == i) {
                        continue outer; // already disabled, no point in adding another one
                    }
                }
                int ownCount = ownCandidates.getOrDefault(i, 0);
                int opponentCount = opponentCandidates.getOrDefault(i, 0);
                if (opponentCount > 3 && opponentCount >= ownCount * 2) {
                    sa.setXManaCostPaid(i);
                    return new AiAbilityDecision(100, AiPlayDecision.WillPlay);
                }
            }
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }

        for (KeywordInterface ki : source.getKeywords(Keyword.MULTIKICKER)) {
            String o = ki.getOriginal();
            String costStr = o.split(":")[1];
            final Cost cost = new Cost(costStr, false);
            if (!cost.hasManaCost()) {
                continue;
            }
            final ManaCost mkCost = cost.getTotalMana();

            ManaCost mCost = sa.getPayCosts().getTotalMana();
            boolean isZeroCost = mCost.isZero();
            for (int i = 0; i < 10; i++) {
                mCost = ManaCost.combine(mCost, mkCost);
                ManaCostBeingPaid mcbp = new ManaCostBeingPaid(mCost);
                if (!ComputerUtilMana.canPayManaCost(mcbp, sa, ai, false)) {
                    sa.setOptionalKeywordAmount(ki, i);
                    break;
                }
                sa.setOptionalKeywordAmount(ki, i + 1);
            }
            if (isZeroCost && sa.getOptionalKeywordAmount(ki) == 0) {
                sa.clearOptionalKeywordAmount();
                // Bail if the card cost was {0} and no multikicker was paid (e.g. Everflowing Chalice).
                // TODO: update this if there's ever a card where it makes sense to play it for {0} with no multikicker
                return new AiAbilityDecision(0, AiPlayDecision.CostNotAcceptable);
            }
        }

        // don't play cards without being able to pay the upkeep for
        boolean hasUpkeepCost = false;
        int upkeepLifeLoss = 0;
        Cost upkeepCost = new Cost("0", true);
        for (Trigger t : source.getTriggers()) {
            if (!TriggerType.Phase.equals(t.getMode())) {
                continue;
            }
            if (!"Upkeep".equals(t.getParam("Phase"))) {
                continue;
            }
            if (!t.matchesValidParam("ValidPlayer", ai)) {
                continue;
            }
            SpellAbility ab = t.ensureAbility();
            if (ab == null) {
                continue;
            }

            if (ApiType.Sacrifice.equals(ab.getApi())) {
                if (!ab.hasParam("UnlessCost")) {
                    continue;
                }
                hasUpkeepCost = true;
                upkeepCost.add(AbilityUtils.calculateUnlessCost(ab, ab.getParam("UnlessCost"), true));
            } else if (ApiType.LoseLife.equals(ab.getApi()) && !ab.usesTargeting()) {
                ab.setActivatingPlayer(ai);
                if (AbilityUtils.getDefinedPlayers(source, ab.getParam("Defined"), ab).contains(ai)) {
                    upkeepLifeLoss += AbilityUtils.calculateAmount(source, ab.getParam("LifeAmount"), ab);
                }
            }
        }

        if (hasUpkeepCost) {
            final SpellAbility emptyAbility = new SpellAbility.EmptySa(source, ai);
            emptyAbility.setPayCosts(upkeepCost);
            emptyAbility.setTargetRestrictions(sa.getTargetRestrictions());
            emptyAbility.setCardState(sa.getCardState());
            emptyAbility.setActivatingPlayer(ai);

            if (!ComputerUtilCost.canPayCost(emptyAbility, ai, true)) {
                return new AiAbilityDecision(0, AiPlayDecision.CantAfford);
            }
        }
        if (upkeepLifeLoss > 0 && (ai.getLife() <= upkeepLifeLoss
                || ComputerUtil.aiLifeInDanger(ai, true, upkeepLifeLoss))) {
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }

        // check for specific AI preferences
        if (source.hasSVar("AICastPreference")) {
            String pref = source.getSVar("AICastPreference");
            String[] groups = StringUtils.split(pref, "|");
            boolean dontCast = false;
            for (String group : groups) {
                String[] elems = StringUtils.split(group.trim(), '$');
                String param = elems[0].trim();
                String value = elems[1].trim();

                if (param.equals("MustHaveInHand")) {
                    // Only cast if another card is present in hand (e.g. Illusions of Grandeur followed by Donate)
                    boolean hasCard = ai.getCardsIn(ZoneType.Hand).anyMatch(CardPredicates.nameEquals(value));
                    if (!hasCard) {
                        dontCast = true;
                    }
                } else if (param.startsWith("MaxControlled")) {
                    // Only cast unless there are X or more cards like this on the battlefield under AI control already,
                    CardCollectionView valid = param.contains("Globally") ? ai.getGame().getCardsIn(ZoneType.Battlefield)
                            : ai.getCardsIn(ZoneType.Battlefield);
                    CardCollection ctrld = CardLists.filter(valid, CardPredicates.nameEquals(source.getName()));

                    int numControlled = 0;
                    if (param.endsWith("WithoutOppAuras")) {
                        // Check that the permanent does not have any auras attached to it by the opponent (this assumes that if
                        // the opponent cast an aura on the opposing permanent, it's not with good intentions, and thus it might
                        // be better to have a pristine copy of the card - might not always be a correct assumption, but sounds
                        // like a reasonable default for some cards).
                        for (Card c : ctrld) {
                            if (c.getEnchantedBy().isEmpty()) {
                                numControlled++;
                            } else {
                                for (Card att : c.getEnchantedBy()) {
                                    if (!att.getController().isOpponentOf(ai)) {
                                        numControlled++;
                                    }
                                }
                            }
                        }
                    } else {
                        numControlled = ctrld.size();
                    }

                    if (numControlled >= Integer.parseInt(value)) {
                        dontCast = true;
                    }
                } else if (param.equals("NumManaSources")) {
                    // Only cast if there are X or more mana sources controlled by the AI
                    CardCollection m = ComputerUtilMana.getAvailableManaSources(ai, true);
                    if (m.size() < Integer.parseInt(value)) {
                        dontCast = true;
                    }
                } else if (param.equals("NumManaSourcesNextTurn")) {
                    // Only cast if there are X or more mana sources controlled by the AI *or*
                    // if there are X-1 mana sources in play but the AI has an extra land in hand
                    CardCollection m = ComputerUtilMana.getAvailableManaSources(ai, true);
                    int extraMana = CardLists.count(ai.getCardsIn(ZoneType.Hand), CardPredicates.LANDS) > 0 ? 1 : 0;
                    if (source.getName().equals("Illusions of Grandeur")) {
                        // TODO: this is currently hardcoded for specific Illusions-Donate cost reduction spells, need to make this generic.
                        extraMana += Math.min(3, CardLists.filter(ai.getCardsIn(ZoneType.Battlefield), CardPredicates.nameEquals("Sapphire Medallion").or(CardPredicates.nameEquals("Helm of Awakening"))).size()) * 2; // each cost-reduction spell accounts for {1} in both Illusions and Donate
                    }
                    if (m.size() + extraMana < Integer.parseInt(value)) {
                        dontCast = true;
                    }
                } else if (param.equals("NeverCastIfLifeBelow")) {
                    // Do not cast this spell if AI life is below a certain threshold
                    if (ai.getLife() < Integer.parseInt(value)) {
                        dontCast = true;
                    }
                } else if (param.equals("NeverCastIfLifeAbove")) {
                    // Do not cast this spell if AI life is below a certain threshold
                    if (ai.getLife() > Integer.parseInt(value)) {
                        dontCast = true;
                    }
                } else if (param.equals("AlwaysCastIfLifeBelow")) {
                    if (ai.getLife() < Integer.parseInt(value)) {
                        dontCast = false;
                        break; // disregard other preferences, always cast as a last resort
                    }
                } else if (param.equals("AlwaysCastIfLifeAbove")) {
                    if (ai.getLife() > Integer.parseInt(value)) {
                        dontCast = false;
                        break; // disregard other preferences, always cast as a last resort
                    }
                } else if (param.equals("OnlyFromZone")) {
                    if (!source.getZone().getZoneType().toString().equals(value)) {
                        dontCast = true;
                        break; // limit casting to a specific zone only
                    }
                }
            }

            if (dontCast) {
                return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
            }
        }

        return new AiAbilityDecision(100, AiPlayDecision.WillPlay);
    }

    private static boolean chaliceIdentityKnown(Card card, Player observer) {
        if (card == null) {
            return false;
        }
        CardView view = card.getView();
        return view.canBeShownTo(observer.getView()) && view.canFaceDownBeShownTo(observer.getView());
    }

    private static Map<Integer, Integer> chaliceFutureCounts(Player owner, Player observer) {
        // Retain the existing disclosed-deck assumption; never reconstruct a deck from hidden zones.
        CardPool main = owner.getRegisteredPlayer().getDeck().getMain();
        Map<String, Integer> external = new HashMap<>();
        for (Map.Entry<DeckSection, CardPool> section : owner.getRegisteredPlayer().getDeck()) {
            if (section.getKey() != DeckSection.Main) {
                for (Map.Entry<PaperCard, Integer> entry : section.getValue()) {
                    external.merge(entry.getKey().getName(), entry.getValue(), Integer::sum);
                }
            }
        }

        CardCollection known = new CardCollection();
        EnumSet<ZoneType> potentialMayPlayZones = EnumSet.noneOf(ZoneType.class);
        for (ZoneType zone : ZoneType.STATIC_ABILITIES_SOURCE_ZONES) {
            for (Card card : observer.getGame().getCardsIn(zone)) {
                if (!chaliceIdentityKnown(card, observer)) {
                    continue;
                }
                known.add(card);
                for (StaticAbility ability : card.getStaticAbilities()) {
                    if (ability.checkMode(StaticAbilityMode.Continuous) && ability.zonesCheck()
                            && ability.hasParam("MayPlay") && !ability.hasParam("MayPlayDontGrantZonePermissions")) {
                        // Match native zone selection, but never evaluate private definitions or conditions.
                        if (ability.hasParam("AffectedDefined")) {
                            potentialMayPlayZones.addAll(ZoneType.STATIC_ABILITIES_SOURCE_ZONES);
                        } else if (ability.hasParam("AffectedZone")) {
                            potentialMayPlayZones.addAll(ZoneType.listValueOf(ability.getParam("AffectedZone")));
                        } else {
                            potentialMayPlayZones.add(ZoneType.Battlefield);
                        }
                    }
                }
            }
        }

        Map<String, Integer> spent = new HashMap<>();
        for (Card card : known) {
            if (!chaliceIdentityKnown(card, observer) || card.getOwner() != owner
                    || card.getGamePieceType() != GamePieceType.CARD || card.isTokenCard()
                    || !card.isCollectible() || card.isLKI() || card.isCloned()
                    || card.hasMergedCard() || card.getCopiedPermanent() != null
                    || chaliceMayCastAgain(card, owner, observer, potentialMayPlayZones)) {
                continue;
            }
            IPaperCard paper = card.getPaperCard();
            if (paper != null) {
                spent.merge(paper.getName(), 1, Integer::sum);
            }
        }
        // Any visible departure might be an external copy: reserve those before charging the main.
        for (Map.Entry<String, Integer> entry : spent.entrySet()) {
            entry.setValue(Math.max(0, entry.getValue() - external.getOrDefault(entry.getKey(), 0)));
        }

        Map<Integer, Integer> result = new HashMap<>();
        for (Map.Entry<PaperCard, Integer> entry : main) {
            PaperCard paper = entry.getKey();
            int removed = Math.min(entry.getValue(), spent.getOrDefault(paper.getName(), 0));
            spent.put(paper.getName(), spent.getOrDefault(paper.getName(), 0) - removed);
            int remaining = entry.getValue() - removed;
            ManaCost cost = paper.getRules().getManaCost();
            if (cost == null || remaining == 0) {
                continue;
            }
            int manaValue = cost.getCMC();
            if (manaValue == 0 && (paper.getRules().getType().isLand()
                    || (owner == observer && "Chalice of the Void".equals(paper.getName())))) {
                continue;
            }
            result.merge(manaValue, remaining, Integer::sum);
        }
        return result;
    }

    private static boolean chaliceMayCastAgain(Card card, Player owner, Player observer,
            EnumSet<ZoneType> potentialMayPlayZones) {
        for (CardPlayOption option : card.mayPlay(owner)) {
            if (chaliceIdentityKnown(option.getHost(), observer) && option.grantsZonePermissions()) {
                return true;
            }
        }
        ZoneType zone = card.getZone().getZoneType();
        for (SpellAbility spell : card.getSpellAbilities()) {
            if (spell.isSpell() && (spell.getRestrictions() == null || spell.getRestrictions().getZone() == null
                    || spell.getRestrictions().getZone() == zone
                    || zone.name().equals(spell.getParam("AdditionalActivationZone")))) {
                return true;
            }
        }
        if (zone == ZoneType.Graveyard && (card.hasKeyword(Keyword.FLASHBACK)
                || card.hasKeyword(Keyword.RETRACE) || card.hasKeyword(Keyword.JUMP_START)
                || card.hasKeyword(Keyword.ESCAPE) || card.hasKeyword(Keyword.DISTURB)
                || card.hasKeyword(Keyword.AFTERMATH) || card.hasKeyword(Keyword.HARMONIZE))) {
            return true;
        }
        // A visible active grant with unresolved applicability conservatively retains the candidate.
        return potentialMayPlayZones.contains(zone);
    }

    @Override
    protected AiAbilityDecision doTriggerNoCost(Player ai, SpellAbility sa, boolean mandatory) {
        if (mandatory) {
            return new AiAbilityDecision(50, AiPlayDecision.MandatoryPlay);
        }
        if (!sa.metConditions()) {
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }

        if (sa.hasParam("AILogic") && !checkAiLogic(ai, sa, sa.getParam("AILogic"))) {
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }
        final Cost cost = sa.getPayCosts();
        if (cost != null && !willPayCosts(ai, sa, cost, sa.getHostCard())) {
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }
        if (!checkPhaseRestrictions(ai, sa, ai.getGame().getPhaseHandler())) {
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }
        return checkApiLogic(ai, sa);
     }
}
