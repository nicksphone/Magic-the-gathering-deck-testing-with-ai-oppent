// SPDX-License-Identifier: GPL-3.0-or-later
// Full canonical Forge Team/Card-Forge programs, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Native constructed-position tests, not natural-game or arbitrary-replacement certification. See LICENSE.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.card.CounterEnumType;
import forge.game.phase.PhaseType;
import forge.game.player.GameLossReason;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class NativeTargetedDrawReplacementAudit extends AITest {
    private record Pose(Game game, Player actor, Player enemy, Card source, List<Card> lands, Card jace) {}
    private static void engine(boolean value, String message) {
        if (!value) throw new IllegalStateException("FIXTURE_OR_ENGINE: " + message);
    }
    private static void policy(boolean value, String message) {
        if (!value) throw new AssertionError("POLICY_RED: " + message);
    }
    private static List<Integer> ids(Player p, ZoneType zone) {
        return p.getCardsIn(zone).stream().map(Card::getId).sorted().toList();
    }
    private static Map<String, Object> state(Pose p) {
        Map<String, Object> r = new LinkedHashMap<>();
        Card source = p.game.getCardState(p.source);
        r.put("source_id", p.source.getId()); r.put("current_source_id", source.getId());
        r.put("source_zone", source.getZone().getZoneType().name());
        r.put("own_library", ids(p.actor, ZoneType.Library)); r.put("enemy_library", ids(p.enemy, ZoneType.Library));
        r.put("own_hand", ids(p.actor, ZoneType.Hand)); r.put("enemy_hand", ids(p.enemy, ZoneType.Hand));
        r.put("tapped_lands", p.lands.stream().filter(Card::isTapped).map(Card::getId).sorted().toList());
        r.put("mana", p.actor.getManaPool().totalMana());
        r.put("native_terminal", p.game.isGameOver()); r.put("actor_won", p.actor.hasWon()); r.put("enemy_won", p.enemy.hasWon());
        r.put("actor_lost", p.actor.hasLost()); r.put("enemy_lost", p.enemy.hasLost());
        if (p.enemy.getOutcome() != null) {
            r.put("enemy_alt_win_source", p.enemy.getOutcome().altWinSourceName);
            r.put("enemy_loss_reason", String.valueOf(p.enemy.getOutcome().lossState));
        }
        if (p.jace != null) {
            Card jace = p.game.getCardState(p.jace);
            r.put("jace_id", jace.getId()); r.put("jace_zone", jace.getZone().getZoneType().name());
            r.put("jace_loyalty", jace.getCounters(CounterEnumType.LOYALTY));
        }
        return r;
    }
    private static void resolve(Game game) {
        int n = 0;
        while (!game.getStack().isEmpty() && n++ < 10) {
            game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
        }
        engine(game.getStack().isEmpty(), "Native stack did not finish");
    }
    private Card enterJace(Game game, Player enemy, Map<String, Object> row) {
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, enemy);
        game.getPhaseHandler().onStackResolved(); game.getPhaseHandler().setPriority(enemy);
        List<Card> lands = addCards("Island", 4, enemy);
        Card original = addCardToZone("Jace, Wielder of Mysteries", enemy, ZoneType.Hand);
        SpellAbility spell = original.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
        spell.setActivatingPlayer(enemy);
        engine(spell.canPlay(), "Jace fixture cast not natively legal");
        engine(((PlayerControllerAi) enemy.getController()).playWithRollback(spell, null), "Jace native paid setup failed");
        engine(game.getStack().peekAbility() == spell && spell.getHostCard().isInZone(ZoneType.Stack)
                && lands.stream().allMatch(Card::isTapped) && enemy.getManaPool().totalMana() == 0,
                "Jace fixture lacked actual paid stack entry");
        resolve(game);
        Card jace = game.getCardState(original);
        engine(jace.getId() == original.getId() && jace.isInZone(ZoneType.Battlefield)
                && jace.getCounters(CounterEnumType.LOYALTY) == 4 && !game.isGameOver(),
                "Jace did not enter with actual printed native loyalty4");
        row.put("jace_fixture", Map.of("method", "trusted legal native paid cast, not AI choice",
                "source_id", original.getId(), "paid_islands", 4, "native_loyalty", 4,
                "native_zone", jace.getZone().getZoneType().name()));
        return jace;
    }
    private Pose pose(int seat, String scene, Map<String, Object> row) {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("draw-replacement-seat" + i, null);
            lobby.setAiProfile("Default"); players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "Constructed draw replacement audit"));
        game.setAge(GameStage.Play);
        engine(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax() && !game.getAIFlatMonteCarloLite(), "Search mode changed");
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        fillLibrary(actor, 10); fillLibrary(enemy, 1); actor.setLife(20, null); enemy.setLife(20, null);
        Card jace = scene.equals("enemy-jace") ? enterJace(game, enemy, row) : null;
        if (scene.equals("enemy-maniac")) addCard("Laboratory Maniac", enemy);
        if (scene.equals("spirit-cap")) {
            addCard("Spirit of the Labyrinth", seat == 0 ? actor : enemy);
            row.put("spirit_controller", seat == 0 ? "actor" : "opponent");
        }
        boolean positive = scene.equals("positive-no-replacement");
        game.getPhaseHandler().devModeSet(positive ? PhaseType.MAIN2 : PhaseType.END_OF_TURN, positive ? actor : enemy);
        game.getPhaseHandler().onStackResolved(); game.getPhaseHandler().setPriority(actor);
        List<Card> lands = addCards("Island", 6, actor);
        Card source = addCardToZone("Inspiration", actor, ZoneType.Hand);
        game.getAction().checkStaticAbilities(); game.getAction().checkStateEffects(true);
        engine(game.getPhaseHandler().getPriorityPlayer() == actor
                && game.getPhaseHandler().is(positive ? PhaseType.MAIN2 : PhaseType.END_OF_TURN)
                && game.getPhaseHandler().isPlayerTurn(positive ? actor : enemy), "Wrong actual turn/phase/priority");
        engine(!game.isGameOver() && game.getStack().isEmpty() && actor.getManaPool().totalMana() == 0
                && actor.getNumDrawnThisTurn() == 0 && enemy.getNumDrawnThisTurn() == 0, "Invalid native starting pose");
        return new Pose(game, actor, enemy, source, lands, jace);
    }
    private Player payResolve(Pose p, SpellAbility chosen, Map<String, Object> row) {
        engine(chosen.getHostCard().getId() == p.source.getId() && p.source.isInZone(ZoneType.Hand), "Wrong original source");
        Player target = chosen.getTargets().getFirstTargetedPlayer();
        engine(chosen.getTargets().size() == 1 && (target == p.actor || target == p.enemy), "Invalid native selected target");
        row.put("actual_target", target == p.actor ? "self" : "opponent");
        engine(((PlayerControllerAi) p.actor.getController()).playWithRollback(chosen, null), "Native chosen payment failed");
        row.put("after_payment", state(p));
        engine(p.game.getStack().peekAbility() == chosen && chosen.getHostCard().isInZone(ZoneType.Stack), "Exact choice not on actual stack");
        engine(p.lands.stream().filter(Card::isTapped).count() == 4 && p.actor.getManaPool().totalMana() == 0
                && p.actor.getCardsIn(ZoneType.Hand).isEmpty(), "Wrong actual land payment/source hand exit");
        resolve(p.game); row.put("after_resolution", state(p));
        engine(p.lands.stream().filter(Card::isTapped).count() == 4, "Paid lands changed after resolution");
        if (!p.game.isGameOver()) engine(p.game.getCardState(p.source).isInZone(ZoneType.Graveyard), "Nonterminal source not in actual graveyard");
        return target;
    }
    private void check(int seat, String scene, boolean manual, Map<String, Object> row) {
        Pose p = pose(seat, scene, row); row.put("before", state(p));
        SpellAbility chosen;
        if (manual) {
            chosen = p.source.getSpellAbilities().get(0); chosen.setActivatingPlayer(p.actor);
            engine(chosen.canTarget(p.enemy), "Manual control enemy target illegal");
            chosen.getTargets().add(p.enemy); engine(chosen.canPlay(), "Manual control cast illegal");
        } else {
            // Actor's one and only fresh chooser; setup never evaluates this actor's play.
            List<SpellAbility> choices = ((PlayerControllerAi) p.actor.getController()).chooseSpellAbilityToPlay();
            row.put("choice_count", choices == null ? 0 : choices.size()); row.put("after_choice", state(p));
            chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
            policy(chosen != null, "Fresh Default declined declared positive");
            engine(choices.size() == 1, "Multiple selected actions");
        }
        row.put("enemy_canDraw_one_after_choice", p.enemy.canDraw());
        row.put("enemy_canDraw_two_after_choice", p.enemy.canDraw(2));
        if (scene.equals("spirit-cap")) engine(p.enemy.canDraw() && !p.enemy.canDraw(2), "Native Spirit draw cap inactive");
        // Preserve the actual selected targets even if wrong, then observe the real outcome.
        Player target = payResolve(p, chosen, row);
        if (manual && scene.equals("enemy-jace")) {
            engine(target == p.enemy && p.game.isGameOver() && p.enemy.hasWon() && p.actor.hasLost()
                    && p.enemy.getOutcome().altWinSourceName.equals("Jace, Wielder of Mysteries"), "Manual Jace did not produce native enemy replacement win");
            return;
        }
        if (manual && scene.equals("spirit-cap")) {
            engine(target == p.enemy && !p.game.isGameOver() && p.enemy.getCardsIn(ZoneType.Library).isEmpty()
                    && p.enemy.getCardsIn(ZoneType.Hand).size() == 1 && !p.enemy.hasLost(), "Manual Spirit did not prevent false decking");
            return;
        }
        if (scene.equals("positive-no-replacement")) {
            policy(target == p.enemy && p.game.isGameOver() && p.actor.hasWon() && p.enemy.hasLost()
                    && p.enemy.getOutcome().lossState == GameLossReason.Milled, "Ordinary native draw lethal failed");
        } else {
            policy(target == p.actor, "Native chooser targeted opponent despite replacement/cap");
            int draws = scene.equals("spirit-cap") ? 1 : 2;
            engine(!p.game.isGameOver() && !p.enemy.hasWon() && p.actor.getCardsIn(ZoneType.Library).size() == 10-draws
                    && p.actor.getCardsIn(ZoneType.Hand).size() == draws && p.enemy.getCardsIn(ZoneType.Library).size() == 1
                    && p.enemy.getCardsIn(ZoneType.Hand).isEmpty(), "Wrong safe self draw destinations/outcome");
        }
    }
    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]); MyRandom.setRandom(new Random(2026110673L));
        NativeTargetedDrawReplacementAudit test = new NativeTargetedDrawReplacementAudit(); test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        List<Map<String, Object>> rows = new ArrayList<>(); int failures = 0, errors = 0;
        outer: for (boolean manual : new boolean[]{false, true}) {
            List<String> scenes = manual ? List.of("enemy-jace", "spirit-cap")
                    : List.of("enemy-jace", "spirit-cap", "positive-no-replacement", "enemy-maniac");
            for (int seat : new int[]{0, 1}) for (String scene : scenes) {
                Map<String, Object> row = new LinkedHashMap<>(); rows.add(row);
                row.put("cohort", manual ? "trusted-opponent-execution-not-ai" : "ai-eight");
                row.put("seat", seat); row.put("scene", scene);
                try { test.check(seat, scene, manual, row); row.put("passed", true); }
                catch (Throwable cause) {
                    row.put("passed", false); row.put("failure", cause.toString()); cause.printStackTrace(System.err);
                    if (cause instanceof AssertionError) failures++; else errors++;
                }
                Files.writeString(out.resolve("ledger.private.json"), new Gson().toJson(rows)+"\n");
                if (errors > 0) break outer;
            }
        }
        Files.writeString(out.resolve("summary.private.json"), new Gson().toJson(Map.of("cases", rows,
                "passed", rows.size()-failures-errors, "failures", failures, "errors", errors, "natural_games", 0))+"\n");
        System.exit(errors > 0 ? 2 : failures > 0 ? 1 : 0);
    }
}
