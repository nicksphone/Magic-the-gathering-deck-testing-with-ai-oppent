// SPDX-License-Identifier: GPL-3.0-or-later
// New supplement only; original eight-case source/classes remain unchanged.
// Full canonical Forge Team/Card-Forge cards; see NOTICE.md.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.AiProfileUtil;
import forge.ai.AiProps;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
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
import java.util.TreeSet;

/** Two positions; each has one game and up to three fresh native choices. */
public final class NativeSorceryChainControls extends AITest {
    private static final long SEED = 2026110617L;

    private static List<Map<String, Object>> cards(Iterable<Card> cards) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Card card : cards) rows.add(Map.of("id", card.getId(), "name", card.getName(), "tapped", card.isTapped()));
        return rows;
    }

    private static Map<String, Object> position(Game game, Player actor, Player enemy) {
        return Map.of("phase", String.valueOf(game.getPhaseHandler().getPhase()),
                "actor_life", actor.getLife(), "enemy_life", enemy.getLife(),
                "hand", cards(actor.getCardsIn(ZoneType.Hand)),
                "graveyard", cards(actor.getCardsIn(ZoneType.Graveyard)),
                "battlefield", cards(actor.getCardsIn(ZoneType.Battlefield)),
                "mana_pool", actor.getManaPool().totalMana(), "stack_size", game.getStack().size(),
                "game_terminal", game.isGameOver());
    }

    private static List<Map<String, Object>> abilityState(Player actor) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Card card : actor.getCardsIn(ZoneType.Hand)) {
            for (SpellAbility ability : card.getSpellAbilities()) {
                List<Integer> targetPlayers = new ArrayList<>();
                for (var target : ability.getTargets()) if (target instanceof Player player) targetPlayers.add(player.getId());
                rows.add(Map.of("source", card.getId(), "api", String.valueOf(ability.getApi()),
                        "is_spell", ability.isSpell(), "damage_param", ability.getParamOrDefault("NumDmg", ""),
                        "target_players", targetPlayers));
            }
        }
        return rows;
    }

    private void check(int seat, Map<String, Object> result) {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("canonical-seat" + i, null) {
                @Override public Player createIngamePlayer(Game game, int id) {
                    Player player = new Player(getName(), game, id);
                    player.setFirstController(new PublicNameController(game, player, this, Map.of()));
                    return player;
                }
            };
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "Canonical three sorcery chain"));
        game.setAge(GameStage.Play);
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        actor.setLife(20, null);
        enemy.setLife(20, null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor);
        game.getPhaseHandler().onStackResolved();
        fillLibrary(actor, 8);
        fillLibrary(enemy, 8);
        List<Card> lands = new ArrayList<>(), originalHand = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            lands.add(addCard("Mountain", actor));
            originalHand.add(addCardToZone("Lava Spike", actor, ZoneType.Hand));
        }
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        require(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Unexpected search mode");
        require(actor.getCreaturesInPlay().isEmpty() && enemy.getCardsIn(ZoneType.Battlefield).isEmpty()
                && lands.stream().noneMatch(Card::isTapped) && actor.getManaPool().totalMana() == 0,
                "Starting position differs from the declaration");
        result.put("native_game_id", game.getId());
        result.put("original_source_ids", originalHand.stream().map(Card::getId).toList());
        List<Map<String, Object>> steps = new ArrayList<>();
        result.put("steps", steps);
        TreeSet<Integer> played = new TreeSet<>();
        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        int[] expectedLife = {17, 14, 11};
        for (int step = 0; step < 3; step++) {
            require(game.getPhaseHandler().is(PhaseType.MAIN2) && game.getPhaseHandler().isPlayerTurn(actor)
                    && game.getStack().isEmpty() && !game.isGameOver(), "Native phase/game changed before fresh choice");
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("step", step + 1);
            row.put("before", position(game, actor, enemy));
            steps.add(row);
            // One fresh real decision after the previous native resolution; no diagnostic evaluation.
            long started = System.nanoTime();
            List<SpellAbility> selected = controller.chooseSpellAbilityToPlay();
            row.put("choice_elapsed_ms", (System.nanoTime() - started) / 1_000_000.0);
            row.put("native_decision_timeout_seconds", game.getAITimeout());
            SpellAbility chosen = selected == null || selected.isEmpty() ? null : selected.get(0);
            row.put("chosen", selected == null ? List.of() : selected.stream().map(sa -> Map.of(
                    "source", sa.getHostCard().getId(), "name", sa.getHostCard().getName(),
                    "api", String.valueOf(sa.getApi()))).toList());
            row.put("after_choice", position(game, actor, enemy));
            row.put("native_hand_abilities_after_choice", abilityState(actor));
            result.put("profile", ((LobbyPlayerAi) actor.getLobbyPlayer()).getAiProfile());
            result.put("native_chain_property", AiProfileUtil.getIntProperty(actor, AiProps.CHANCE_TO_CHAIN_TWO_DAMAGE_SPELLS));
            require("Default".equals(result.get("profile")) && result.get("native_chain_property").equals(90),
                    "Native Default profile did not load");
            if (chosen == null) {
                result.put("declined_at_step", step + 1);
                result.put("decline_snapshot", new ActorBoundary(actor).snapshot(game.getView()));
                throw new AssertionError("Native Default declined fresh chain decision " + (step + 1));
            }
            int id = chosen.getHostCard().getId();
            require(chosen.isSpell() && chosen.getApi() == ApiType.DealDamage
                    && chosen.getHostCard().isInZone(ZoneType.Hand) && chosen.getTargets().contains(enemy)
                    && originalHand.stream().anyMatch(card -> card.getId() == id) && !played.contains(id),
                    "Fresh choice is not a distinct original enemy-targeting Lava Spike");
            require(controller.playWithRollback(chosen, null), "Native payment rejected its chosen Lava Spike");
            require(chosen.getHostCard().isInZone(ZoneType.Stack) && game.getStack().size() == 1,
                    "Chosen Lava Spike did not enter the actual stack");
            require(lands.stream().filter(Card::isTapped).count() == step + 1
                    && actor.getManaPool().totalMana() == 0, "Native cast did not spend exactly one more red source");
            row.put("after_payment", position(game, actor, enemy));
            game.getStack().resolveStack();
            game.getAction().checkStateEffects(true);
            played.add(id);
            row.put("after_resolution", position(game, actor, enemy));
            require(enemy.getLife() == expectedLife[step] && actor.getLife() == 20
                    && actor.getCardsIn(ZoneType.Hand).size() == 2 - step
                    && actor.getCardsIn(ZoneType.Graveyard).size() == step + 1
                    && game.getStack().isEmpty() && !game.isGameOver(), "Native resolution/lifecycle differs from the declaration");
        }
        TreeSet<Integer> graveyard = new TreeSet<>();
        for (Card card : actor.getCardsIn(ZoneType.Graveyard)) graveyard.add(card.getId());
        require(graveyard.equals(new TreeSet<>(originalHand.stream().map(Card::getId).toList()))
                && played.equals(graveyard) && actor.getCardsIn(ZoneType.Hand).isEmpty()
                && lands.stream().allMatch(Card::isTapped) && actor.getManaPool().totalMana() == 0
                && enemy.getLife() == 11 && !game.isGameOver(), "Final three-source/three-card chain assertion failed");
        result.put("passed", true);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        MyRandom.setRandom(new Random(SEED));
        NativeSorceryChainControls test = new NativeSorceryChainControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        List<Map<String, Object>> cases = new ArrayList<>();
        int failures = 0, errors = 0;
        for (int seat : new int[]{0, 1}) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("seat", seat);
            cases.add(result);
            try {
                test.check(seat, result);
            } catch (AssertionError failure) {
                failures++;
                result.put("failure", failure.getMessage());
                System.err.println("RED seat=" + seat + ": " + failure.getMessage());
            } catch (Throwable failure) {
                errors++;
                result.put("error", failure.getClass().getName());
                failure.printStackTrace();
            }
        }
        String json = new Gson().toJson(Map.of("label", "CANONICAL-DEFAULT-THREE-SORCERY-CHAIN-SUPPLEMENT",
                "seed", SEED, "passed", 2 - failures - errors, "failures", failures, "errors", errors,
                "natural_games", 0, "constructed_games", 2, "production_changes", false, "cases", cases));
        Files.writeString(Path.of(args[0], "summary.private.json"), json + "\n");
        System.out.println(json);
        System.exit(failures == 0 && errors == 0 ? 0 : 1);
    }
}
