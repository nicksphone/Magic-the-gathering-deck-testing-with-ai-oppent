// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only controlled positions using Forge Team/Card-Forge full canonical cards.
// Upstream 61e9442c433711a82258daca3236f936a1d6f70e; see NOTICE.md.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
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

/** Eight declared scenes, one native choice per scene, no policy/cost diagnostic calls. */
public final class NativeSorceryPressureControls extends AITest {
    private static final long SEED = 2026110617L;

    private void check(JsonObject spec, Map<String, Object> result) {
        int seat = spec.get("seat").getAsInt();
        int enemyLife = spec.get("enemy_life").getAsInt();
        boolean funded = spec.get("funded").getAsBoolean();
        boolean expectCast = spec.get("expect_cast").getAsBoolean();
        PhaseType phase = PhaseType.valueOf(spec.get("phase").getAsString());
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
        Game game = new Game(registered, rules, new Match(rules, registered, "Canonical sorcery pressure"));
        game.setAge(GameStage.Play);
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        actor.setLife(20, null);
        enemy.setLife(enemyLife, null);
        game.getPhaseHandler().devModeSet(phase, actor);
        game.getPhaseHandler().onStackResolved();
        fillLibrary(actor, 8);
        fillLibrary(enemy, 8);
        List<Card> lands = new ArrayList<>(), hand = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            Card land = addCard("Mountain", actor);
            land.setTapped(!funded);
            lands.add(land);
            hand.add(addCardToZone("Lava Spike", actor, ZoneType.Hand));
        }
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        require(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Fixture unexpectedly enabled search");
        require(game.getStack().isEmpty() && actor.getCreaturesInPlay().isEmpty()
                && enemy.getCardsIn(ZoneType.Battlefield).isEmpty(), "Fixture is not the declared empty board");
        require(actor.getManaPool().totalMana() == 0 && actor.getCardsIn(ZoneType.Hand).size() == 3,
                "Fixture has extra mana/cards");

        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        // The real Default choice is the first policy/cost query. Never retry it for diagnostics.
        List<SpellAbility> selected = controller.chooseSpellAbilityToPlay();
        SpellAbility chosen = selected == null || selected.isEmpty() ? null : selected.get(0);

        result.put("actor_id", actor.getId());
        result.put("enemy_id", enemy.getId());
        result.put("first_choice", selected == null ? List.of() : selected.stream().map(sa -> Map.of(
                "source_id", sa.getHostCard().getId(), "source_name", sa.getHostCard().getName(),
                "api", String.valueOf(sa.getApi()), "description", sa.getDescription())).toList());
        result.put("profile", ((LobbyPlayerAi) actor.getLobbyPlayer()).getAiProfile());
        result.put("native_chain_property", AiProfileUtil.getIntProperty(actor, AiProps.CHANCE_TO_CHAIN_TWO_DAMAGE_SPELLS));
        result.put("actor_snapshot_after_first_choice", new ActorBoundary(actor).snapshot(game.getView()));
        result.put("mana_pool_after_choice", actor.getManaPool().totalMana());
        result.put("tapped_sources_after_choice", lands.stream().filter(Card::isTapped).count());
        result.put("choice_calls", 1);
        require("Default".equals(result.get("profile")) && result.get("native_chain_property").equals(90),
                "The native Default profile was not loaded; no invented fallback profile allowed");

        if (!expectCast) {
            require(chosen == null, "Native choice bypassed declared cost/sorcery timing control");
            require(hand.stream().allMatch(card -> card.isInZone(ZoneType.Hand)) && game.getStack().isEmpty()
                    && lands.stream().filter(Card::isTapped).count() == (funded ? 0 : 3)
                    && actor.getManaPool().totalMana() == 0 && enemy.getLife() == enemyLife,
                    "Declined choice paid or mutated the declared position");
            result.put("passed", true);
            return;
        }
        require(chosen != null, "Native Default passed the funded " + spec.get("scene").getAsString()
                + " scene before any policy/cost diagnostics");
        require(chosen.isSpell() && chosen.getApi() == ApiType.DealDamage
                && hand.stream().anyMatch(card -> card.getId() == chosen.getHostCard().getId())
                && chosen.getTargets().contains(enemy), "Choice was not a recognized canonical enemy-targeting Lava Spike");
        require(controller.playWithRollback(chosen, null), "Native cast/payment rejected its selected Lava Spike");
        require(chosen.getHostCard().isInZone(ZoneType.Stack) && !game.getStack().isEmpty(),
                "Selected Lava Spike never entered native stack");
        long tapped = lands.stream().filter(Card::isTapped).count();
        result.put("paid_lands", tapped);
        require(tapped == 1 && actor.getManaPool().totalMana() == 0, "Native R cost was not actually paid once");
        game.getStack().resolveStack();
        game.getAction().checkStateEffects(true);
        result.put("enemy_life_after_resolution", enemy.getLife());
        result.put("native_game_over", game.isGameOver());
        result.put("native_actor_won", actor.hasWon());
        require(actor.getLife() == 20 && enemy.getLife() == enemyLife - 3, "Native damage did not resolve as declared");
        require(actor.getCardsIn(ZoneType.Hand).size() == 2
                && actor.getCardsIn(ZoneType.Graveyard).size() == 1 && game.getStack().isEmpty(),
                "Native card/stack lifecycle did not finish");
        if (enemyLife == 3) {
            require(game.isGameOver() && actor.hasWon() && enemy.hasLost(), "Native lethal did not award its own outcome");
        } else {
            require(!game.isGameOver(), "Nonlethal pressure unexpectedly ended the game");
        }
        result.put("passed", true);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        JsonObject plan = JsonParser.parseString(Files.readString(output.resolve("DECLARATION.json"))).getAsJsonObject();
        require(plan.get("seed").getAsLong() == SEED && plan.getAsJsonArray("cases").size() == 8,
                "Only the predeclared eight-case seed/family is supported");
        MyRandom.setRandom(new Random(SEED));
        NativeSorceryPressureControls test = new NativeSorceryPressureControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        List<Map<String, Object>> results = new ArrayList<>();
        int failures = 0, errors = 0;
        for (var item : plan.getAsJsonArray("cases")) {
            JsonObject spec = item.getAsJsonObject();
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("declaration", new Gson().fromJson(spec, Map.class));
            results.add(result);
            try {
                test.check(spec, result);
            } catch (AssertionError failure) {
                failures++;
                result.put("failure", failure.getMessage());
                System.err.println("RED seat=" + spec.get("seat") + " scene=" + spec.get("scene") + ": " + failure.getMessage());
            } catch (Throwable failure) {
                errors++;
                result.put("error", failure.getClass().getName());
                failure.printStackTrace();
            }
        }
        String json = new Gson().toJson(Map.of("label", plan.get("label").getAsString(), "seed", SEED,
                "passed", 8 - failures - errors, "failures", failures, "errors", errors,
                "natural_games", 0, "production_changes", false, "cases", results));
        Files.writeString(output.resolve("summary.private.json"), json + "\n");
        System.out.println(json);
        System.exit(failures == 0 && errors == 0 ? 0 : 1);
    }
}
