// SPDX-License-Identifier: GPL-3.0-or-later
// Derived from Forge Team/Card-Forge CounterAi; local critical counter targeting correction.
package forge.ai.ability;

import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.google.common.collect.Iterables;

import org.apache.commons.lang3.StringUtils;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;

import forge.ai.*;
import forge.game.Game;
import forge.game.ability.AbilityUtils;
import forge.game.ability.AbilityKey;
import forge.game.ability.ApiType;
import forge.game.ability.effects.CounterEffect;
import forge.game.card.Card;
import forge.game.card.CardCollectionView;
import forge.game.card.CardPredicates;
import forge.game.cost.Cost;
import forge.game.cost.CostDiscard;
import forge.game.cost.CostExile;
import forge.game.cost.CostSacrifice;
import forge.game.keyword.Keyword;
import forge.game.player.Player;
import forge.game.replacement.ReplaceLifeReduced;
import forge.game.replacement.ReplacementEffect;
import forge.game.replacement.ReplacementType;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.SpellAbilityStackInstance;
import forge.game.zone.ZoneType;
import forge.util.MyRandom;
import forge.util.collect.FCollectionView;

public class CounterAi extends SpellAbilityAi {

    @Override
    protected AiAbilityDecision checkApiLogic(Player ai, SpellAbility sa) {
        final Card source = sa.getHostCard();
        final String sourceName = ComputerUtilAbility.getAbilitySourceName(sa);
        final Game game = ai.getGame();
        int tgtCMC = 0;
        SpellAbility tgtSA = null;
        boolean selectedCritical = false;

        if (game.getStack().isEmpty()) {
            return new AiAbilityDecision(0, AiPlayDecision.TargetingFailed);
        }

        if ("Force of Will".equals(sourceName)) {
            if (!SpecialCardAi.ForceOfWill.consider(ai, sa)) {
                return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
            }
        }

        if (sa.usesTargeting()) {
            sa.resetTargets();
            Pair<SpellAbility, Boolean> selected = chooseOptionalCounterTarget(game, sa, ai);
            tgtSA = selected.getLeft();
            selectedCritical = selected.getRight();
            if (tgtSA == null) {
                return new AiAbilityDecision(0, AiPlayDecision.TargetingFailed);
            }

            if (sa.hasParam("UnlessCost") && "TargetedController".equals(sa.getParamOrDefault("UnlessPayer", "TargetedController"))) {
                Cost unlessCost = AbilityUtils.calculateUnlessCost(sa, sa.getParam("UnlessCost"), false);
                if (unlessCost.hasSpecificCostType(CostDiscard.class)) {
                    CostDiscard discardCost = unlessCost.getCostPartByType(CostDiscard.class);
                    if ("Hand".equals(discardCost.getType())) {
                        if (tgtSA.getActivatingPlayer().getCardsIn(ZoneType.Hand).size() < 2) {
                            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
                        }
                    }
                }
                // TODO check if Player can pay the unless cost?
            }

            sa.getTargets().add(tgtSA);
            if (tgtSA.getPayCosts().getTotalMana() != null) {
                tgtCMC = tgtSA.getPayCosts().getTotalMana().getCMC();
                tgtCMC += tgtSA.getPayCosts().getTotalMana().countX() > 0 ? 3 : 0; // TODO: somehow determine the value of X paid and account for it?
            }
        } else {
            // This spell doesn't target. Must be a "Counter All" or "Counter trigger" type of ability.
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }

        String unlessCost = sa.hasParam("UnlessCost") ? sa.getParam("UnlessCost").trim() : null;

        if (unlessCost != null && !unlessCost.endsWith(">")) {
            Player opp = tgtSA.getActivatingPlayer();
            int usableManaSources = ComputerUtilMana.getAvailableManaEstimate(opp);

            int toPay = 0;
            boolean setPayX = false;
            if (unlessCost.equals("X") && sa.getSVar(unlessCost).equals("Count$xPaid")) {
                setPayX = true;
                toPay = Math.min(ComputerUtilCost.setMaxXValue(sa, ai, true), usableManaSources + 1);
            } else {
                toPay = AbilityUtils.calculateAmount(source, unlessCost, sa);
            }

            if (toPay == 0) {
                return new AiAbilityDecision(0, AiPlayDecision.CantAffordX);
            }

            if (toPay <= usableManaSources) {
                // If this is a reusable Resource, feel free to play it most of the time
                if (!playReusable(ai, sa)) {
                    return new AiAbilityDecision(0, AiPlayDecision.CantAfford);
                }
            }

            if (setPayX) {
                sa.setXManaCostPaid(toPay);
            }
        }

        // TODO Improve AI

        // Will return true if this spell can counter (or is Reusable and can
        // force the Human into making decisions)

        // But really it should be more picky about how it counters things

        if (sa.hasParam("AILogic")) {
            String logic = sa.getParam("AILogic");
            if (logic.startsWith("MinCMC.")) { // TODO fix Daze and fold into AITgts
                int minCMC = Integer.parseInt(logic.substring(7));
                if (tgtCMC < minCMC) {
                    return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
                }
            } else if ("NullBrooch".equals(logic)) {
                if (!SpecialCardAi.NullBrooch.consider(ai, sa)) {
                    return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
                }
            }
        }

        // Specific constraints for the AI to use/not use counterspells against specific groups of spells
        boolean ctrCmc0ManaPerms = AiProfileUtil.getBoolProperty(ai, AiProps.ALWAYS_COUNTER_CMC_0_MANA_MAKING_PERMS);
        boolean ctrDamageSpells = AiProfileUtil.getBoolProperty(ai, AiProps.ALWAYS_COUNTER_DAMAGE_SPELLS);
        boolean ctrRemovalSpells = AiProfileUtil.getBoolProperty(ai, AiProps.ALWAYS_COUNTER_REMOVAL_SPELLS);
        boolean ctrPumpSpells = AiProfileUtil.getBoolProperty(ai, AiProps.ALWAYS_COUNTER_PUMP_SPELLS);
        boolean ctrAuraSpells = AiProfileUtil.getBoolProperty(ai, AiProps.ALWAYS_COUNTER_AURAS);
        boolean ctrOtherCounters = AiProfileUtil.getBoolProperty(ai, AiProps.ALWAYS_COUNTER_OTHER_COUNTERSPELLS);
        int ctrChanceCMC1 = AiProfileUtil.getIntProperty(ai, AiProps.CHANCE_TO_COUNTER_CMC_1);
        int ctrChanceCMC2 = AiProfileUtil.getIntProperty(ai, AiProps.CHANCE_TO_COUNTER_CMC_2);
        int ctrChanceCMC3 = AiProfileUtil.getIntProperty(ai, AiProps.CHANCE_TO_COUNTER_CMC_3);
        String ctrNamed = AiProfileUtil.getProperty(ai, AiProps.ALWAYS_COUNTER_SPELLS_FROM_NAMED_CARDS);
        boolean dontCounter = false;

        if (tgtCMC == 1 && !MyRandom.percentTrue(ctrChanceCMC1)) {
            dontCounter = true;
        } else if (tgtCMC == 2 && !MyRandom.percentTrue(ctrChanceCMC2)) {
            dontCounter = true;
        } else if (tgtCMC == 3 && !MyRandom.percentTrue(ctrChanceCMC3)) {
            dontCounter = true;
        }

        // TODO check against game changers

        if (tgtSA != null && tgtCMC < AiProfileUtil.getIntProperty(ai, AiProps.MIN_SPELL_CMC_TO_COUNTER)) {
            dontCounter = true;
            Card tgtSource = tgtSA.getHostCard();
            if ((tgtSource != null && tgtCMC == 0 && tgtSource.isPermanent() && !tgtSource.getManaAbilities().isEmpty() && ctrCmc0ManaPerms)
                    || (tgtSA.getApi() == ApiType.DealDamage || tgtSA.getApi() == ApiType.LoseLife || tgtSA.getApi() == ApiType.DamageAll && ctrDamageSpells)
                    || (tgtSA.getApi() == ApiType.Counter && ctrOtherCounters)
                    || ((tgtSA.getApi() == ApiType.Pump || tgtSA.getApi() == ApiType.PumpAll) && ctrPumpSpells)
                    || (tgtSA.getApi() == ApiType.Attach && ctrAuraSpells)
                    || (tgtSA.getApi() == ApiType.Destroy || tgtSA.getApi() == ApiType.DestroyAll || tgtSA.getApi() == ApiType.Sacrifice
                       || tgtSA.getApi() == ApiType.SacrificeAll && ctrRemovalSpells)) {
                dontCounter = false;
            }

            if (tgtSource != null && !ctrNamed.isEmpty() && !"none".equalsIgnoreCase(ctrNamed)) {
                for (String name : StringUtils.split(ctrNamed, ";")) {
                    if (name.equals(tgtSource.getName())) {
                        dontCounter = false;
                    }
                }
            }

            // should not refrain from countering a CMC X spell if that's the only CMC
            // counterable with that particular counterspell type (e.g. Mental Misstep vs. CMC 1 spells)
            if (sa.getParamOrDefault("ValidTgts", "").startsWith("Card.cmcEQ")) {
                int validTgtCMC = AbilityUtils.calculateAmount(source, sa.getParam("ValidTgts").substring(10), sa);
                if (tgtCMC == validTgtCMC) {
                    dontCounter = false;
                }
            }
        }

        // Should ALWAYS counter if it doesn't spend a card, otherwise it wastes an opportunity
        // to gain card advantage
        if (sa.isAbility()
                && (!sa.getPayCosts().hasSpecificCostType(CostDiscard.class))
                && (!sa.getPayCosts().hasSpecificCostType(CostSacrifice.class))
                && (!sa.getPayCosts().hasSpecificCostType(CostExile.class))) {
            // TODO: maybe also disallow CostPayLife?
            dontCounter = false;
        }

        // Null Brooch is special - it has a discard cost, but the AI will be
        // discarding no cards, or is playing a deck where discarding is a benefit
        // as defined in SpecialCardAi.NullBrooch
        if (sa.hasParam("AILogic")) {
            if ("NullBrooch".equals(sa.getParam("AILogic"))) {
                dontCounter = false;
            }
        }

        if (dontCounter && !selectedCritical) {
            return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
        }

        return new AiAbilityDecision(100, AiPlayDecision.WillPlay);
    }

