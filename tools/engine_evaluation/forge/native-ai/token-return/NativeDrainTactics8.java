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
        // The single run seed is installed in main, before model/fixture construction.
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("controlled-two-step-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Cauldron Familiar", 1); deck.getMain().add("Witch's Oven", 1);
                deck.getMain().add("Swamp", 58);
            } else deck.getMain().add("Mountain", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("two-step-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "CONTROLLED-OVEN-CAT-TWO-STEP2"));
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
        pose(actor, "Swamp"); pose(actor, "Swamp");
        resolve(game);
        actor.setLife(2, null); enemy.setLife(1, null);
        game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && actor.getLife() == 2 && enemy.getLife() == 1
                && cat.isInZone(ZoneType.Battlefield) && !oven.isTapped() && food(actor).isEmpty()
                && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Settled declared main1 two-step frontier");
        need(actor.getAllCards().stream().noneMatch(c -> c.getName().equals("Blood Artist"))
                && actor.getCreaturesInPlay().size() == 1, "No death-drain payoff; Cat is the only sacrifice creature");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default, MC off");
        List<Map<String, Object>> events = new ArrayList<>();
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> value = new LinkedHashMap<>();
                value.put("index", events.size() + 1); value.put("event", event.getClass().getSimpleName());
                value.put("turn", game.getPhaseHandler().getTurn());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    value.put("source", cast.si().getSourceCard().getName());
                    value.put("source_id", cast.si().getSourceCard().getId());
                    value.put("is_spell", cast.sa().isSpell());
                }
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved) value.put("message", event.toString());
                events.add(value);
            }
        });
        row.put("registered_main_totals", List.of(60, 60));
        row.put("no_Blood_Artist", true); row.put("seed_scope", "once before model and both ordered fixtures; never reset");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_before_choice", rng());
        // No chooser, forecast, or affordability query precedes this ordinary callback.
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("first_choice", ability(chosen)); row.put("ordinary_Default_initial_callbacks", 1);
        row.put("rng_after_choice", rng());
        row.put("after_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        boolean firstSelected = chosen != null && chosen.getHostCard().getId() == oven.getId() && chosen.getApi() == ApiType.Token;
        need(chosen == null || firstSelected, "Unexpected initial action is not silently relabeled PASS");
        List<String> failed = new ArrayList<>();
        if (!firstSelected) failed.add("FIRST_DEFAULT_PASS_MISSES_NATIVE_TWO_ACTION_OVEN_CAT_WIN");
        row.put("first_AI_selected_Oven", firstSelected);
        row.put("manual_full_two_action_control_not_AI_success", !firstSelected);
        SpellAbility first = firstSelected ? chosen : activation(oven, actor, ApiType.Token);
        boolean ovenPaid = ComputerUtil.playStack(first, actor, game);
        need(ovenPaid && oven.isTapped()
                && actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == catId),
                "Actual selected/manual Oven pays tap and sacrifices the original Cat");
        resolve(game);
        need(!game.isGameOver() && enemy.getLife() == 1 && game.getStack().isEmpty(),
                "Oven payment/resolution alone is nonlethal without Blood Artist");
        need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Native Oven creates exactly one real Food");
        row.put("real_Food_id", food(actor).get(0).getId());
        row.put("after_Oven_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("Oven_actual_paid", ovenPaid); row.put("enemy_life_after_Oven", enemy.getLife());
        priority(game, actor, enemy);
        Card graveCat = actor.getCardsIn(ZoneType.Graveyard).stream().filter(c -> c.getId() == catId).findFirst().orElseThrow();
        SpellAbility second = null;
        boolean secondSelected = false;
        if (firstSelected) {
            row.put("rng_before_second_choice", rng());
            List<SpellAbility> next = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
            second = next == null || next.isEmpty() ? null : next.get(0);
            row.put("second_choice", ability(second)); row.put("rng_after_second_choice", rng());
            secondSelected = second != null && second.getHostCard().getId() == catId && second.getApi() == ApiType.ChangeZone;
            if (!secondSelected) failed.add("SECOND_DEFAULT_MISSES_NATIVE_CAT_RETURN_WIN");
        }
        row.put("ordinary_Default_subsequent_callbacks", firstSelected ? 1 : 0);
        row.put("second_AI_selected_Cat", secondSelected);
        row.put("second_manual_control_not_AI_success", !secondSelected);
        boolean catPaid = ComputerUtil.playStack(secondSelected ? second : activation(graveCat, actor, ApiType.ChangeZone), actor, game);
        need(catPaid, "Actual selected/manual Cat ability pays the genuine generated Food sacrifice");
        resolve(game);
        boolean won = game.isGameOver() && actor.hasWon() && enemy.hasLost();
        need(won && food(actor).isEmpty() && actor.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == catId),
                "Full actual native Cat return, Food consumption, entry drain, and win");
        row.put("Cat_actual_paid", catPaid); row.put("actual_native_win", won);
        row.put("AI_two_selected_actions_actual_win", firstSelected && secondSelected && won);
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("native_game_over", game.isGameOver()); row.put("food_after", food(actor).size());
        row.put("native_events", events); row.put("failures", failed);
        row.put("status", failed.isEmpty() ? "PASS" : "POLICY_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private report directory argument");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110620L));
        NativeDrainTactics8 audit = new NativeDrainTactics8(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, manualWins = 0, selectedWins = 0;
        String scene = "OvenCatTwoActionWin";
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", 2026110620L));
            try {
                audit.check(2026110620L, seat, scene, row);
                if (row.get("status").equals("PASS")) pass++; else red++;
                if (Boolean.TRUE.equals(row.get("manual_full_two_action_control_not_AI_success"))
                        && Boolean.TRUE.equals(row.get("actual_native_win"))) manualWins++;
                if (Boolean.TRUE.equals(row.get("AI_two_selected_actions_actual_win"))) selectedWins++;
            } catch (Throwable error) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
            }
            Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n");
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "CONTROLLED-NATIVE-OVEN-CAT-TWO-STEP2");
        summary.put("total", 2); summary.put("pass", pass); summary.put("policy_red", red); summary.put("harness_errors", errors);
        summary.put("natural_games", 0); summary.put("ordinary_Default_initial_callbacks", 2);
        summary.put("manual_full_two_action_native_wins", manualWins); summary.put("AI_two_selected_action_native_wins", selectedWins);
        summary.put("seed", 2026110620L); summary.put("seed_installations", 1);
        summary.put("manual_control_is_not_AI_success", true); summary.put("imminent_death_cost_fix_closes_this_gap", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
