// SPDX-License-Identifier: GPL-3.0-or-later
// One paid canonical frontier, then explicitly counterfactual Mockito metadata checks.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.AITest;
import forge.ai.AiController;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.ability.AbilityKey;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.card.CardPlayOption;
import forge.game.card.CardView;
import forge.game.phase.PhaseType;
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
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;

public final class NativeExpiringPermissionProtocol17 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().setPrettyPrinting().create();
    private final List<Map<String, Object>> rows = new ArrayList<>();
    private final Map<String, Object> setup = new LinkedHashMap<>();
    private Player actor;
    private Card realLand;
    private CardPlayOption realOption;
    private Method helper;
    private AiController ai;

    private static void need(boolean value, String message) {
        if (!value) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true);
        return card;
    }
    private static Card library(Player player, String name) {
        return player.getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
    }
    private static Card pose(Player player, String name) {
        return player.getGame().getAction().moveToPlay(library(player, name), player, null, AbilityKey.newMap());
    }
    private static Card hand(Player player, String name) {
        return player.getGame().getAction().moveToHand(library(player, name), null);
    }
    private static void resolve(Game game) {
        for (int n = 0; n < 30; n++) {
            need(!game.isGameOver(), "Unexpected terminal setup");
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        throw new IllegalStateException("HARNESS: native resolution exceeded bound");
    }
    private void frontier() throws Exception {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int seat = 0; seat < 2; seat++) {
            Deck deck = new Deck("permission-protocol-seat-" + seat);
            if (seat == 0) {
                deck.getMain().add("Expressive Iteration", 1);
                deck.getMain().add("Sprite Dragon", 1);
                deck.getMain().add("Mountain", 4);
                deck.getMain().add("Island", 54);
            } else deck.getMain().add("Mountain", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("permission-protocol-seat-" + seat, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "PAID-FRONTIER-PROTOCOL17"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        actor = game.getPlayers().get(0);
        Player enemy = game.getPlayers().get(1);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int n = 0; n < entry.getValue(); n++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60
                    && player.getAllCards().size() == 60, "Complete registered original120");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor, 6);
        game.getPhaseHandler().onStackResolved();
        pose(actor, "Island"); pose(actor, "Mountain"); pose(actor, "Mountain");
        hand(actor, "Island"); hand(actor, "Sprite Dragon");
        Card iteration = hand(actor, "Expressive Iteration");
        List<Map<String, Object>> events = new ArrayList<>();
        setup.put("events", events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("index", events.size() + 1);
                row.put("event", event.getClass().getSimpleName());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    row.put("source_id", cast.si().getSourceCard().getId());
                    for (var item : game.getStack()) if (item.getId() == cast.si().getId()) {
                        row.put("paid_mana", item.getSpellAbility().getPayingMana().stream()
                                .map(m -> Map.of("color", (int) m.getColor(), "source_id", m.getSourceCard().getId())).toList());
                        break;
                    }
                }
                events.add(row);
            }
        });
        resolve(game);
        actor.setLife(20, null); enemy.setLife(20, null);
        List<Card> top = actor.getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals("Island")).limit(3).toList();
        need(top.size() == 3, "Three original top Islands");
        List<Integer> ids = top.stream().map(Card::getId).toList();
        for (int i = 2; i >= 0; i--) game.getAction().moveToLibrary(top.get(i), 0, null);
        need(actor.getCardsIn(ZoneType.Library).stream().limit(3).map(Card::getId).toList().equals(ids),
                "Trusted own top order");
        setup.put("top3_original_ids", ids);
        SpellAbility spell = iteration.getSpellAbilities().stream()
                .filter(sa -> sa.isSpell() && sa.getApi() == ApiType.Dig).findFirst().orElseThrow();
        spell.setActivatingPlayer(actor);
        boolean paid = ComputerUtil.playStack(spell, actor, game);
        setup.put("manual_Iteration_actual_paid_not_AI", paid);
        need(paid, "Native paid Iteration");
        List<?> mana = (List<?>) events.stream().filter(e -> Integer.valueOf(iteration.getId()).equals(e.get("source_id")))
                .findFirst().orElseThrow().get("paid_mana");
        need(mana != null && mana.size() == 2
                && mana.stream().anyMatch(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 2)
                && mana.stream().anyMatch(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 8), "Actual U/R payment");
        resolve(game);
        List<Card> exiled = actor.getCardsIn(ZoneType.Exile).stream().filter(c -> ids.contains(c.getId())).toList();
        List<Card> kept = actor.getCardsIn(ZoneType.Hand).stream().filter(c -> ids.contains(c.getId())).toList();
        List<Card> bottom = actor.getCardsIn(ZoneType.Library).stream().filter(c -> ids.contains(c.getId())).toList();
        need(exiled.size() == 1 && kept.size() == 1 && bottom.size() == 1
                && actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == iteration.getId()),
                "Native complete Iteration partition and resolution");
        need(actor.getCardsIn(ZoneType.Library).get(actor.getCardsIn(ZoneType.Library).size() - 1).getId()
                == bottom.get(0).getId(), "Native bottom result");
        realLand = exiled.get(0);
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        ai = controller.getAi();
        need(actor.getController().getClass() == PlayerControllerAi.class && !ai.usesSimulation()
                && actor.getLandsPlayedThisTurn() == 0 && game.getStack().isEmpty(), "Ordinary settled first frontier");
        setup.put("before_first_root_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        List<SpellAbility> first = controller.chooseSpellAbilityToPlay();
        setup.put("ordinary_first_root_count", 1);
        setup.put("first_root_unjudged_unplayed", first == null || first.isEmpty() ? "PASS"
                : Map.of("source_id", first.get(0).getHostCard().getId(), "is_land", first.get(0).isLandAbility()));
        setup.put("after_first_root_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        // All helper reflection, permission inspection, and Mockito work start after the ordinary callback.
        helper = AiController.class.getDeclaredMethod("hasExpiringLandPermission", Card.class);
        helper.setAccessible(true);
        List<CardPlayOption> permissions = realLand.mayPlay(actor);
        need(permissions.size() == 1, "Exactly one genuinely created native permission");
        realOption = permissions.get(0);
        need(realOption.appliesTo(actor) && realOption.grantsZonePermissions()
                && realOption.getHost().getEffectSourceAbility() != null, "Actual permission creator exists");
        setup.put("actual_permission_static_params", new LinkedHashMap<>(realOption.getAbility().getMapParams()));
        setup.put("actual_creator_params", new LinkedHashMap<>(realOption.getHost().getEffectSourceAbility().getMapParams()));
        setup.put("native_setup_not_natural_game", true);
        setup.put("protocol_variants_are_spies_not_real_cards_or_effects", true);
    }
    private CardPlayOption option(String duration, ApiType api, boolean missingCreator) {
        Card effect = spy(realOption.getHost());
        SpellAbility creator = spy(realOption.getHost().getEffectSourceAbility());
        doReturn(duration).when(creator).getParam("Duration");
        doReturn(api).when(creator).getApi();
        doReturn(missingCreator ? null : creator).when(effect).getEffectSourceAbility();
        CardPlayOption option = spy(realOption);
        doReturn(effect).when(option).getHost();
        return option;
    }
    private Card land(List<CardPlayOption> options) {
        Card land = spy(realLand);
        doReturn(options).when(land).mayPlay(actor);
        return land;
    }
    private void check(String name, boolean expected, Card land, Runnable noBodyReadCheck) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("label", name); row.put("expected", expected);
        row.put("kind", name.equals("ABSENT_NATIVE") ? "REAL_FRONTIER_HELPER" : "PROTOCOL_ONLY_METADATA_SPY");
        try {
            boolean actual = (Boolean) helper.invoke(ai, land);
            row.put("actual", actual);
            if (noBodyReadCheck != null) noBodyReadCheck.run();
            row.put("status", actual == expected ? "PASS" : "PROTOCOL_RED");
        } catch (InvocationTargetException e) {
            row.put("status", "PROTOCOL_RED"); row.put("error", e.getCause().toString());
        } catch (AssertionError e) {
            row.put("status", "PROTOCOL_RED"); row.put("error", e.toString());
        } catch (ReflectiveOperationException e) {
            row.put("status", "HARNESS_ERROR"); row.put("error", e.toString());
        }
        rows.add(row);
    }
    private void hidden(String level, boolean faceDownGate) {
        Card target;
        Card land = land(List.of(realOption));
        Card effect = spy(realOption.getHost());
        SpellAbility creator = spy(realOption.getHost().getEffectSourceAbility());
        CardPlayOption option = spy(realOption);
        doReturn(effect).when(option).getHost();
        doReturn(List.of(option)).when(land).mayPlay(actor);
        doReturn(creator).when(effect).getEffectSourceAbility();
        if (level.equals("LAND")) target = land;
        else if (level.equals("EFFECT")) target = effect;
        else {
            target = spy(creator.getHostCard());
            doReturn(target).when(creator).getHostCard();
        }
        CardView view = spy(target.getView());
        doReturn(view).when(target).getView();
        doReturn(true).when(view).canBeShownTo(actor.getView());
        doReturn(true).when(view).canFaceDownBeShownTo(actor.getView());
        if (faceDownGate) doReturn(false).when(view).canFaceDownBeShownTo(actor.getView());
        else doReturn(false).when(view).canBeShownTo(actor.getView());
        Runnable verification;
        if (level.equals("LAND")) {
            doThrow(new AssertionError("Hidden land permission body read")).when(land).mayPlay(actor);
            verification = () -> verify(land, never()).mayPlay(actor);
        } else if (level.equals("EFFECT")) {
            doThrow(new AssertionError("Hidden effect immutable body read")).when(effect).isImmutable();
            doThrow(new AssertionError("Hidden effect creator body read")).when(effect).getEffectSourceAbility();
            verification = () -> {
                verify(effect, never()).isImmutable();
                verify(effect, never()).getEffectSourceAbility();
            };
        } else {
            doThrow(new AssertionError("Hidden creator API body read")).when(creator).getApi();
            doThrow(new AssertionError("Hidden creator duration body read")).when(creator).getParam("Duration");
            verification = () -> {
                verify(creator, never()).getApi();
                verify(creator, never()).getParam("Duration");
            };
        }
        check("HIDDEN_" + level + (faceDownGate ? "_FACE_DOWN_GATE" : "_PUBLIC_GATE"), false, land, verification);
    }
    private void protocol() {
        check("ABSENT_NATIVE", true, realLand, null);
        check("EXPLICIT_EOT", true, land(List.of(option("UntilEndOfTurn", ApiType.Effect, false))), null);
        check("PERMANENT", false, land(List.of(option("Permanent", ApiType.Effect, false))), null);
        check("UNTIL_YOUR_NEXT_TURN", false, land(List.of(option("UntilYourNextTurn", ApiType.Effect, false))), null);
        check("UNKNOWN_DURATION", false, land(List.of(option("PROTOCOL_UNKNOWN_DURATION", ApiType.Effect, false))), null);
        check("NON_EFFECT_CREATOR", false, land(List.of(option(null, ApiType.Dig, false))), null);
        check("MISSING_CREATOR", false, land(List.of(option(null, ApiType.Effect, true))), null);
        for (String duration : List.of("Permanent", "PROTOCOL_UNKNOWN_DURATION")) {
            CardPlayOption other = option(duration, ApiType.Effect, false);
            check("MIXED_" + duration + "_EXPIRING_FIRST", false, land(List.of(realOption, other)), null);
            check("MIXED_" + duration + "_EXPIRING_LAST", false, land(List.of(other, realOption)), null);
        }
        for (String level : List.of("LAND", "EFFECT", "CREATOR")) {
            hidden(level, false);
            hidden(level, true);
        }
        need(rows.size() == 17, "Fixed protocol count");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh report-directory argument");
        Path out = Path.of(args[0]);
        Files.createDirectories(out);
        need(!Files.exists(out.resolve("summary.json")), "Once-only report root");
        NativeExpiringPermissionProtocol17 probe = new NativeExpiringPermissionProtocol17();
        int setupErrors = 0;
        try {
            MyRandom.setRandom(new Random(2026110717L));
            probe.initializeModel();
            FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
            FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
            probe.frontier();
            probe.protocol();
        } catch (Throwable error) {
            setupErrors++;
            probe.setup.put("harness_error", error.toString());
            error.printStackTrace();
        }
        long passed = probe.rows.stream().filter(r -> "PASS".equals(r.get("status"))).count();
        long red = probe.rows.stream().filter(r -> "PROTOCOL_RED".equals(r.get("status"))).count();
        long errors = setupErrors + probe.rows.stream().filter(r -> "HARNESS_ERROR".equals(r.get("status"))).count();
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("planned", 17); summary.put("passed", passed); summary.put("red", red); summary.put("errors", errors);
        summary.put("observed_rows", probe.rows.size()); summary.put("setup", probe.setup); summary.put("cases", probe.rows);
        summary.put("AiController_origin", AiController.class.getProtectionDomain().getCodeSource().getLocation().toString());
        summary.put("Mockito_origin", org.mockito.Mockito.class.getProtectionDomain().getCodeSource().getLocation().toString());
        summary.put("strength_or_AI_game_success_claim", false);
        Files.writeString(out.resolve("summary.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(Map.of("planned", 17, "passed", passed, "red", red, "errors", errors, "observed_rows", probe.rows.size())));
        System.exit(errors > 0 ? 2 : red > 0 || passed != 17 ? 1 : 0);
    }
}
