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

public final class NativeTokenReturnPreferenceDanger4 extends AITest {
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
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("actor_life", actor.getLife()); record.put("enemy_life", enemy.getLife());
        record.put("native_game_over", game.isGameOver()); record.put("native_stack_empty", game.getStack().isEmpty());
        record.put("Food_ids", food(actor).stream().map(Card::getId).toList());
        record.put("actor_view", new ActorBoundary(actor).snapshot(game.getView())); record.put("rng", rng());
        return record;
    }
    private static void helperDiagnostic(boolean required, boolean expected, Player actor, SpellAbility ability,
                                         Map<String, Object> row) {
        row.put("helper_expected", expected);
        if (!required) {
            row.put("helper_status", "OMITTED_CONTROLS_ONLY_NO_QUALIFICATION"); return;
        }
        try {
            java.lang.reflect.Method helper = SpellAbilityAi.class.getDeclaredMethod("hasKnownWinningTokenReturn", Player.class, SpellAbility.class);
            if (helper.getReturnType() != boolean.class || !java.lang.reflect.Modifier.isPrivate(helper.getModifiers())
                    || !java.lang.reflect.Modifier.isStatic(helper.getModifiers())) {
                row.put("helper_status", "HELPER_ABI_RED"); return;
            }
            helper.setAccessible(true);
            boolean result = (Boolean) helper.invoke(null, actor, ability);
            row.put("postchoice_hasKnownWinningTokenReturn", result);
            row.put("helper_diagnostic_completed", true);
            row.put("helper_status", result == expected ? "MATCH" : "HELPER_VALUE_RED");
        } catch (NoSuchMethodException error) {
            row.put("helper_status", "HELPER_ABI_RED"); row.put("helper_error", error.toString());
        } catch (ReflectiveOperationException | RuntimeException error) {
            row.put("helper_status", "HELPER_DIAGNOSTIC_RED"); row.put("helper_error", error.toString());
        }
    }
    private void check(int seat, boolean danger, boolean requireHelper, Map<String, Object> row) throws Exception {
        row.put("rng_before_fixture_construction", rng());
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("token-return-preference-danger-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Witch's Oven", 1); deck.getMain().add("Cauldron Familiar", 1);
                if (!danger) deck.getMain().add("Blood Artist", 1);
                deck.getMain().add("Swamp", danger ? 58 : 57);
            } else {
                if (danger) deck.getMain().add("Disciple of the Vault", 1);
                deck.getMain().add("Mountain", danger ? 59 : 60);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("preference-danger-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-PROTOCOL-TOKEN-RETURN-PREFERENCE-DANGER4"));
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
        row.put("setup_before_any_pose", state(game, actor, enemy));
        if (danger) pose(enemy, "Disciple of the Vault");
        Card oven = pose(actor, "Witch's Oven"), cat = pose(actor, "Cauldron Familiar");
        Card artist = danger ? null : pose(actor, "Blood Artist");
        List<Card> lands = List.of(pose(actor, "Swamp"), pose(actor, "Swamp"));
        resolve(game);
        row.put("setup_all_outcomes_before_fixture_life_assignment", state(game, actor, enemy));
        int actorLife = danger ? 1 : 2, enemyLife = danger ? 1 : 2;
        row.put("fixture_life_assignment", Map.of("actor", actorLife, "enemy", enemyLife));
        actor.setLife(actorLife, null); enemy.setLife(enemyLife, null); game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && food(actor).isEmpty()
                && actor.getLife() == actorLife && enemy.getLife() == enemyLife
                && cat.isInZone(ZoneType.Battlefield) && !oven.isTapped() && lands.stream().noneMatch(Card::isTapped)
                && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Settled trusted native frontier, no Food or prior cost");
        need(actor.getCreaturesInPlay().size() == (danger ? 1 : 2), "Only the declared native sacrifice candidates");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default, MC off");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView())); row.put("rng_before_choice", rng());
        // No preference/helper/affordability diagnostic precedes the ordinary first callback.
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("first_choice", ability(chosen)); row.put("ordinary_Default_initial_callbacks", 1);
        row.put("rng_after_choice", rng()); row.put("first_choice_judged", !danger);
        row.put("native_Cat_SacMe_after_first_choice", actualCardRef(game, cat).getSVar("SacMe"));
        if (artist != null) row.put("native_Artist_SacMe_after_first_choice", actualCardRef(game, artist).getSVar("SacMe"));
        helperDiagnostic(requireHelper, !danger, actor, activation(actualCardRef(game, oven), actor, ApiType.Token), row);
        row.put("rng_after_helper_diagnostic", rng());
        boolean firstSelected = !danger && chosen != null && chosen.getHostCard().getId() == oven.getId() && chosen.getApi() == ApiType.Token;
        row.put("first_choice_executed", firstSelected);
        row.put("first_action_is_manual_control_not_AI_success", !firstSelected);
        List<String> policyFailures = new ArrayList<>(), controlFailures = new ArrayList<>();
        if (!danger && !firstSelected) policyFailures.add("FIRST_DEFAULT_MISSES_OVEN_CAT_ARTIST_TWO_LIFE_WIN");
        boolean ovenPaid = ComputerUtil.playStack(firstSelected ? chosen : activation(actualCardRef(game, oven), actor, ApiType.Token), actor, game);
        row.put("Oven_actual_paid", ovenPaid); need(ovenPaid && actualCardRef(game, oven).isTapped(), "Native Oven tap/sacrifice payment");
        List<Card> candidates = artist == null ? List.of(cat) : List.of(cat, artist);
        List<Card> victims = candidates.stream().map(c -> actualCardRef(game, c)).filter(c -> !c.isInZone(ZoneType.Battlefield)).toList();
        need(victims.size() == 1 && victims.get(0).isInZone(ZoneType.Graveyard), "Exactly one real original creature paid the unforced cost");
        Card victim = victims.get(0);
        row.put("actual_unforced_sacrifice_victim", Map.of("name", victim.getName(), "id", victim.getId()));
        boolean catVictim = victim.getId() == cat.getId(); row.put("native_payment_selected_Cat", catVictim);
        resolve(game);
        need(!game.isGameOver() && game.getStack().isEmpty() && food(actor).size() == 1 && food(actor).get(0).isToken(),
                "Actual Oven resolves to one native Food, still nonterminal");
        row.put("after_Oven_native_resolution", state(game, actor, enemy));
        boolean secondSelected = false, catPaid = false;
        if (!catVictim) {
            controlFailures.add("NATIVE_PAYMENT_PREFERENCE_DID_NOT_CHOOSE_CAT_NO_RETURN_FORCED");
            row.put("Cat_return_not_forced", true);
        } else {
            priority(game, actor, enemy); SpellAbility second = null;
            if (!danger && firstSelected) {
                row.put("rng_before_second_choice", rng());
                List<SpellAbility> next = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
                second = next == null || next.isEmpty() ? null : next.get(0);
                row.put("second_choice", ability(second)); row.put("ordinary_Default_subsequent_callbacks", 1);
                row.put("rng_after_second_choice", rng());
                secondSelected = second != null && second.getHostCard().getId() == cat.getId() && second.getApi() == ApiType.ChangeZone;
                if (!secondSelected) policyFailures.add("SECOND_DEFAULT_MISSES_CAT_RETURN");
            }
            row.put("second_action_is_manual_control_not_AI_success", !secondSelected);
            catPaid = ComputerUtil.playStack(secondSelected ? second : activation(actualCardRef(game, cat), actor, ApiType.ChangeZone), actor, game);
            row.put("Cat_actual_paid", catPaid); need(catPaid, "Actual Cat pays real Food sacrifice");
            need(food(actor).isEmpty(), "Actual Cat cost consumed the real artifact Food");
            row.put("after_Cat_payment_before_native_resolution", state(game, actor, enemy));
            resolve(game);
        }
        boolean actorWon = game.isGameOver() && actor.hasWon() && enemy.hasLost();
        boolean actorLostBeforeReturn = game.isGameOver() && actor.hasLost() && enemy.hasWon()
                && actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == cat.getId());
        if (danger) {
            if (!catPaid || !actorLostBeforeReturn) controlFailures.add("NATIVE_DISCIPLE_DID_NOT_PROVE_RESOURCE_COST_DEATH_BEFORE_RETURN");
        } else if (!actorWon || !catVictim || !actualCardRef(game, cat).isInZone(ZoneType.Battlefield)) {
            controlFailures.add("NATIVE_PREFERENCE_LINE_DID_NOT_WIN");
        }
        row.putIfAbsent("ordinary_Default_subsequent_callbacks", 0);
        row.put("actual_native_actor_win", actorWon); row.put("actual_native_actor_loss_before_Cat_return", actorLostBeforeReturn);
        row.put("AI_two_selected_actions_actual_win", !danger && firstSelected && secondSelected && actorWon);
        row.put("manual_full_sequence_actor_win_not_AI_success", !danger && !firstSelected && actorWon);
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("native_game_over", game.isGameOver()); row.put("food_after", food(actor).size());
        row.put("rng_after_native_outcome", rng()); row.put("policy_failures", policyFailures); row.put("control_failures", controlFailures);
        row.put("control_status", controlFailures.isEmpty() ? "MATCH" : "CONTROL_RED");
        row.put("policy_status", danger ? "UNJUDGED" : policyFailures.isEmpty() ? "MATCH" : "POLICY_RED");
        String helperStatus = String.valueOf(row.get("helper_status"));
        row.put("status", !controlFailures.isEmpty() ? "CONTROL_RED" : helperStatus.endsWith("RED") ? helperStatus
                : !policyFailures.isEmpty() ? "POLICY_RED" : requireHelper ? "PASS" : "CONTROL_PASS_UNQUALIFIED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 2, "Fresh private report directory and require-helper or controls-only mode; specific external GO required");
        Path out = Path.of(args[0]); need(Files.isDirectory(out), "Runner-created fresh report directory");
        need(args[1].equals("require-helper") || args[1].equals("controls-only"), "Explicit helper qualification mode");
        boolean requireHelper = args[1].equals("require-helper");
        MyRandom.setRandom(new Random(2026110701L)); String initialRng = rng();
        NativeTokenReturnPreferenceDanger4 audit = new NativeTokenReturnPreferenceDanger4(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, unqualified = 0, red = 0, errors = 0, callbacks = 0, helperAbiRed = 0, controlMatch = 0, policyRed = 0;
        for (boolean danger : List.of(false, true)) for (int seat = 0; seat < 2; seat++) {
            String scene = danger ? "DiscipleResourceDeathDanger" : "OvenCatArtistOpponentTwoLifePreference";
            Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", 2026110701L,
                    "label", "INTERNAL-PROTOCOL", "mode", args[1]));
            try {
                audit.check(seat, danger, requireHelper, row);
                if (row.get("status").equals("PASS")) pass++;
                else if (row.get("status").equals("CONTROL_PASS_UNQUALIFIED")) unqualified++;
                else red++;
            } catch (Throwable error) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
            }
            callbacks += ((Number) row.getOrDefault("ordinary_Default_initial_callbacks", 0)).intValue();
            if ("HELPER_ABI_RED".equals(row.get("helper_status"))) helperAbiRed++;
            if ("MATCH".equals(row.get("control_status"))) controlMatch++;
            if ("POLICY_RED".equals(row.get("policy_status"))) policyRed++;
            Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "INTERNAL-PROTOCOL-TOKEN-RETURN-PREFERENCE-DANGER4"); summary.put("total", 4); summary.put("mode", args[1]);
        summary.put("pass", pass); summary.put("control_pass_unqualified", unqualified); summary.put("red", red); summary.put("harness_errors", errors);
        summary.put("ordinary_Default_initial_callbacks", callbacks); summary.put("helper_ABI_red_not_game_failure", helperAbiRed);
        summary.put("native_control_matches", controlMatch); summary.put("ordinary_policy_red", policyRed);
        summary.put("helper_qualification_claimed", requireHelper && pass == 4 && errors == 0);
        summary.put("seed", 2026110701L); summary.put("seed_installations", 1); summary.put("rng_after_seed_before_model", initialRng);
        summary.put("sacrifice_payment_forced_to_Cat", false); summary.put("manual_controls_are_AI_successes", false);
        summary.put("natural_games", 0); summary.put("expert_games", 0); summary.put("RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
