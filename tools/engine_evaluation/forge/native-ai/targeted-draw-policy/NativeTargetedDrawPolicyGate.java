// SPDX-License-Identifier: GPL-3.0-or-later
// Native integration for Forge Team/Card-Forge 61e9442c433711a82258daca3236f936a1d6f70e.
// Full canonical scripts and original notices retained; see LICENSE.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.ability.DrawAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.GameLossReason;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
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

public final class NativeTargetedDrawPolicyGate extends AITest {
    private record Pose(Game game, Player actor, Player enemy, Card source, List<Card> lands,
                        int enemyLibrary, int draws, int cost, boolean lethal) {}
    private static void engine(boolean value, String message) {
        if (!value) throw new IllegalStateException("FIXTURE_OR_ENGINE: " + message);
    }
    private static void policy(boolean value, String message) {
        if (!value) throw new AssertionError("POLICY_RED: " + message);
    }
    private static List<Integer> ids(Player p, ZoneType zone) {
        return p.getCardsIn(zone).stream().map(Card::getId).sorted().toList();
    }
    private static Map<String, Object> snapshot(Pose p) {
        Map<String, Object> row = new LinkedHashMap<>();
        Card current = p.game.getCardState(p.source);
        row.put("source_id", p.source.getId());
        row.put("native_current_source_id", current.getId());
        row.put("source_zone", current.getZone().getZoneType().name());
        row.put("own_library", ids(p.actor, ZoneType.Library));
        row.put("enemy_library", ids(p.enemy, ZoneType.Library));
        row.put("own_hand", ids(p.actor, ZoneType.Hand));
        row.put("enemy_hand", ids(p.enemy, ZoneType.Hand));
        row.put("tapped_lands", p.lands.stream().filter(Card::isTapped).map(Card::getId).sorted().toList());
        row.put("mana", p.actor.getManaPool().totalMana());
        row.put("phase", p.game.getPhaseHandler().getPhase().name());
        row.put("priority_id", p.game.getPhaseHandler().getPriorityPlayer().getId());
        row.put("actor_won", p.actor.hasWon());
        row.put("enemy_lost", p.enemy.hasLost());
        row.put("native_terminal", p.game.isGameOver());
        return row;
    }
    private Pose pose(int seat, String scene) {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("draw-policy-seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "Constructed targeted draw policy"));
        game.setAge(GameStage.Play);
        engine(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Unexpected search mode");
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        boolean opportunity = scene.equals("opportunity-equal"), lethal = scene.equals("empty-enemy");
        int draws = opportunity ? 4 : 2;
        int enemyLibrary = scene.endsWith("-equal") ? draws : lethal ? 0 : 1;
        fillLibrary(actor, 10); fillLibrary(enemy, enemyLibrary);
        actor.setLife(20, null); enemy.setLife(20, null);
        game.getPhaseHandler().devModeSet(lethal ? PhaseType.MAIN2 : PhaseType.END_OF_TURN, lethal ? actor : enemy);
        game.getPhaseHandler().onStackResolved();
        game.getPhaseHandler().setPriority(actor);
        List<Card> lands = addCards("Island", 6, actor);
        if (scene.equals("unfunded")) for (Card land : lands) land.setTapped(true);
        if (scene.equals("enemy-cannot-lose")) addCard("Platinum Angel", enemy);
        Card source = addCardToZone(opportunity ? "Opportunity" : "Inspiration", actor, ZoneType.Hand);
        game.getAction().checkStaticAbilities(); game.getAction().checkStateEffects(true);
        engine(game.getPhaseHandler().getPriorityPlayer() == actor
                && game.getPhaseHandler().is(lethal ? PhaseType.MAIN2 : PhaseType.END_OF_TURN)
                && game.getPhaseHandler().isPlayerTurn(lethal ? actor : enemy), "Wrong actual priority/phase/turn");
        engine(!game.isGameOver() && game.getStack().isEmpty() && actor.getManaPool().totalMana() == 0,
                "Invalid initial native game");
        if (scene.equals("enemy-cannot-lose")) engine(enemy.cantLoseCheck(GameLossReason.Milled)
                && actor.cantWin() && enemy.isCardInPlay("Platinum Angel"), "Canonical Angel guard inactive");
        return new Pose(game, actor, enemy, source, lands, enemyLibrary, draws, opportunity ? 6 : 4, lethal);
    }
    private void paid(Pose p, SpellAbility chosen, Player target, boolean expectWin, Map<String, Object> row) {
        engine(chosen.getHostCard().getId() == p.source.getId() && p.source.isInZone(ZoneType.Hand), "Wrong original source");
        engine(chosen.getTargets().size() == 1 && chosen.getTargets().contains(target), "Target changed before payment");
        List<Integer> own = ids(p.actor, ZoneType.Library), enemy = ids(p.enemy, ZoneType.Library);
        List<Integer> drawnFrom = target == p.actor ? own : enemy;
        row.put("target", target == p.actor ? "self" : "opponent");
        engine(((PlayerControllerAi) p.actor.getController()).playWithRollback(chosen, null), "Native payment failed");
        row.put("after_payment", snapshot(p));
        engine(p.game.getStack().peekAbility() == chosen && chosen.getHostCard().isInZone(ZoneType.Stack),
                "Exact selected ability not actually on native stack");
        engine(p.lands.stream().filter(Card::isTapped).count() == p.cost && p.actor.getManaPool().totalMana() == 0,
                "Wrong actual native land payment");
        engine(ids(p.actor, ZoneType.Library).equals(own) && ids(p.enemy, ZoneType.Library).equals(enemy)
                && p.actor.getCardsIn(ZoneType.Hand).isEmpty(), "Zones changed before native resolution");
        int n = 0;
        while (!p.game.getStack().isEmpty() && n++ < 8) {
            p.game.getStack().resolveStack(); p.game.getAction().checkStateEffects(true);
        }
        row.put("after_resolution", snapshot(p));
        row.put("paid_lands", p.cost); row.put("draw_instruction", p.draws);
        engine(p.game.getStack().isEmpty(), "Native stack did not finish");
        if (expectWin) {
            engine(p.game.isGameOver() && p.actor.hasWon() && p.enemy.hasLost()
                    && p.enemy.getOutcome().lossState == GameLossReason.Milled, "No native decking win");
            engine(ids(p.enemy, ZoneType.Hand).equals(enemy) && p.enemy.getCardsIn(ZoneType.Library).isEmpty()
                    && ids(p.actor, ZoneType.Library).equals(own) && p.actor.getCardsIn(ZoneType.Hand).isEmpty(),
                    "Wrong actual lethal draw movement");
            // Terminal source cleanup is recorded by native ID, not prescribed.
        } else {
            engine(p.game.getCardState(p.source).isInZone(ZoneType.Graveyard)
                    && ids(p.actor, ZoneType.Graveyard).equals(List.of(p.source.getId())), "Nonterminal source not in graveyard");
            List<Integer> hand = ids(target, ZoneType.Hand), library = ids(target, ZoneType.Library);
            engine(hand.size() == p.draws && library.size() == drawnFrom.size()-p.draws
                    && drawnFrom.containsAll(hand) && drawnFrom.containsAll(library)
                    && hand.stream().noneMatch(library::contains), "Wrong native draw destinations");
            Player other = target == p.actor ? p.enemy : p.actor;
            engine(ids(other, ZoneType.Library).equals(target == p.actor ? enemy : own)
                    && other.getCardsIn(ZoneType.Hand).isEmpty(), "Untargeted player zones changed");
            engine(!p.game.isGameOver() && !p.actor.hasLost() && !p.enemy.hasLost(), "Unexpected native outcome");
        }
        engine(p.lands.stream().filter(Card::isTapped).count() == p.cost, "Paid lands changed after resolution");
    }
    private void check(int seat, String scene, Map<String, Object> row) {
        Pose p = pose(seat, scene);
        Map<String, Object> before = snapshot(p); row.put("before", before);
        List<SpellAbility> choices = ((PlayerControllerAi) p.actor.getController()).chooseSpellAbilityToPlay();
        row.put("choice_count", choices == null ? 0 : choices.size()); row.put("after_choice", snapshot(p));
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        if (scene.equals("unfunded")) {
            policy(chosen == null, "Unfunded action selected");
            engine(before.equals(snapshot(p)), "Decline mutated native resources");
            return;
        }
        policy(chosen != null, "Fresh Default declined declared positive");
        policy(choices.size() == 1, "Multiple choices");
        Player target = p.lethal ? p.enemy : p.actor;
        policy(chosen.getTargets().size() == 1 && chosen.getTargets().contains(target), "Wrong native target");
        paid(p, chosen, target, p.lethal, row);
    }
    private void exactBoundaryExecution(int seat, String scene, Map<String, Object> row) throws Exception {
        Pose p = pose(seat, scene); row.put("before", snapshot(p));
        SpellAbility sa = p.source.getSpellAbilities().get(0); sa.setActivatingPlayer(p.actor);
        Method target = DrawAi.class.getDeclaredMethod("targetAI", Player.class, SpellAbility.class, boolean.class);
        target.setAccessible(true);
        row.put("native_targetAI_success", target.invoke(new DrawAi(), p.actor, sa, false));
        row.put("native_targetAI_opponent", sa.getTargets().contains(p.enemy));
        row.put("native_targetAI_self", sa.getTargets().contains(p.actor));
        // Independent trusted legal action, never an AI-choice pass.
        sa.resetTargets(); engine(sa.canTarget(p.enemy), "Boundary opponent target illegal");
        sa.getTargets().add(p.enemy); engine(sa.canPlay(), "Boundary explicit action illegal");
        paid(p, sa, p.enemy, false, row);
    }
    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110641L));
        NativeTargetedDrawPolicyGate test = new NativeTargetedDrawPolicyGate(); test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        Class<?> dependency = Class.forName("forge.evaluation.NativeTargetedDrawAudit");
        Object old = dependency.getConstructor().newInstance();
        Method oldCheck = dependency.getDeclaredMethod("aiCase", int.class, String.class, Map.class);
        oldCheck.setAccessible(true);
        List<Map<String, Object>> rows = new ArrayList<>(); int failures = 0, errors = 0;
        outer: for (String cohort : List.of("unchanged-audit12", "new-safety10", "trusted-exact-library4-not-ai")) {
            List<String> scenes = cohort.equals("unchanged-audit12")
                    ? List.of("inspiration-lethal", "opportunity-lethal", "safe-self", "avoid-selfdeck", "enemy-maniac", "enemy-hexproof")
                    : cohort.equals("new-safety10")
                    ? List.of("inspiration-equal", "opportunity-equal", "empty-enemy", "unfunded", "enemy-cannot-lose")
                    : List.of("inspiration-equal", "opportunity-equal");
            for (int seat : new int[]{0, 1}) for (String scene : scenes) {
                Map<String, Object> row = new LinkedHashMap<>(); rows.add(row);
                row.put("cohort", cohort); row.put("seat", seat); row.put("scene", scene);
                try {
                    if (cohort.equals("unchanged-audit12")) oldCheck.invoke(old, seat, scene, row);
                    else if (cohort.equals("new-safety10")) test.check(seat, scene, row);
                    else test.exactBoundaryExecution(seat, scene, row);
                    row.put("passed", true);
                } catch (Throwable failure) {
                    Throwable cause = failure instanceof InvocationTargetException ? failure.getCause() : failure;
                    row.put("passed", false); row.put("failure", cause.toString()); cause.printStackTrace(System.err);
                    if (cause instanceof AssertionError) failures++; else errors++;
                }
                Files.writeString(out.resolve("ledger.private.json"), new Gson().toJson(rows)+"\n");
                if (errors > 0) break outer;
            }
        }
        Files.writeString(out.resolve("summary.private.json"), new Gson().toJson(Map.of(
                "cases", rows, "passed", rows.size()-failures-errors, "failures", failures, "errors", errors,
                "declared_ai_cases", 22, "declared_supplemental_controls", 4, "natural_games", 0))+"\n");
        System.exit(errors > 0 ? 2 : failures > 0 ? 1 : 0);
    }
}