    private Pair<SpellAbility, Boolean> chooseOptionalCounterTarget(Game game, SpellAbility sa, Player ai) {
        SpellAbility firstEligible = null;
        final Card source = sa.getHostCard();
        // Same native stack order as chooseTargetSpellAbility, without its mandatory fallback.
        for (SpellAbilityStackInstance instance : game.getStack()) {
            final SpellAbility candidate = instance.getSpellAbility();
            if (!sa.canTargetSpellAbility(candidate) || candidate.getActivatingPlayer() == null
                    || !candidate.getActivatingPlayer().isOpponentOf(ai) || !candidate.isCounterableBy(sa)) {
                continue;
            }
            if (sa.hasParam("ConditionWouldDestroy") && !CounterEffect.checkForConditionWouldDestroy(sa, candidate)) {
                continue;
            }
            if (sa.hasParam("AITgts") && (candidate.getHostCard() == null
                    || !candidate.getHostCard().isValid(sa.getParam("AITgts"), sa.getActivatingPlayer(), source, sa))) {
                continue;
            }
            if (firstEligible == null) {
                firstEligible = candidate;
            }
            if (isCriticalDamageTarget(ai, candidate)) {
                return new ImmutablePair<>(candidate, true);
            }
        }
        return new ImmutablePair<>(firstEligible, false);
    }

