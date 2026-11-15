// SPDX-License-Identifier: GPL-3.0-or-later
// Trusted registered fixtures with actual Forge payment, resolution and land abilities.
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
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class NativeExpiringLand6 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().setPrettyPrinting().create();
    private static final long SEED = 2026110706L;
    private static final int SETUP_TURN = 6;
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
    private static Card current(Player player, int id, ZoneType zone) {
        return player.getCardsIn(zone).stream().filter(c -> c.getId() == id).findFirst().orElseThrow();
    }
    private static Card pose(Player player, String name) {
        return player.getGame().getAction().moveToPlay(library(player, name), player, null, AbilityKey.newMap());
    }
    private static Card hand(Player player, String name) {
        return player.getGame().getAction().moveToHand(library(player, name), null);
    }
    private static void priority(Game game, Player actor, Player enemy) {
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true);
        enemy.setHasPriority(false);
    }
    private static void resolve(Game game) {
        for (int n = 0; n < 30; n++) {
            need(!game.isGameOver(), "Unexpected terminal setup/control");
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        throw new IllegalStateException("HARNESS: bounded actual native resolution exceeded");
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) { out.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Object> describe(SpellAbility sa) {
        Map<String, Object> row = new LinkedHashMap<>();
        if (sa == null) { row.put("choice", "PASS"); return row; }
        row.put("source", sa.getHostCard().getName());
        row.put("source_id", sa.getHostCard().getId());
        row.put("source_zone", String.valueOf(sa.getHostCard().getZone().getZoneType()));
        row.put("ability_id", sa.getId());
        row.put("api", String.valueOf(sa.getApi()));
        row.put("is_land", sa.isLandAbility());
        row.put("is_spell", sa.isSpell());
        return row;
    }
    private static List<SpellAbility> landOptions(Card card, Player actor) {
        List<SpellAbility> options = card.getAllPossibleAbilities(actor, false).stream()
                .filter(SpellAbility::isLandAbility).toList();
        for (SpellAbility sa : options) sa.setActivatingPlayer(actor);
        return options;
    }
    private static SpellAbility manualLand(Card card, Player actor) {
        List<SpellAbility> options = landOptions(card, actor);
        need(!options.isEmpty(), "Actual manual land play requires an offered native ability");
        return options.stream().filter(SpellAbility::canPlay).findFirst().orElse(options.get(0));
    }
    private static List<Map<String, Object>> diagnostics(Card card, Player actor) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (SpellAbility sa : landOptions(card, actor)) {
            Map<String, Object> row = describe(sa);
            row.put("can_play", sa.canPlay());
            if (sa.getMayPlay() != null) {
                Card host = sa.getMayPlay().getHostCard();
                row.put("permission_params", new LinkedHashMap<>(sa.getMayPlay().getMapParams()));
                row.put("permission_host_id", host.getId());
                row.put("permission_host_zone", String.valueOf(host.getZone().getZoneType()));
                row.put("permission_effect_source_id", host.getEffectSource() == null ? null : host.getEffectSource().getId());
                row.put("permission_effect_source_ability_params", host.getEffectSourceAbility() == null
                        ? null : new LinkedHashMap<>(host.getEffectSourceAbility().getMapParams()));
            }
            result.add(row);
        }
        return result;
    }
    private static void refused(Player actor, Card card, Map<String, Object> row, String label) {
        Game game = actor.getGame();
        ZoneType before = card.getZone().getZoneType();
        int drops = actor.getLandsPlayedThisTurn();
        if (landOptions(card, actor).isEmpty()) {
            boolean allowed = actor.canPlayLand(card, false, card.getFirstSpellAbility());
            row.put(label, Map.of("manual_not_AI", true, "native_options_empty", true,
                    "can_play", allowed, "controller_dispatch_attempted", false));
            need(!allowed && actor.getLandsPlayedThisTurn() == drops
                    && actor.getCardsIn(before).stream().anyMatch(c -> c.getId() == card.getId()),
                    label + " native option absence and checked land rejection");
            return;
        }
        SpellAbility attempt = manualLand(card, actor);
        boolean allowed = attempt.canPlay();
        // The controller returns true even for refusal; observe actual zone and land count instead.
        boolean returned = ((PlayerControllerAi) actor.getController()).playChosenSpellAbility(attempt);
        resolve(game);
        boolean unchanged = actor.getLandsPlayedThisTurn() == drops
                && actor.getCardsIn(before).stream().anyMatch(c -> c.getId() == card.getId());
        row.put(label, Map.of("manual_not_AI", true, "can_play", allowed,
                "controller_return_not_success_proof", returned, "zone_and_land_count_unchanged", unchanged));
        need(!allowed && unchanged, label + " actual native refusal");
    }
    private void check(int seat, String scene, Map<String, Object> row) throws Exception {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("expiring-land6-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Expressive Iteration", 1);
                deck.getMain().add("Sprite Dragon", 1);
                deck.getMain().add("Mountain", 4);
                deck.getMain().add("Island", 54);
            } else deck.getMain().add("Mountain", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("expiring-land6-seat-" + index, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-EXPIRING-LAND6"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int n = 0; n < entry.getValue(); n++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60
                    && player.getAllCards().size() == 60, "Registered60 complete originals");
        }
        row.put("registered_totals_before_effect_creation", List.of(60, 60));
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor, SETUP_TURN);
        game.getPhaseHandler().onStackResolved();
        pose(actor, "Island"); pose(actor, "Mountain"); pose(actor, "Mountain");
        Card originalHandIsland = hand(actor, "Island");
        Card dragon = hand(actor, "Sprite Dragon");
        Card iteration = hand(actor, "Expressive Iteration");
        List<Map<String, Object>> events = new ArrayList<>();
        row.put("native_events", events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> value = new LinkedHashMap<>();
                value.put("index", events.size() + 1);
                value.put("event", event.getClass().getSimpleName());
                value.put("turn", game.getPhaseHandler().getTurn());
                value.put("phase", String.valueOf(game.getPhaseHandler().getPhase()));
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    value.put("source_id", cast.si().getSourceCard().getId());
                    value.put("source", cast.si().getSourceCard().getName());
                    value.put("targets", cast.targetDescription());
                    value.put("paid_mana_observed", false);
                    for (var item : game.getStack()) if (item.getId() == cast.si().getId()) {
                        value.put("paid_mana_observed", true);
                        value.put("paid_mana", item.getSpellAbility().getPayingMana().stream().map(m -> Map.of(
                                "color", m.getColor(), "source_id", m.getSourceCard() == null ? -1 : m.getSourceCard().getId())).toList());
                        break;
                    }
                }
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved
                        || event instanceof forge.game.event.GameEventLandPlayed) value.put("message", event.toString());
                events.add(value);
            }
        });
        resolve(game);
        actor.setLife(20, null); enemy.setLife(20, null);
        priority(game, actor, enemy);
        if (scene.equals("EXHAUSTED")) {
            Card consume = hand(actor, "Mountain");
            SpellAbility setupLand = manualLand(consume, actor);
            need(setupLand.canPlay(), "Actual setup land available before exhaustion");
            ((PlayerControllerAi) actor.getController()).playChosenSpellAbility(setupLand);
            resolve(game);
            need(actor.getLandsPlayedThisTurn() == 1
                    && actor.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == consume.getId()),
                    "Real land play consumes the land drop; no counter mutation");
            row.put("exhaustion_setup_land_id", consume.getId());
        }
        List<Card> top = actor.getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals("Island")).limit(3).toList();
        need(top.size() == 3, "Three registered original Islands for top pose");
        for (int i = top.size() - 1; i >= 0; i--) game.getAction().moveToLibrary(top.get(i), 0, null);
        List<Integer> topIds = top.stream().map(Card::getId).toList();
        need(actor.getCardsIn(ZoneType.Library).stream().limit(3).map(Card::getId).toList().equals(topIds),
                "Trusted own library ordering, no injected choice or card");
        row.put("trusted_own_top3_ids", topIds);
        row.put("original_hand_Island_id", originalHandIsland.getId());
        row.put("useful_cast_Sprite_Dragon_id", dragon.getId());
        row.put("before_paid_setup_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        SpellAbility spell = iteration.getSpellAbilities().stream()
                .filter(sa -> sa.isSpell() && sa.getApi() == ApiType.Dig).findFirst().orElseThrow();
        spell.setActivatingPlayer(actor);
        boolean paid = ComputerUtil.playStack(spell, actor, game);
        row.put("manual_Iteration_not_AI_choice", true);
        row.put("Iteration_actual_paid", paid);
        need(paid, "Genuine Iteration UR payment");
        List<?> paidMana = (List<?>) events.stream()
                .filter(e -> "GameEventSpellAbilityCast".equals(e.get("event"))
                        && Integer.valueOf(iteration.getId()).equals(e.get("source_id")))
                .findFirst().orElseThrow().get("paid_mana");
        need(paidMana != null && paidMana.size() == 2
                && paidMana.stream().anyMatch(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 2)
                && paidMana.stream().anyMatch(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 8),
                "Native stack instance records actual U and R payment");
        resolve(game);
        need(actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == iteration.getId()),
                "Actual complete Iteration resolves to graveyard");
        List<Card> derivedHand = actor.getCardsIn(ZoneType.Hand).stream().filter(c -> topIds.contains(c.getId())).toList();
        List<Card> derivedExile = actor.getCardsIn(ZoneType.Exile).stream().filter(c -> topIds.contains(c.getId())).toList();
        List<Card> derivedBottom = actor.getCardsIn(ZoneType.Library).stream().filter(c -> topIds.contains(c.getId())).toList();
        need(derivedHand.size() == 1 && derivedExile.size() == 1 && derivedBottom.size() == 1,
                "Native Dig chain partitions three real originals, not forced choices");
        need(actor.getCardsIn(ZoneType.Library).get(actor.getCardsIn(ZoneType.Library).size() - 1).getId()
                == derivedBottom.get(0).getId(), "Native partition's remaining Island is actually bottom");
        int exileId = derivedExile.get(0).getId();
        row.put("native_partition", Map.of("hand", derivedHand.get(0).getId(),
                "exile", exileId, "bottom", derivedBottom.get(0).getId()));
        row.put("after_paid_Iteration_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        need(actor.getLandsInPlay().stream().filter(c -> !c.isTapped()).allMatch(c -> c.getName().equals("Mountain"))
                && actor.getLandsInPlay().stream().anyMatch(c -> !c.isTapped() && c.getName().equals("Mountain")),
                "Paid setup leaves red only; fresh Island enables the useful UR creature");
        if (scene.equals("EXPIRED")) {
            // Trusted clock boundary invokes the real command registered by native EffectEffect.
            game.getPhaseHandler().devModeSet(PhaseType.CLEANUP, actor, SETUP_TURN);
            game.getEndOfTurn().executeUntil();
            resolve(game);
            game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor, SETUP_TURN + 2);
            game.getPhaseHandler().onStackResolved();
            row.put("expiry_boundary", "Trusted CLEANUP clock + actual EOT executeUntil; next own MAIN1. Not natural turn progression.");
        }
        priority(game, actor, enemy);
        need(actor.getLandsPlayedThisTurn() == (scene.equals("EXHAUSTED") ? 1 : 0)
                && game.getStack().isEmpty() && !game.isGameOver(), "Settled declared first-choice frontier");
        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        need(actor.getController().getClass() == PlayerControllerAi.class && !controller.getAi().usesSimulation(),
                "Ordinary Default, MC off, no choice override");
        row.put("before_first_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_before_first_choice", rng());
        // First and only ordinary root callback precedes permission/affordability diagnostics.
        List<SpellAbility> choices = controller.chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("ordinary_root_callback_count", 1);
        row.put("first_choice", describe(chosen));
        row.put("first_choice_count", choices == null ? 0 : choices.size());
        row.put("rng_after_first_choice", rng());
        row.put("after_first_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        Card exile = current(actor, exileId, ZoneType.Exile);
        List<Card> handIslands = actor.getCardsIn(ZoneType.Hand).stream().filter(c -> c.getName().equals("Island")).toList();
        need(handIslands.size() == 2, "Original hand Island plus native kept Island");
        row.put("exile_diagnostics_AFTER_callback", diagnostics(exile, actor));
        row.put("hand_diagnostics_AFTER_callback", diagnostics(handIslands.get(0), actor));
        List<Map<String, Object>> permissionRows = new ArrayList<>();
        for (var option : exile.mayPlay(actor)) {
            Map<String, Object> permission = new LinkedHashMap<>();
            permission.put("host_id", option.getHost().getId());
            permission.put("host_zone", String.valueOf(option.getHost().getZone().getZoneType()));
            permission.put("applies_to_actor", option.appliesTo(actor));
            permission.put("grants_zone_permissions", option.grantsZonePermissions());
            permission.put("static_params", new LinkedHashMap<>(option.getAbility().getMapParams()));
            permissionRows.add(permission);
        }
        row.put("native_CardPlayOptions_AFTER_callback", permissionRows);
        need(permissionRows.isEmpty() == scene.equals("EXPIRED"),
                "Native permission remains active when exhausted but vanishes after actual cleanup");
        boolean exilePlayable = landOptions(exile, actor).stream().anyMatch(SpellAbility::canPlay);
        boolean handPlayable = landOptions(handIslands.get(0), actor).stream().anyMatch(SpellAbility::canPlay);
        need(exilePlayable == scene.equals("ACTIVE") && handPlayable == !scene.equals("EXHAUSTED"),
                "Actual permission and land-limit control must match declared scene, never assumed");
        List<String> red = new ArrayList<>();
        String unqualified = null;
        boolean selectedLand = chosen != null && chosen.isLandAbility();
        if (scene.equals("EXHAUSTED")) {
            if (selectedLand) red.add("EXHAUSTED_ROOT_SELECTED_LAND");
            else if (chosen != null) unqualified = "UNEXPECTED_NONLAND_FIRST_CHOICE";
            refused(actor, exile, row, "manual_exile_refusal");
            refused(actor, handIslands.get(0), row, "manual_hand_refusal");
        } else {
            if (!selectedLand) unqualified = "MAIN1_LAND_BRANCH_NOT_OBSERVED_NOT_SOURCE_SELECTION_RED";
            else if (scene.equals("ACTIVE") && chosen.getHostCard().getId() != exileId)
                red.add("ACTIVE_CHOSE_HAND_OVER_PLAYABLE_EXPIRING_EXILE");
            else if (scene.equals("EXPIRED") && handIslands.stream().noneMatch(c -> c.getId() == chosen.getHostCard().getId()))
                red.add("EXPIRED_ROOT_DID_NOT_SELECT_HAND_LAND");
            if (scene.equals("EXPIRED")) refused(actor, exile, row, "manual_expired_exile_refusal_before_any_land_payment");
            boolean executeAI = selectedLand && red.isEmpty();
            Card controlCard = scene.equals("ACTIVE") ? exile : handIslands.get(0);
            SpellAbility play = executeAI ? chosen : manualLand(controlCard, actor);
            int playId = play.getHostCard().getId();
            need(play.canPlay(), "Actual selected/manual land is legal at time of payment");
            controller.playChosenSpellAbility(play);
            resolve(game);
            need(actor.getLandsPlayedThisTurn() == 1
                    && actor.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == playId),
                    "Actual selected/manual land move consumes native land allowance");
            row.put("land_actual_played_id", playId);
            row.put("land_actual_play_executed_AI_selection", executeAI);
            row.put("manual_alternative_not_AI_success", !executeAI);
            row.put("after_land_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        }
        row.put("failures", red);
        row.put("not_qualified_reason", unqualified);
        row.put("status", !red.isEmpty() ? "POLICY_RED" : unqualified != null ? "NOT_QUALIFIED" : "PASS");
        row.put("final_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_final", rng());
        row.put("purity_claim", false);
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh report-directory argument");
        Path out = Path.of(args[0]);
        Files.createDirectories(out);
        need(!Files.exists(out.resolve("summary.json")), "Once-only report root");
        MyRandom.setRandom(new Random(SEED));
        NativeExpiringLand6 probe = new NativeExpiringLand6();
        probe.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Map<String, Object>> rows = new ArrayList<>();
        int pass = 0, red = 0, errors = 0, unqualified = 0;
        for (String scene : List.of("ACTIVE", "EXPIRED", "EXHAUSTED")) for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("scene", scene); row.put("seat", seat); row.put("seed", SEED);
            try { probe.check(seat, scene, row); }
            catch (Throwable error) {
                row.put("status", "HARNESS_ERROR"); row.put("error", error.toString());
                error.printStackTrace();
            }
            switch (String.valueOf(row.get("status"))) {
                case "PASS" -> pass++;
                case "POLICY_RED" -> red++;
                case "NOT_QUALIFIED" -> unqualified++;
                default -> errors++;
            }
            rows.add(row);
            Files.writeString(out.resolve(scene + "-seat" + seat + ".json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW);
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("planned", 6); summary.put("passed", pass); summary.put("red", red);
        summary.put("errors", errors); summary.put("not_qualified", unqualified);
        summary.put("cases", rows);
        summary.put("seed_once_before_construction", SEED);
        summary.put("AiController_origin", AiController.class.getProtectionDomain().getCodeSource().getLocation().toString());
        Files.writeString(out.resolve("summary.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(Map.of("planned", 6, "passed", pass, "red", red, "errors", errors, "not_qualified", unqualified)));
        System.exit(errors > 0 ? 2 : red > 0 || unqualified > 0 ? 1 : 0);
    }
}
