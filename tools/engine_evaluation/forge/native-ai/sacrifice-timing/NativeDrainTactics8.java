// SPDX-License-Identifier: GPL-3.0-or-later
// Constructed native fixtures using the Forge Team/Card-Forge engine and full programs.
// These are not natural games or synthetic replacements for printed card abilities.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.AbilityKey;
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
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public final class NativeDrainTactics8 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static void need(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true);
        return card;
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) { stream.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Object> ability(SpellAbility sa) {
        if (sa == null) return Map.of("choice", "PASS");
        return Map.of("source", sa.getHostCard().getName(), "source_id", sa.getHostCard().getId(),
                "ability_id", sa.getId(), "api", String.valueOf(sa.getApi()), "is_spell", sa.isSpell());
    }
    private static Card pose(Player player, String name) {
        Card original = player.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        return player.getGame().getAction().moveToPlay(original, player, null, AbilityKey.newMap());
    }
    private static void priority(Game game, Player actor, Player enemy) {
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
    }
    private static void resolve(Game game) {
        for (int count = 0; count < 20; count++) {
            if (game.isGameOver()) return;
            game.getAction().checkStateEffects(true);
            if (game.isGameOver()) return;
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        need(game.getStack().isEmpty() || game.isGameOver(), "Bounded actual native stack resolution");
    }
    private static List<Card> food(Player player) {
        return player.getCardsIn(ZoneType.Battlefield).stream()
                .filter(c -> c.getType().hasSubtype("Food") && c.getController().equals(player)).toList();
    }
    private static SpellAbility activation(Card source, Player player, ApiType api) {
        SpellAbility sa = source.getSpellAbilities().stream().filter(s -> s.isActivatedAbility() && s.getApi() == api).findFirst().orElseThrow();
        sa.setActivatingPlayer(player); return sa;
    }
    private void check(long seed, int seat, String scene, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(seed)); // Once before construction; no reset after setup or decision.
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("controlled-drain-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Cauldron Familiar", 1); deck.getMain().add("Witch's Oven", 1);
                deck.getMain().add("Blood Artist", 1); deck.getMain().add("Swamp", 57);
            } else {
                deck.getMain().add("Icy Manipulator", 1); deck.getMain().add("Mountain", 59);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("drain-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "CONTROLLED-DRAIN-TACTICS8"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int count = 0; count < entry.getValue(); count++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && player.getAllCards().size() == 60,
                    "Complete native registered60 originals before token creation");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor);
        game.getPhaseHandler().onStackResolved();
        Card oven = pose(actor, "Witch's Oven"), cat = pose(actor, "Cauldron Familiar");
        final int catId = cat.getId();
        List<Card> mana = List.of(pose(actor, "Swamp"), pose(actor, "Swamp"));
        boolean ovenWin = scene.equals("OvenDeathWin"), spent = scene.equals("FoodAlreadySpent"), tappedFood = scene.equals("TappedFoodReturnWin");
        if (ovenWin) pose(actor, "Blood Artist");
        resolve(game);
        need(!game.isGameOver() && game.getStack().isEmpty() && cat.isInZone(ZoneType.Battlefield)
                && !oven.isTapped() && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Settled trusted battlefield setup, no hidden playable hand");
        if (!ovenWin) {
            priority(game, actor, enemy);
            need(ComputerUtil.playStack(activation(oven, actor, ApiType.Token), actor, game), "Genuine Oven activation pays native tap/sacrifice cost");
            need(oven.isTapped() && actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == catId),
                    "Actual Oven sacrifice paid with the only creature");
            resolve(game);
            need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Native Oven resolution created exactly one real Food token");
            Card originalFood = food(actor).get(0);
            row.put("setup_generated_food_id", originalFood.getId());
            row.put("setup_generated_food_program", "c_a_food_sac");
            if (spent) {
                priority(game, actor, enemy);
                need(ComputerUtil.playStack(activation(originalFood, actor, ApiType.GainLife), actor, game), "Native Food ability actually pays two mana/tap/sacrifice");
                resolve(game);
                need(food(actor).isEmpty() && mana.stream().allMatch(Card::isTapped), "Food really spent, not removed by a fixture shortcut");
            } else if (tappedFood) {
                Card icy = pose(enemy, "Icy Manipulator"), mountain = pose(enemy, "Mountain");
                priority(game, enemy, actor);
                SpellAbility tap = activation(icy, enemy, ApiType.Tap); tap.getTargets().add(originalFood);
                need(ComputerUtil.playStack(tap, enemy, game), "Actual opponent Icy activation against generated Food");
                resolve(game);
                need(icy.isTapped() && mountain.isTapped() && originalFood.isTapped() && food(actor).size() == 1,
                        "Genuine paid Icy effect tapped Food without sacrificing it");
            }
        }
        actor.setLife(2, null); enemy.setLife(1, null);
        game.getAction().checkStateEffects(true);
        priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && actor.getLife() == 2 && enemy.getLife() == 1,
                "Nonterminal declared tactical frontier before first ordinary response");
        need(actor.getController().getClass() == PlayerControllerAi.class && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(),
                "Unmodified Default heuristic controller");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_before_choice", rng());
        row.put("food_before_choice", food(actor).size()); row.put("cat_in_graveyard_before",
                actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == catId));
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("ordinary_Default_callbacks", 1); row.put("first_choice", ability(chosen));
        row.put("rng_after_choice", rng()); row.put("after_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        List<String> failed = new ArrayList<>();
        if (spent) {
            if (chosen != null && chosen.getHostCard().getId() == catId) failed.add("Proposes Cat return after its only Food was genuinely spent");
            row.put("selected_action_executed", false);
        } else {
            Card expected = ovenWin ? oven : actor.getCardsIn(ZoneType.Graveyard).stream()
                    .filter(c -> c.getId() == catId).findFirst().orElseThrow();
            ApiType api = ovenWin ? ApiType.Token : ApiType.ChangeZone;
            boolean selected = chosen != null && chosen.getHostCard().getId() == expected.getId() && chosen.getApi() == api;
            if (!selected) failed.add("Missed the available immediate native drain win");
            SpellAbility actual = selected ? chosen : activation(expected, actor, api);
            boolean paid = ComputerUtil.playStack(actual, actor, game);
            row.put("selected_action_executed", selected); row.put("trusted_post_decline_control_not_AI_success", !selected);
            row.put("actual_expected_action_paid", paid);
            need(paid, "Expected winning line must actually pay; not an inferred playable card");
            resolve(game);
            boolean won = game.isGameOver() && actor.hasWon() && enemy.hasLost();
            row.put("actual_native_win", won);
            if (!won) failed.add("Actual chosen/control drain sequence did not win against one life");
            need(selected || won, "A post-decline control must prove the supposed immediate win");
        }
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("native_game_over", game.isGameOver()); row.put("food_after", food(actor).size());
        row.put("failures", failed); row.put("status", failed.isEmpty() ? "PASS" : "POLICY_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private report directory argument");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110613L));
        NativeDrainTactics8 audit = new NativeDrainTactics8(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, index = 0;
        for (String scene : List.of("FoodReturnWin", "OvenDeathWin", "FoodAlreadySpent", "TappedFoodReturnWin")) {
            long seed = 2026110613L + index++;
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", seed));
                try { audit.check(seed, seat, scene, row); if (row.get("status").equals("PASS")) pass++; else red++; }
                catch (Throwable error) { errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName()); row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err); }
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n");
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
            }
        }
        Map<String, Object> summary = Map.of("label", "CONTROLLED-NATIVE-DRAIN-TACTICS8", "total", 8, "pass", pass,
                "policy_red", red, "harness_errors", errors, "natural_games", 0, "ordinary_Default_initial_callbacks", 8,
                "forced_AI_actions_or_winners", false, "RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