    private boolean isCriticalDamageTarget(Player ai, SpellAbility target) {
        final Card source = target.getHostCard();
        if (source == null || !source.getView().canBeShownTo(ai.getView())
                || !source.getView().canFaceDownBeShownTo(ai.getView())) {
            return false;
        }
        if (target.getApi() != ApiType.DealDamage || target.isWrapper() || target.isTrigger()
                || target.isOptionalTrigger() || target.getParent() != null || target.getSubAbility() != null
                || !target.getAdditionalAbilities().isEmpty() || !target.getAdditionalAbilityLists().isEmpty()
                || !target.usesTargeting() || !Iterables.contains(target.getTargets().getTargetPlayers(), ai)
                || !target.canTarget(ai, true)) {
            return false;
        }
        // Only plain literal targeted damage: unknown semantic parameters do not earn an override.
        // This excludes conditions, optional/unless effects, alternate sources and divided damage.
        for (String parameter : target.getMapParams().keySet()) {
            if (!parameter.equals("SP") && !parameter.equals("AB") && !parameter.equals("DB")
                    && !parameter.equals("Cost") && !parameter.equals("ValidTgts")
                    && !parameter.equals("NumDmg") && !parameter.equals("SpellDescription")
                    && !parameter.equals("StackDescription") && !parameter.equals("TgtPrompt")) {
                return false;
            }
        }
        final String amount = target.getParam("NumDmg");
        if (amount == null || !amount.matches("[1-9][0-9]*")
                || source.isInfectDamage(ai) || source.hasKeyword(Keyword.LIFELINK)
                || !ai.canLoseLife() || ai.cantLoseForZeroOrLessLife()) {
            return false;
        }
        final int damage;
        try {
            damage = Integer.parseInt(amount);
        } catch (NumberFormatException ex) {
            return false;
        }
        // Native replacement/prevention estimate, not a complete or observer-fenced simulation.
        final int predictedDamage = ComputerUtilCombat.predictDamageTo(ai, damage, source, false);
        return predictedDamage >= ai.getLife() && !hasPublicLifeReducedUncertainty(ai, predictedDamage);
    }

