// SPDX-License-Identifier: GPL-3.0-or-later
// Native test integration for Forge Team/Card-Forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Full unchanged card scripts are in canonical/; upstream license is ../../LICENSE.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.AiAbilityDecision;
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
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class NativeTargetedDrawAudit extends AITest {
    private static final long SEED = 2026110629L;
    private static final List<String> SCENES = List.of("inspiration-lethal", "opportunity-lethal",
            "safe-self", "avoid-selfdeck", "enemy-maniac", "enemy-hexproof");
    private record Pose(Game game, Player actor, Player enemy, Card source, List<Card> lands,
                        int ownLibrary, int enemyLibrary, int draws, int cost, boolean lethal) {}

    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private Pose pose(int seat, String scene) {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("targeted-draw-seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "Constructed targeted draw audit"));
        game.setAge(GameStage.Play);
        require(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Unexpected search mode");
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        boolean lethal = scene.endsWith("-lethal"), opportunity = scene.equals("opportunity-lethal");
        int ownLibrary = scene.equals("avoid-selfdeck") ? 1 : 10;
        int enemyLibrary = lethal || scene.equals("enemy-maniac") || scene.equals("enemy-hexproof") ? 1 : 10;
        fillLibrary(actor, ownLibrary);
        fillLibrary(enemy, enemyLibrary);
        actor.setLife(20, null);
        enemy.setLife(20, null);
        game.getPhaseHandler().devModeSet(lethal ? PhaseType.MAIN2 : PhaseType.END_OF_TURN,
                lethal ? actor : enemy);
        game.getPhaseHandler().onStackResolved();
        game.getPhaseHandler().setPriority(actor);
        List<Card> lands = addCards("Island", 6, actor);
        if (scene.equals("enemy-maniac")) addCard("Laboratory Maniac", enemy);
        if (scene.equals("enemy-hexproof")) addCard("Leyline of Sanctity", enemy);
        Card source = addCardToZone(opportunity ? "Opportunity" : "Inspiration", actor, ZoneType.Hand);
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        require(game.getPhaseHandler().getPriorityPlayer() == actor, "Actor lacks actual native priority");
        require(game.getPhaseHandler().is(lethal ? PhaseType.MAIN2 : PhaseType.END_OF_TURN)
                && game.getPhaseHandler().isPlayerTurn(lethal ? actor : enemy), "Wrong native phase/turn");
        require(!game.isGameOver() && game.getStack().isEmpty() && actor.getManaPool().totalMana() == 0,
                "Invalid initial native game");
        return new Pose(game, actor, enemy, source, lands, ownLibrary, enemyLibrary,
                opportunity ? 4 : 2, opportunity ? 6 : 4, lethal);
    }

    private static List<Integer> ids(Player player, ZoneType zone) {
        return player.getCardsIn(zone).stream().map(Card::getId).sorted().toList();
    }

    private static Map<String, Object> snapshot(Pose p) {
        Map<String, Object> s = new LinkedHashMap<>();
        s.put("source_id", p.source.getId());
        s.put("source_zone", p.game.getCardState(p.source).getZone().getZoneType().name());
        s.put("own_library_ids", ids(p.actor, ZoneType.Library));
        s.put("enemy_library_ids", ids(p.enemy, ZoneType.Library));
        s.put("own_hand_ids", ids(p.actor, ZoneType.Hand));
        s.put("enemy_hand_ids", ids(p.enemy, ZoneType.Hand));
        s.put("tapped_lands", p.lands.stream().filter(Card::isTapped).map(Card::getId).sorted().toList());
        s.put("mana", p.actor.getManaPool().totalMana());
        s.put("phase", p.game.getPhaseHandler().getPhase().name());
        s.put("priority_id", p.game.getPhaseHandler().getPriorityPlayer().getId());
        s.put("actor_won", p.actor.hasWon());
        s.put("enemy_lost", p.enemy.hasLost());
        s.put("native_game_over", p.game.isGameOver());
        return s;
    }

    private void paid(Pose p, SpellAbility chosen, Map<String, Object> row) {
        Player target = p.lethal ? p.enemy : p.actor;
        require(chosen.getHostCard().getId() == p.source.getId() && p.source.isInZone(ZoneType.Hand),
                "Choice is not the original hand source");
        require(chosen.getTargets().size() == 1 && chosen.getTargets().contains(target), "Wrong native target");
        row.put("native_target", target == p.enemy ? "opponent" : "self");
        List<Integer> drawnFrom = ids(target, ZoneType.Library);
        require(((PlayerControllerAi) p.actor.getController()).playWithRollback(chosen, null),
                "Native selected payment/cast failed");
        row.put("after_payment", snapshot(p));
        require(chosen.getHostCard().isInZone(ZoneType.Stack) && !p.game.getStack().isEmpty(),
                "No actual native stack entry");
        require(p.game.getStack().peekAbility() == chosen, "Selected ability identity changed on stack");
        require(p.lands.stream().filter(Card::isTapped).count() == p.cost
                && p.actor.getManaPool().totalMana() == 0, "Wrong actual native land payment");
        require(p.actor.getCardsIn(ZoneType.Hand).isEmpty()
                && p.actor.getCardsIn(ZoneType.Library).size() == p.ownLibrary
                && p.enemy.getCardsIn(ZoneType.Library).size() == p.enemyLibrary,
                "Unexpected zones before resolution");
        int n = 0;
        while (!p.game.getStack().isEmpty() && n++ < 8) {
            p.game.getStack().resolveStack();
            p.game.getAction().checkStateEffects(true);
        }
        row.put("after_resolution", snapshot(p));
        require(p.game.getStack().isEmpty(), "Stack did not finish");
        require(p.game.getCardState(p.source).isInZone(ZoneType.Graveyard)
                && ids(p.actor, ZoneType.Graveyard).equals(List.of(p.source.getId())),
                "Original source did not complete hand/stack/graveyard lifecycle");
        if (p.lethal) {
            require(p.enemy.getCardsIn(ZoneType.Library).isEmpty()
                    && ids(p.enemy, ZoneType.Hand).equals(drawnFrom)
                    && p.actor.getCardsIn(ZoneType.Hand).isEmpty()
                    && p.actor.getCardsIn(ZoneType.Library).size() == p.ownLibrary,
                    "Wrong actual lethal draw movement");
            require(p.game.isGameOver() && p.actor.hasWon() && p.enemy.hasLost()
                    && p.enemy.getOutcome().lossState == GameLossReason.Milled, "No native decking win");
        } else {
            List<Integer> hand = ids(p.actor, ZoneType.Hand), library = ids(p.actor, ZoneType.Library);
            require(hand.size() == p.draws && library.size() == p.ownLibrary-p.draws
                    && drawnFrom.containsAll(hand) && drawnFrom.containsAll(library)
                    && hand.stream().noneMatch(library::contains), "Wrong actual self draw movement");
            require(p.enemy.getCardsIn(ZoneType.Library).size() == p.enemyLibrary
                    && p.enemy.getCardsIn(ZoneType.Hand).isEmpty()
                    && !p.game.isGameOver() && !p.actor.hasLost() && !p.enemy.hasWon(),
                    "Self draw ended game or changed opponent zones");
        }
        row.put("paid_lands", p.cost);
        row.put("resolved_draw_instruction", p.draws);
    }

    private void aiCase(int seat, String scene, Map<String, Object> row) {
        Pose p = pose(seat, scene);
        Map<String, Object> before = snapshot(p);
        row.put("before", before);
        row.put("expected", scene.equals("avoid-selfdeck") ? "decline" : p.lethal ? "opponent-draw-win" : "self-draw");
        // This is deliberately the first policy/cost evaluation in this fresh game.
        List<SpellAbility> choices = ((PlayerControllerAi) p.actor.getController()).chooseSpellAbilityToPlay();
        row.put("choice_count", choices == null ? 0 : choices.size());
        row.put("after_choice", snapshot(p));
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        if (scene.equals("avoid-selfdeck")) {
            require(chosen == null, "Native chooser did not avoid self-decking");
            require(before.equals(snapshot(p)), "Decline mutated native resources or outcome");
            return;
        }
        // No probes, target repair, forced execution, retries or alternate seeds after decline.
        require(chosen != null, "STRICT_RED: fresh native Default declined declared positive");
        require(choices.size() == 1, "Unexpected multiple native choices");
        paid(p, chosen, row);
    }

    private void execution(int seat, String scene, Map<String, Object> row) {
        Pose p = pose(seat, scene);
        row.put("before", snapshot(p));
        SpellAbility sa = p.source.getSpellAbilities().get(0);
        sa.setActivatingPlayer(p.actor);
        require(sa.canTarget(p.enemy), "Execution opponent not a legal target");
        sa.getTargets().add(p.enemy);
        require(sa.canPlay(), "Explicit paid action not natively legal");
        paid(p, sa, row);
    }

    private void diagnostic(int seat, String scene, Map<String, Object> row) throws Exception {
        Pose p = pose(seat, scene);
        SpellAbility sa = p.source.getSpellAbilities().get(0);
        sa.setActivatingPlayer(p.actor);
        DrawAi draw = new DrawAi();
        AiAbilityDecision full = draw.canPlayWithSubs(p.actor, sa);
        row.put("full_canPlayWithSubs", full.toString());
        row.put("full_native_target_opponent", sa.getTargets().contains(p.enemy));
        Method method = DrawAi.class.getDeclaredMethod("checkApiLogic", Player.class, SpellAbility.class);
        method.setAccessible(true);
        AiAbilityDecision gate = (AiAbilityDecision) method.invoke(draw, p.actor, sa);
        row.put("checkApiLogic", gate.toString());
        row.put("native_target_opponent", sa.getTargets().contains(p.enemy));
        row.put("target_legal", sa.canTarget(p.enemy));
        require(!full.willingToPlay() && full.decision().name().equals("CantPlayAi")
                && !gate.willingToPlay() && gate.decision().name().equals("CantPlayAi")
                && sa.getTargets().contains(p.enemy), "Root hypothesis not reproduced by native gate");
    }

    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED));
        NativeTargetedDrawAudit test = new NativeTargetedDrawAudit();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        List<Map<String, Object>> rows = new ArrayList<>();
        int failures = 0, errors = 0;
        for (String cohort : List.of("ai-choice", "trusted-execution-not-ai", "separate-gate-diagnostic")) {
            List<String> scenes = cohort.equals("ai-choice") ? SCENES : SCENES.subList(0, 2);
            for (int seat : new int[]{0, 1}) for (String scene : scenes) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("cohort", cohort); row.put("seat", seat); row.put("scene", scene);
                rows.add(row);
                try {
                    if (cohort.equals("ai-choice")) test.aiCase(seat, scene, row);
                    else if (cohort.equals("trusted-execution-not-ai")) test.execution(seat, scene, row);
                    else test.diagnostic(seat, scene, row);
                    row.put("passed", true);
                } catch (Throwable failure) {
                    row.put("passed", false); row.put("failure", failure.toString());
                    if (failure instanceof AssertionError) failures++; else errors++;
                    failure.printStackTrace(System.err);
                }
                Files.writeString(out.resolve("ledger.private.json"), new Gson().toJson(rows)+"\n");
            }
        }
        Files.writeString(out.resolve("summary.private.json"), new Gson().toJson(Map.of(
                "seed", SEED, "cases", rows, "passed", rows.size()-failures-errors,
                "failures", failures, "errors", errors, "natural_games", 0))+"\n");
        System.exit(errors > 0 ? 2 : failures > 0 ? 1 : 0);
    }
}
