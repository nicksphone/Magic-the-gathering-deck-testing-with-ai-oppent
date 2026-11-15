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
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeGooseCatTwoStep2 extends AITest {
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
    private static Card actualCardRef(Game game, Card previous) {
        Card current = game.getCardState(previous, null);
        need(current != null && current.getId() == previous.getId(), "Actual native card reference after movement");
        return current;
    }
    private static Map<String, Object> state(Game game, Player actor, Player enemy) throws Exception {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("actor_life", actor.getLife()); value.put("enemy_life", enemy.getLife());
        value.put("native_game_over", game.isGameOver()); value.put("native_stack_empty", game.getStack().isEmpty());
        value.put("Food", food(actor).stream().map(c -> Map.of("id", c.getId(), "is_token", c.isToken(), "tapped", c.isTapped())).toList());
        value.put("Forests", actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest"))
                .map(c -> Map.of("id", c.getId(), "tapped", c.isTapped())).toList());
        value.put("actor_view", new ActorBoundary(actor).snapshot(game.getView())); value.put("rng", rng());
        return value;
    }
    private void check(int seat, Map<String, Object> row) throws Exception {
        // The single run seed is installed in main, before model and both fixtures.
        row.put("rng_before_fixture_construction", rng());
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("controlled-goose-cat-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Gilded Goose", 1); deck.getMain().add("Cauldron Familiar", 1);
                deck.getMain().add("Witch's Oven", 1); deck.getMain().add("Forest", 57);
            } else deck.getMain().add("Mountain", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("goose-cat-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-PROTOCOL-GOOSE-CAT-TWO-STEP2"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int count = 0; count < entry.getValue(); count++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && player.getAllCards().size() == 60,
                    "Complete native registered60 originals");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor); game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>(); row.put("native_events_including_setup", events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> value = new LinkedHashMap<>();
                value.put("index", events.size() + 1); value.put("event", event.getClass().getSimpleName());
                value.put("turn", game.getPhaseHandler().getTurn());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    value.put("source", cast.si().getSourceCard().getName()); value.put("source_id", cast.si().getSourceCard().getId());
                    value.put("is_spell", cast.sa().isSpell());
                }
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved) value.put("message", event.toString());
                events.add(value);
            }
        });
        row.put("registered_main_totals", List.of(60, 60)); row.put("setup_before_any_pose", state(game, actor, enemy));
        Card oven = pose(actor, "Witch's Oven"), cat = pose(actor, "Cauldron Familiar");
        List<Card> spentForests = List.of(pose(actor, "Forest"), pose(actor, "Forest"), pose(actor, "Forest"), pose(actor, "Forest"));
        resolve(game);
        row.put("setup_Cat_entry_resolved_before_life_assignment", state(game, actor, enemy));
        need(actor.getCreaturesInPlay().size() == 1 && food(actor).isEmpty(), "Cat is the only Oven victim, no Food shortcut");
        priority(game, actor, enemy);
        boolean ovenPaid = ComputerUtil.playStack(activation(actualCardRef(game, oven), actor, ApiType.Token), actor, game);
        row.put("setup_manual_Oven_paid", ovenPaid);
        need(ovenPaid && actualCardRef(game, oven).isTapped() && actualCardRef(game, cat).isInZone(ZoneType.Graveyard),
                "Setup Oven genuinely taps and sacrifices original Cat before Goose is posed");
        resolve(game);
        need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Native Oven produced setup Food");
        row.put("setup_Oven_resolved_before_life_assignment", state(game, actor, enemy));
        Card goose = pose(actor, "Gilded Goose"); resolve(game);
        need(food(actor).size() == 2 && food(actor).stream().allMatch(Card::isToken)
                && actualCardRef(game, goose).isSick() && !actualCardRef(game, goose).isTapped(),
                "Native Goose ETB adds a second Food; newly entered Goose cannot be a setup mana source");
        row.put("setup_Goose_ETB_resolved_before_life_assignment", state(game, actor, enemy));
        List<Card> setupFoods = new ArrayList<>(food(actor));
        row.put("setup_native_Food_ids", setupFoods.stream().map(Card::getId).toList());
        for (int index = 0; index < setupFoods.size(); index++) {
            priority(game, actor, enemy);
            int lifeBefore = actor.getLife();
            boolean paid = ComputerUtil.playStack(activation(actualCardRef(game, setupFoods.get(index)), actor, ApiType.GainLife), actor, game);
            row.put("setup_manual_Food_" + index + "_paid", paid);
            need(paid, "Actual Food gain-life activation pays two mana, tap and sacrifice"); resolve(game);
            need(actor.getLife() == lifeBefore + 3 && food(actor).size() == 1 - index,
                    "Native Food resolves to three life and consumes its real token");
            need(spentForests.stream().filter(c -> actualCardRef(game, c).isTapped()).count() == 2L * (index + 1),
                    "Each Food activation consumes two actual Forest mana sources");
            row.put("setup_Food_" + index + "_resolved_before_life_assignment", state(game, actor, enemy));
        }
        List<Card> freshForests = List.of(pose(actor, "Forest"), pose(actor, "Forest"));
        row.put("setup_paid_cleanup_complete_before_fixture_age_or_life_assignment", state(game, actor, enemy));
        row.put("trusted_Goose_standing_age_before", actualCardRef(game, goose).isSick());
        // Trusted frontier age, not a simulated elapsed turn or a printed Haste grant.
        actualCardRef(game, goose).setSickness(false);
        row.put("trusted_Goose_standing_age_after", actualCardRef(game, goose).isSick());
        row.put("setup_all_outcomes_before_explicit_fixture_life_assignment", state(game, actor, enemy));
        row.put("fixture_life_assignment", Map.of("actor", 2, "enemy", 1));
        actor.setLife(2, null); enemy.setLife(1, null); game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && actor.getLife() == 2 && enemy.getLife() == 1
                && actualCardRef(game, cat).isInZone(ZoneType.Graveyard) && actualCardRef(game, goose).isInZone(ZoneType.Battlefield)
                && !actualCardRef(game, goose).isSick() && !actualCardRef(game, goose).isTapped()
                && actualCardRef(game, oven).isTapped() && food(actor).isEmpty()
                && spentForests.stream().allMatch(c -> actualCardRef(game, c).isTapped())
                && freshForests.stream().noneMatch(c -> actualCardRef(game, c).isTapped())
                && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Settled Goose/CatGY/no-Food/two-fresh-Forest frontier");
        need(actor.getAllCards().stream().noneMatch(c -> c.getName().equals("Blood Artist"))
                && actor.getCreaturesInPlay().size() == 1, "No Artist or other creature payoff");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default, MC off");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView())); row.put("rng_before_choice", rng());
        // No helper, forecast or affordability diagnostic precedes this ordinary callback.
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("first_choice", ability(chosen)); row.put("ordinary_Default_initial_callbacks", 1);
        row.put("rng_after_choice", rng()); row.put("after_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        boolean firstSelected = chosen != null && chosen.getHostCard().getId() == goose.getId() && chosen.getApi() == ApiType.Token;
        List<String> failed = new ArrayList<>();
        if (!firstSelected) failed.add(chosen == null ? "FIRST_DEFAULT_PASS_MISSES_GOOSE_CAT_TWO_ACTION_WIN"
                : "FIRST_DEFAULT_OTHER_ACTION_MISSES_GOOSE_CAT_TWO_ACTION_WIN");
        row.put("first_AI_selected_Goose_Token", firstSelected);
        row.put("manual_full_two_action_control_not_AI_success", !firstSelected);
        boolean goosePaid = ComputerUtil.playStack(firstSelected ? chosen : activation(actualCardRef(game, goose), actor, ApiType.Token), actor, game);
        row.put("Goose_actual_paid", goosePaid);
        need(goosePaid && actualCardRef(game, goose).isTapped()
                && freshForests.stream().allMatch(c -> actualCardRef(game, c).isTapped())
                && actualCardRef(game, cat).isInZone(ZoneType.Graveyard), "Goose really pays 1G and tap, Cat remains in graveyard");
        resolve(game);
        need(!game.isGameOver() && enemy.getLife() == 1 && game.getStack().isEmpty()
                && food(actor).size() == 1 && food(actor).get(0).isToken(), "Goose activation creates one Food, not an immediate win");
        need(setupFoods.stream().noneMatch(c -> c.getId() == food(actor).get(0).getId()), "New Goose Food is not a recycled setup token");
        row.put("real_Goose_activation_Food_id", food(actor).get(0).getId()); row.put("after_Goose_resolution", state(game, actor, enemy));
        priority(game, actor, enemy);
        SpellAbility second = null; boolean secondSelected = false;
        if (firstSelected) {
            row.put("rng_before_second_choice", rng());
            List<SpellAbility> next = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
            second = next == null || next.isEmpty() ? null : next.get(0);
            row.put("second_choice", ability(second)); row.put("ordinary_Default_subsequent_callbacks", 1);
            row.put("rng_after_second_choice", rng());
            secondSelected = second != null && second.getHostCard().getId() == cat.getId() && second.getApi() == ApiType.ChangeZone;
            if (!secondSelected) failed.add("SECOND_DEFAULT_MISSES_NATIVE_CAT_RETURN_WIN");
        }
        row.putIfAbsent("ordinary_Default_subsequent_callbacks", 0);
        row.put("second_AI_selected_Cat", secondSelected); row.put("second_manual_control_not_AI_success", !secondSelected);
        boolean catPaid = ComputerUtil.playStack(secondSelected ? second : activation(actualCardRef(game, cat), actor, ApiType.ChangeZone), actor, game);
        row.put("Cat_actual_paid", catPaid); need(catPaid, "Cat pays genuine Goose-generated Food sacrifice"); resolve(game);
        boolean won = game.isGameOver() && actor.hasWon() && enemy.hasLost(); row.put("actual_native_win", won);
        need(won && food(actor).isEmpty() && actualCardRef(game, cat).isInZone(ZoneType.Battlefield),
                "Actual native Cat return, Food consumption and entry-drain win");
        row.put("AI_two_selected_actions_actual_win", firstSelected && secondSelected && won);
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("native_game_over", game.isGameOver()); row.put("rng_after_native_outcome", rng());
        row.put("failures", failed); row.put("status", failed.isEmpty() ? "PASS" : "POLICY_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private report directory, explicit parent GO required externally");
        Path out = Path.of(args[0]); need(Files.isDirectory(out), "Runner-created fresh private output directory");
        MyRandom.setRandom(new Random(2026110701L)); String rngBeforeModel = rng();
        NativeGooseCatTwoStep2 audit = new NativeGooseCatTwoStep2(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, manualWins = 0, selectedWins = 0, initialCallbacks = 0, subsequentCallbacks = 0;
        String scene = "GooseFoodThenCatReturnWin";
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", 2026110701L,
                    "label", "INTERNAL-PROTOCOL", "seed_scope", "once before model and both ordered fixtures; never reset"));
            try {
                audit.check(seat, row);
                if (row.get("status").equals("PASS")) pass++; else red++;
                if (Boolean.TRUE.equals(row.get("manual_full_two_action_control_not_AI_success"))
                        && Boolean.TRUE.equals(row.get("actual_native_win"))) manualWins++;
                if (Boolean.TRUE.equals(row.get("AI_two_selected_actions_actual_win"))) selectedWins++;
            } catch (Throwable error) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
            }
            initialCallbacks += ((Number) row.getOrDefault("ordinary_Default_initial_callbacks", 0)).intValue();
            subsequentCallbacks += ((Number) row.getOrDefault("ordinary_Default_subsequent_callbacks", 0)).intValue();
            Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n",
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "INTERNAL-PROTOCOL-GOOSE-CAT-TWO-STEP2"); summary.put("total", 2);
        summary.put("pass", pass); summary.put("policy_red", red); summary.put("harness_errors", errors);
        summary.put("ordinary_Default_initial_callbacks", initialCallbacks); summary.put("ordinary_Default_subsequent_callbacks", subsequentCallbacks);
        summary.put("manual_full_two_action_native_wins", manualWins); summary.put("AI_two_selected_action_native_wins", selectedWins);
        summary.put("seed", 2026110701L); summary.put("seed_installations", 1); summary.put("rng_after_seed_before_model", rngBeforeModel);
        summary.put("manual_controls_are_AI_successes", false); summary.put("natural_games", 0); summary.put("expert_games", 0);
        summary.put("RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