    private boolean hasPublicLifeReducedUncertainty(Player ai, int damage) {
        final Game game = ai.getGame();
        final Map<AbilityKey, Object> event = AbilityKey.mapFromAffected(ai);
        event.put(AbilityKey.Amount, damage);
        event.put(AbilityKey.IsDamage, true);
        for (Card card : game.getCardsIn(ZoneType.STATIC_ABILITIES_SOURCE_ZONES)) {
            // Never inspect replacement collections on hidden sources, including face-down exile.
            if (!card.getView().canBeShownTo(ai.getView())
                    || !card.getView().canFaceDownBeShownTo(ai.getView())) {
                continue;
            }
            for (ReplacementEffect replacement : card.getReplacementEffects()) {
                if (replacement.getMode() != ReplacementType.LifeReduced || replacement.isSuppressed()
                        || replacement.hasRun() || !replacement.zonesCheck(game.getZoneOf(card))) {
                    continue;
                }
                // Only this native implementation has the bounded applicability contract below.
                if (replacement.getClass() != ReplaceLifeReduced.class
                        || !hasPublicLifeReducedApplicability(replacement)) {
                    return true;
                }
                if (!replacement.canReplace(event)) {
                    continue;
                }
                // Unknown requirements are not evaluated and cannot establish certain lethality.
                if (!hasPublicLifeReducedRequirements(replacement) || replacement.requirementsCheck(game)) {
                    return true;
                }
            }
        }
        return false;
    }

    private boolean hasPublicLifeReducedApplicability(ReplacementEffect replacement) {
        return replacement.getParamOrDefault("ValidPlayer", "Player")
                    .matches("(?:You|Opponent|Player)(?:\\.life(?:LT|LE|EQ|GE|GT|NE)-?[0-9]{1,9})?")
                && replacement.getParamOrDefault("IsDamage", "True").matches("True|False")
                && replacement.getParamOrDefault("Result", "GE0").matches("(?:LT|LE|EQ|GE|GT|NE)-?[0-9]{1,9}");
    }

