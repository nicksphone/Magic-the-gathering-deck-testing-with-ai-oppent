// SPDX-License-Identifier: GPL-3.0-or-later
// Forge Team/Card-Forge integration; full upstream scripts and license retained.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.PlayerControllerAi;
import forge.game.Game;
import forge.game.card.Card;
import forge.game.card.CounterEnumType;
import forge.game.phase.PhaseType;
import forge.game.player.GameLossReason;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class NativeTargetedDrawSafetyGate extends AITest {
    private static void engine(boolean value, String message) {
        if (!value) throw new IllegalStateException("FIXTURE_OR_ENGINE: " + message);
    }
    private static void policy(boolean value, String message) {
        if (!value) throw new AssertionError("POLICY_RED: " + message);
    }
    private static Method method(Class<?> owner, String name, Class<?>... parameters) throws Exception {
        Method m = owner.getDeclaredMethod(name, parameters); m.setAccessible(true); return m;
    }
    private static <T> T part(Object pose, String name, Class<T> type) throws Exception {
        return type.cast(method(pose.getClass(), name).invoke(pose));
    }
    private static void resolve(Game game) {
        int n = 0;
        while (!game.getStack().isEmpty() && n++ < 10) {
            game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
        }
        engine(game.getStack().isEmpty(), "Native setup stack unfinished");
    }
    private void newCase(Object replacement, int seat, String scene, Map<String, Object> row) throws Exception {
        Class<?> owner = replacement.getClass();
        boolean bounce = scene.equals("jace-left-battlefield-positive");
        Object pose = method(owner, "pose", int.class, String.class, Map.class).invoke(replacement, seat,
                bounce ? "enemy-jace" : "positive-no-replacement", row);
        Game game = part(pose, "game", Game.class);
        Player actor = part(pose, "actor", Player.class), enemy = part(pose, "enemy", Player.class);
        Card source = part(pose, "source", Card.class);
        Card jace = part(pose, "jace", Card.class);
        if (bounce) {
            engine(jace.isInZone(ZoneType.Battlefield) && jace.getCounters(CounterEnumType.LOYALTY) == 4,
                    "Native paid Jace entry/printed loyalty missing");
            List<Card> bounceLands = addCards("Island", 2, enemy);
            Card roil = addCardToZone("Into the Roil", enemy, ZoneType.Hand);
            game.getPhaseHandler().setPriority(enemy);
            SpellAbility spell = roil.getSpellAbilities().get(0); spell.setActivatingPlayer(enemy);
            engine(spell.canTarget(jace), "Native Jace bounce target illegal"); spell.getTargets().add(jace);
            engine(spell.canPlay() && ((PlayerControllerAi) enemy.getController()).playWithRollback(spell, null),
                    "Native paid Into the Roil setup failed");
            engine(game.getStack().peekAbility() == spell && spell.getHostCard().isInZone(ZoneType.Stack)
                    && bounceLands.stream().allMatch(Card::isTapped) && enemy.getManaPool().totalMana() == 0,
                    "No actual paid two-Island Into the Roil stack entry");
            resolve(game);
            jace = game.getCardState(jace);
            engine(jace.isInZone(ZoneType.Hand) && game.getCardState(roil).isInZone(ZoneType.Graveyard)
                    && enemy.getCardsIn(ZoneType.Hand).size() == 1 && enemy.getCardsIn(ZoneType.Library).size() == 1
                    && actor.getCardsIn(ZoneType.Library).size() == 10 && actor.getCardsIn(ZoneType.Hand).size() == 1,
                    "Jace did not genuinely leave battlefield, or un-kicked bounce drew cards");
            row.put("bounce_setup", Map.of("trusted_not_ai", true, "source_id", roil.getId(), "jace_id", jace.getId(),
                    "paid_islands", 2, "jace_native_zone", "Hand", "bounce_source_native_zone", "Graveyard"));
        } else {
            game.getPhaseHandler().devModeSet(PhaseType.MAIN2, enemy);
            game.getPhaseHandler().onStackResolved(); game.getPhaseHandler().setPriority(enemy);
            List<Card> lands = addCards("Island", 4, enemy);
            Card insight = addCardToZone("Teferi's Ageless Insight", enemy, ZoneType.Hand);
            SpellAbility spell = insight.getSpellAbilities().get(0); spell.setActivatingPlayer(enemy);
            engine(spell.canPlay() && ((PlayerControllerAi) enemy.getController()).playWithRollback(spell, null),
                    "Native Teferi fixture cast failed");
            engine(game.getStack().peekAbility() == spell && spell.getHostCard().isInZone(ZoneType.Stack)
                    && lands.stream().allMatch(Card::isTapped) && enemy.getManaPool().totalMana() == 0,
                    "Teferi lacked actual four-Island payment/stack entry");
            resolve(game);
            engine(game.getCardState(insight).isInZone(ZoneType.Battlefield), "Native Teferi entry missing");
            row.put("teferi_setup", Map.of("trusted_not_ai", true, "source_id", insight.getId(), "paid_islands", 4));
        }
        game.getPhaseHandler().devModeSet(bounce ? PhaseType.END_OF_TURN : PhaseType.MAIN2, bounce ? enemy : actor);
        game.getPhaseHandler().onStackResolved(); game.getPhaseHandler().setPriority(actor);
        game.getAction().checkStaticAbilities(); game.getAction().checkStateEffects(true);
        engine(!game.isGameOver() && game.getStack().isEmpty() && game.getPhaseHandler().getPriorityPlayer() == actor
                && game.getPhaseHandler().is(bounce ? PhaseType.END_OF_TURN : PhaseType.MAIN2)
                && game.getPhaseHandler().isPlayerTurn(bounce ? enemy : actor), "Wrong fresh actor priority/phase");
        row.put("before_actor_choice", method(owner, "state", pose.getClass()).invoke(null, pose));
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        row.put("choice_count", choices == null ? 0 : choices.size());
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        policy(chosen != null, "Fresh Default declined declared new positive");
        policy(choices.size() == 1 && chosen.getHostCard().getId() == source.getId()
                && chosen.getTargets().contains(enemy), "Native choice not original Inspiration targeting enemy");
        method(owner, "payResolve", pose.getClass(), SpellAbility.class, Map.class).invoke(replacement, pose, chosen, row);
        policy(game.isGameOver() && actor.hasWon() && enemy.hasLost()
                && enemy.getOutcome().lossState == GameLossReason.Milled, "New positive lacked native Milled victory");
        engine(actor.getCardsIn(ZoneType.Library).size() == 10 && enemy.getCardsIn(ZoneType.Library).isEmpty()
                && enemy.getCardsIn(ZoneType.Hand).size() == (bounce ? 2 : 1), "New positive draw/source destinations wrong");
    }
    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]); MyRandom.setRandom(new Random(2026110683L));
        NativeTargetedDrawSafetyGate test = new NativeTargetedDrawSafetyGate(); test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        Object original = Class.forName("forge.evaluation.NativeTargetedDrawAudit").getConstructor().newInstance();
        Object firstPolicy = Class.forName("forge.evaluation.NativeTargetedDrawPolicyGate").getConstructor().newInstance();
        Object replacement = Class.forName("forge.evaluation.NativeTargetedDrawReplacementAudit").getConstructor().newInstance();
        List<Map<String, Object>> rows = new ArrayList<>(); int failures = 0, errors = 0;
        outer: for (String cohort : List.of("unchanged-original12", "unchanged-policy10", "unchanged-replacement8", "new-positive4", "trusted-replacement4-not-ai")) {
            List<String> scenes = cohort.equals("unchanged-original12")
                    ? List.of("inspiration-lethal", "opportunity-lethal", "safe-self", "avoid-selfdeck", "enemy-maniac", "enemy-hexproof")
                    : cohort.equals("unchanged-policy10")
                    ? List.of("inspiration-equal", "opportunity-equal", "empty-enemy", "unfunded", "enemy-cannot-lose")
                    : cohort.equals("unchanged-replacement8")
                    ? List.of("enemy-jace", "spirit-cap", "positive-no-replacement", "enemy-maniac")
                    : cohort.equals("new-positive4")
                    ? List.of("teferi-multiplier-positive", "jace-left-battlefield-positive") : List.of("enemy-jace", "spirit-cap");
            for (int seat : new int[]{0, 1}) for (String scene : scenes) {
                Map<String, Object> row = new LinkedHashMap<>(); rows.add(row);
                row.put("cohort", cohort); row.put("seat", seat); row.put("scene", scene);
                try {
                    if (cohort.equals("unchanged-original12")) method(original.getClass(), "aiCase", int.class, String.class, Map.class).invoke(original, seat, scene, row);
                    else if (cohort.equals("unchanged-policy10")) method(firstPolicy.getClass(), "check", int.class, String.class, Map.class).invoke(firstPolicy, seat, scene, row);
                    else if (cohort.equals("new-positive4")) test.newCase(replacement, seat, scene, row);
                    else method(replacement.getClass(), "check", int.class, String.class, boolean.class, Map.class).invoke(replacement, seat, scene, cohort.equals("trusted-replacement4-not-ai"), row);
                    row.put("passed", true);
                } catch (Throwable failure) {
                    Throwable cause = failure; while (cause instanceof InvocationTargetException) cause = cause.getCause();
                    row.put("passed", false); row.put("failure", cause.toString()); cause.printStackTrace(System.err);
                    if (cause instanceof AssertionError) failures++; else errors++;
                }
                Files.writeString(out.resolve("ledger.private.json"), new Gson().toJson(rows)+"\n");
                if (errors > 0) break outer;
            }
        }
        Files.writeString(out.resolve("summary.private.json"), new Gson().toJson(Map.of("cases", rows,
                "passed", rows.size()-failures-errors, "failures", failures, "errors", errors,
                "declared_ai_cases", 34, "declared_manual_controls", 4, "natural_games", 0))+"\n");
        System.exit(errors > 0 ? 2 : failures > 0 ? 1 : 0);
    }
}