    private boolean hasPublicLifeReducedRequirements(ReplacementEffect replacement) {
        // All other native common requirements (including SVar/defined/private-zone queries)
        // remain unresolved. Replacement output is deliberately not constructed or executed.
        if (!Set.of("Event", "ActiveZones", "Layer", "Description", "ReplaceWith", "ValidPlayer",
                "IsDamage", "Result", "PlayerTurn", "ActivePhases", "IsPresent", "PresentZone",
                "PresentPlayer", "PresentCompare").containsAll(replacement.getMapParams().keySet())) {
            return false;
        }
        if (replacement.hasParam("PlayerTurn") && !"True".equals(replacement.getParam("PlayerTurn"))) {
            return false;
        }
        return (!replacement.hasParam("IsPresent") || replacement.getParam("IsPresent")
                    .matches("(?:Card|Permanent|Creature|Artifact|Enchantment|Land|Planeswalker|Battle)(?:\\.(?:YouCtrl|OppCtrl))?"))
                && "Battlefield".equals(replacement.getParamOrDefault("PresentZone", "Battlefield"))
                && replacement.getParamOrDefault("PresentPlayer", "Any").matches("You|Opponent|Any")
                && replacement.getParamOrDefault("PresentCompare", "GE1").matches("(?:LT|LE|EQ|GE|GT|NE)-?[0-9]{1,9}");
    }

    @Override
    public AiAbilityDecision chkDrawback(Player aiPlayer, SpellAbility sa) {
        return doTriggerNoCost(aiPlayer, sa, true);
    }

    @Override
    protected AiAbilityDecision doTriggerNoCost(Player ai, SpellAbility sa, boolean mandatory) {
        final Game game = ai.getGame();

        if (sa.usesTargeting()) {
            if (game.getStack().isEmpty()) {
                return new AiAbilityDecision(0, AiPlayDecision.TargetingFailed);
            }

            sa.resetTargets();
            if (mandatory && !sa.canAddMoreTarget()) {
                return new AiAbilityDecision(100, AiPlayDecision.WillPlay);
            }
            Pair<SpellAbility, Boolean> pair = chooseTargetSpellAbility(game, sa, ai, mandatory);
            SpellAbility tgtSA = pair.getLeft();

            if (tgtSA == null) {
                return new AiAbilityDecision(0, AiPlayDecision.TargetingFailed);
            }
            sa.getTargets().add(tgtSA);
            if (!mandatory && !pair.getRight()) {
                // If not mandatory and not preferred, bail out after setting target
                return new AiAbilityDecision(0, AiPlayDecision.CantPlayAi);
            }

            String unlessCost = sa.hasParam("UnlessCost") ? sa.getParam("UnlessCost").trim() : null;

            final Card source = sa.getHostCard();
            if (unlessCost != null) {
                Player opp = tgtSA.getActivatingPlayer();
                int usableManaSources = ComputerUtilMana.getAvailableManaEstimate(opp);

                int toPay = 0;
                boolean setPayX = false;
                if (unlessCost.equals("X") && sa.getSVar(unlessCost).equals("Count$xPaid")) {
                    setPayX = true;
                    toPay = ComputerUtilCost.setMaxXValue(sa, ai, true);
                } else {
                    toPay = AbilityUtils.calculateAmount(source, unlessCost, sa);
                }

                if (!mandatory) {
                    if (toPay == 0) {
                        return new AiAbilityDecision(0, AiPlayDecision.CantAffordX);
                    }

                    if (toPay <= usableManaSources) {
                        // If this is a reusable Resource, feel free to play it most of the time
                        if (!playReusable(ai,sa) || (MyRandom.getRandom().nextFloat() < .4)) {
                            return new AiAbilityDecision(0, AiPlayDecision.CantAfford);
                        }
                    }
                }

                if (setPayX) {
                    sa.setXManaCostPaid(toPay);
                }
            }
        }

        // TODO Improve AI

        // Will return true if this spell can counter (or is Reusable and can
        // force the Human into making decisions)

        // But really it should be more picky about how it counters things
        return new AiAbilityDecision(100, AiPlayDecision.WillPlay);
    }

    public Pair<SpellAbility, Boolean> chooseTargetSpellAbility(Game game, SpellAbility sa, Player ai, boolean mandatory) {
        SpellAbility tgtSA;
        SpellAbility leastBadOption = null;
        SpellAbility bestOption = null;

        Iterator<SpellAbilityStackInstance> it = game.getStack().iterator();
        SpellAbilityStackInstance si = null;
        while (it.hasNext()) {
            si = it.next();
            tgtSA = si.getSpellAbility();
            if (!sa.canTargetSpellAbility(tgtSA)) {
                continue;
            }
            if (leastBadOption == null) {
                leastBadOption = tgtSA;
            }

            if ((tgtSA.isSpell() && !tgtSA.isCounterableBy(sa)) ||
                tgtSA.getActivatingPlayer() == ai ||
                !tgtSA.getActivatingPlayer().isOpponentOf(ai)) {
                // Is this a "better" least bad option
                if (leastBadOption.getActivatingPlayer().isOpponentOf(ai)) {
                    // NOOP
                } else if (sa.getActivatingPlayer().isOpponentOf(ai)) {
                    // Target opponents uncounterable stuff, before our own stuff
                    leastBadOption = tgtSA;
                }
                continue;
            }

            if (bestOption == null) {
                bestOption = tgtSA;
            } else {
                // TODO Determine if this option is better than the current best option
                boolean betterThanBest = false;
                if (betterThanBest) {
                    bestOption = tgtSA;
                }
                // Don't really need to keep updating leastBadOption once we have a bestOption
            }
        }

        return new ImmutablePair<>(bestOption != null ? bestOption : leastBadOption, bestOption != null);
    }

    @Override
    public boolean willPayUnlessCost(Player payer, SpellAbility sa, Cost cost, boolean alreadyPaid, FCollectionView<Player> payers) {
        final Card source = sa.getHostCard();
        final Game game = source.getGame();
        List<SpellAbility> spells = AbilityUtils.getDefinedSpellAbilities(source, sa.getParamOrDefault("Defined", "Targeted"), sa);
        for (SpellAbility toBeCountered : spells) {
            // ward or human misplay
            if (!toBeCountered.isCounterableBy(sa)) {
                return false;
            }

            if (toBeCountered.isSpell()) {
                Card spellHost = toBeCountered.getHostCard();
                Card gameCard = game.getCardState(spellHost, null);
                // Spell Host already left the Stack Zone
                if (gameCard == null || !gameCard.isInZone(ZoneType.Stack) || !gameCard.equalsWithGameTimestamp(spellHost)) {
                    return false;
                }
            }

            // no reason to pay if we don't plan to confirm
            if (toBeCountered.isOptionalTrigger() && !SpellApiToAi.Converter.get(toBeCountered).doTriggerNoCostWithSubs(payer, toBeCountered, false).willingToPlay()) {
                return false;
            }
            // TODO check hasFizzled
        }
        CardCollectionView hand = payer.getCardsIn(ZoneType.Hand);
        if (cost.hasSpecificCostType(CostDiscard.class)) {
            CostDiscard discard = cost.getCostPartByType(CostDiscard.class);
            String type = discard.getType();
            if (type.equals("Hand")) {
                if (hand.isEmpty()) {
                    return true;
                }

                // TODO how to check if the Spell on the Stack is more valuable than the Cards in Hand?
                int spellSum = spells.stream().map(SpellAbility::getHostCard).filter(CardPredicates.CREATURES).mapToInt(ComputerUtilCard::evaluateCreature).sum();
                int handSum = hand.stream().filter(CardPredicates.CREATURES).mapToInt(ComputerUtilCard::evaluateCreature).sum();
                if (spellSum <= handSum) {
                    return false;
                }
            }
        }

        return super.willPayUnlessCost(payer, sa, cost, alreadyPaid, payers);
    }
}
