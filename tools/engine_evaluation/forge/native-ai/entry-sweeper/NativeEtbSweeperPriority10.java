// SPDX-License-Identifier: GPL-3.0-or-later
// Declared priority-consistency controls, not natural games or universal strategy goldens.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.AbilityKey;
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

public final class NativeEtbSweeperPriority10 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110741L;
    private static void need(boolean value, String message) {
        if (!value) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true);
        return card;
    }
    private static Deck deck(boolean ramp) {
        Deck deck = new Deck(ramp ? "case18-public-Ramp" : "case18-public-Tribal");
        String[] names = ramp ? new String[]{"Arboreal Grazer", "Growth Spiral", "Cultivate", "Migration Path",
                "Topiary Stomper", "Fatal Push", "Go for the Throat", "The Meathook Massacre",
                "Nissa, Who Shakes the World", "Ugin, the Spirit Dragon", "Hydroid Krasis", "Storm the Festival",
                "Forest", "Swamp", "Tropical Island", "Underground Sea"}
                : new String[]{"Elvish Mystic", "Llanowar Elves", "Elvish Archdruid", "Elvish Warmaster",
                "Elvish Clancaller", "Collected Company", "Realmwalker", "Shaman of the Pack", "Forest", "Swamp", "Bayou"};
        int[] counts = ramp ? new int[]{4,4,4,4,4,4,4,4,2,2,1,1,10,4,4,4}
                : new int[]{4,4,4,4,4,4,4,4,20,4,4};
        for (int i = 0; i < names.length; i++) deck.getMain().add(names[i], counts[i]);
        need(deck.getMain().countAll() == 60, "Full original public registered60");
        return deck;
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
    private static Card in(Player player, ZoneType zone, int id) {
        return player.getCardsIn(zone).stream().filter(c -> c.getId() == id).findFirst().orElseThrow();
    }
    private static void resolve(Game game) {
        for (int i = 0; i < 40; i++) {
            need(!game.isGameOver(), "Unexpected terminal state in native control");
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        throw new IllegalStateException("HARNESS: native resolution exceeded fixed bound");
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) { stream.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Object> choice(SpellAbility sa) {
        if (sa == null) return Map.of("choice", "PASS");
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("source", sa.getHostCard().getName()); value.put("source_id", sa.getHostCard().getId());
        value.put("api", String.valueOf(sa.getApi())); value.put("is_spell", sa.isSpell());
        value.put("is_land", sa.isLandAbility()); value.put("X", sa.getXManaCostPaid());
        return value;
    }
    private static List<Map<String, Object>> creatures(Player player) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Card c : player.getCreaturesInPlay()) result.add(Map.of("id", c.getId(), "name", c.getName(),
                "power", c.getNetPower(), "toughness", c.getNetToughness(), "tapped", c.isTapped(), "sick", c.isSick()));
        return result;
    }
    private void check(int seat, String scene, Map<String, Object> row) throws Exception {
        boolean main1 = scene.equals("MAIN1_THREATENED");
        boolean hookOnly = scene.equals("MAIN2_MEATHOOK_ONLY");
        boolean friendly = scene.equals("MAIN2_FRIENDLY_GRAZERS");
        boolean threatened = main1 || hookOnly || scene.equals("MAIN2_THREATENED");
        boolean expectHook = !main1 && threatened;
        PhaseType phase = main1 ? PhaseType.MAIN1 : PhaseType.MAIN2;
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("case18-public-seat-" + index, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck(index == seat)).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-ETB-SWEEPER-PRIORITY10"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int n = 0; n < entry.getValue(); n++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getAllCards().size() == 60, "Exactly120 registered originals before any poses");
        }
        row.put("registered_original_totals", List.of(60, 60));
        game.getPhaseHandler().devModeSet(phase, actor, 8);
        game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>();
        row.put("native_events", events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("index", events.size() + 1); e.put("event", event.getClass().getSimpleName());
                e.put("phase", String.valueOf(game.getPhaseHandler().getPhase()));
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    e.put("source_id", cast.si().getSourceCard().getId());
                    e.put("source", cast.si().getSourceCard().getName());
                    e.put("targets", cast.targetDescription());
                    for (var item : game.getStack()) if (item.getId() == cast.si().getId()) {
                        e.put("actual_X_paid", item.getSpellAbility().getXManaCostPaid());
                        e.put("paid_mana", item.getSpellAbility().getPayingMana().stream().map(m -> Map.of(
                                "color", (int) m.getColor(), "source_id", m.getSourceCard() == null ? -1 : m.getSourceCard().getId())).toList());
                        break;
                    }
                }
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved
                        || event instanceof forge.game.event.GameEventLandPlayed) e.put("message", event.toString());
                events.add(e);
            }
        });
        List<Integer> manaIds = new ArrayList<>();
        manaIds.add(pose(actor, "Tropical Island").getId());
        manaIds.add(pose(actor, "Underground Sea").getId());
        manaIds.add(pose(actor, "Forest").getId()); manaIds.add(pose(actor, "Forest").getId());
        List<Integer> grazerIds = new ArrayList<>();
        if (friendly) {
            need(actor.getCardsIn(ZoneType.Hand).isEmpty(), "No hand lands before genuine Grazer ETBs");
            for (int i = 0; i < 4; i++) grazerIds.add(pose(actor, "Arboreal Grazer").getId());
            resolve(game);
            need(actor.getCardsIn(ZoneType.Hand).isEmpty() && actor.getLandsInPlay().size() == 4
                    && actor.getLandsPlayedThisTurn() == 0, "Grazer ETBs resolved with no extra entry land");
            row.put("after_Grazer_ETBs_before_hand_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        }
        Card nissa = null;
        if (!hookOnly) {
            hand(actor, "Growth Spiral"); nissa = hand(actor, "Nissa, Who Shakes the World"); hand(actor, "Cultivate");
        }
        Card meathook = hand(actor, "The Meathook Massacre");
        if (!hookOnly) { hand(actor, "Cultivate"); hand(actor, "Forest"); }
        Card fifthLand = hand(actor, "Underground Sea");
        // Real land action, not a counter edit or an ordinary AI choice.
        Card played = actor.playLand(fifthLand, null); manaIds.add(played.getId());
        List<Integer> enemyForests = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            Card forest = pose(enemy, "Forest"); forest.setTapped(true); enemyForests.add(forest.getId());
        }
        List<Card> elfPoses = new ArrayList<>();
        if (threatened) {
            elfPoses.add(pose(enemy, "Llanowar Elves")); elfPoses.add(pose(enemy, "Elvish Archdruid"));
            elfPoses.add(pose(enemy, "Llanowar Elves")); elfPoses.add(pose(enemy, "Elvish Clancaller"));
        }
        List<Integer> elfIds = elfPoses.stream().map(Card::getId).toList();
        // Only readiness/tap history is trusted; no power/toughness, Oracle or ability edits.
        for (Card c : elfPoses) c.setSickness(false);
        if (threatened) { elfPoses.get(0).setTapped(true); elfPoses.get(1).setTapped(true); }
        resolve(game);
        row.put("after_native_setup_actor_view_before_life_assignment", new ActorBoundary(actor).snapshot(game.getView()));
        int[] expected = {3,3,3,2};
        for (int i = 0; i < elfIds.size(); i++) {
            Card c = in(enemy, ZoneType.Battlefield, elfIds.get(i));
            need(c.getNetPower() == expected[i] && c.getNetToughness() == expected[i]
                    && c.isTapped() == (i < 2), "Native lord layers produce exact public Elf stats/taps");
        }
        actor.setLife(14, null); enemy.setLife(20, null);
        game.getAction().checkStateEffects(true);
        game.getPhaseHandler().setPriority(actor); actor.setHasPriority(true); enemy.setHasPriority(false);
        need(actor.getLandsPlayedThisTurn() == 1 && actor.getCardsIn(ZoneType.Hand).size() == (hookOnly ? 1 : 6)
                && actor.getCreaturesInPlay().size() == (friendly ? 4 : 0) && game.getStack().isEmpty()
                && actor.getManaPool().isEmpty() && !game.isGameOver(), "Exact settled public turn8 frontier");
        need(enemy.getCreaturesInPlay().size() == (threatened ? 4 : 0), "Declared enemy creature frontier");
        if (friendly) need(actor.getCreaturesInPlay().stream().allMatch(c -> grazerIds.contains(c.getId())
                && c.getNetPower() == 0 && c.getNetToughness() == 3), "Four real native0/3 Grazers");
        need(manaIds.stream().allMatch(id -> !in(actor, ZoneType.Battlefield, id).isTapped()), "Five real untapped lands");
        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        need(actor.getController().getClass() == PlayerControllerAi.class && !controller.getAi().usesSimulation(),
                "Ordinary Default with Monte Carlo off");
        row.put("mana_source_ids", manaIds); row.put("enemy_Elf_ids", elfIds); row.put("enemy_Forest_ids", enemyForests);
        int nissaId = nissa == null ? -1 : nissa.getId();
        row.put("meathook_id", meathook.getId()); row.put("nissa_id", nissaId); row.put("grazer_ids", grazerIds);
        row.put("phase", phase.name());
        row.put("expected_first_action", main1 ? "PASS" : expectHook ? "MEATHOOK_X3" : "NISSA");
        row.put("creatures_before", creatures(enemy));
        List<Map<String, Object>> ownBefore = creatures(actor), enemyBefore = creatures(enemy);
        row.put("own_creatures_before", ownBefore);
        row.put("before_first_root_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_before_root", rng());
        // No ability/API/affordability/forecast diagnostics precede this ordinary callback.
        List<SpellAbility> selected = controller.chooseSpellAbilityToPlay();
        SpellAbility chosen = selected == null || selected.isEmpty() ? null : selected.get(0);
        row.put("ordinary_root_callbacks", 1);
        row.put("returned_root_actions", selected == null ? List.of() : selected.stream().map(NativeEtbSweeperPriority10::choice).toList());
        row.put("first_choice", choice(chosen));
        row.put("rng_after_root", rng());
        row.put("after_first_root_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        need(game.getStack().isEmpty() && actor.getLife() == 14 && enemy.getLife() == 20
                && manaIds.stream().allMatch(id -> !in(actor, ZoneType.Battlefield, id).isTapped())
                && actor.getCardsIn(ZoneType.Hand).stream().anyMatch(c -> c.getId() == meathook.getId()),
                "Observed choice has not been played before selected-action execution");
        int chosenId = chosen == null ? -1 : chosen.getHostCard().getId();
        boolean choseHook = chosen != null && chosen.isSpell() && chosenId == meathook.getId();
        boolean choseNissa = chosen != null && chosen.isSpell() && chosenId == nissaId;
        boolean announcedX3 = choseHook && chosen.getXManaCostPaid() != null && chosen.getXManaCostPaid() == 3;
        boolean selectionMatches = main1 ? chosen == null : expectHook ? choseHook : choseNissa;
        row.put("selected_root_announced_X3", announcedX3);
        row.put("selection_matches_declared_priority", selectionMatches);
        row.put("before_selected_action_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        boolean paid = false;
        if (chosen != null) {
            if (chosen.isLandAbility()) {
                controller.playChosenSpellAbility(chosen);
                paid = actor.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == chosenId);
            } else paid = ComputerUtil.playStack(chosen, actor, game);
        }
        row.put("actual_selected_action_payment_succeeded", paid);
        row.put("manual_substitution", false); row.put("X_override", false);
        resolve(game);
        Map<String, Object> cast = events.stream().filter(e -> "GameEventSpellAbilityCast".equals(e.get("event"))
                && Integer.valueOf(chosenId).equals(e.get("source_id"))).findFirst().orElse(null);
        List<?> paidMana = cast == null ? List.of() : (List<?>) cast.getOrDefault("paid_mana", List.of());
        int black = (int) paidMana.stream().filter(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 4).count();
        int green = (int) paidMana.stream().filter(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 16).count();
        Set<Integer> paidSources = new HashSet<>();
        for (Object m : paidMana) paidSources.add(((Number) ((Map<?, ?>) m).get("source_id")).intValue());
        boolean exactFiveSources = paidSources.size() == 5 && paidSources.containsAll(manaIds);
        boolean actualX3 = cast != null && cast.get("actual_X_paid") instanceof Number
                && ((Number) cast.get("actual_X_paid")).intValue() == 3;
        boolean hookEntered = actor.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == meathook.getId());
        Card nissaOnBattlefield = actor.getCardsIn(ZoneType.Battlefield).stream()
                .filter(c -> c.getId() == nissaId).findFirst().orElse(null);
        int nissaLoyalty = nissaOnBattlefield == null ? -1 : nissaOnBattlefield.getCounters(forge.game.card.CounterEnumType.LOYALTY);
        long deaths = enemy.getCardsIn(ZoneType.Graveyard).stream().filter(c -> elfIds.contains(c.getId())).count();
        boolean landsRemain = manaIds.stream().allMatch(id -> actor.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == id));
        boolean allTapped = landsRemain && manaIds.stream().allMatch(id -> in(actor, ZoneType.Battlefield, id).isTapped());
        boolean ownBoardPreserved = ownBefore.equals(creatures(actor));
        boolean enemyBoardPreserved = enemyBefore.equals(creatures(enemy));
        boolean noOwnLoss = actor.getCardsIn(ZoneType.Graveyard).isEmpty() && ownBoardPreserved && landsRemain;
        boolean forestsRemain = enemyForests.stream().allMatch(id -> enemy.getCardsIn(ZoneType.Battlefield).stream().anyMatch(c -> c.getId() == id));
        row.put("actual_selected_cast_event", cast); row.put("actual_mana_paid_count", paidMana.size()); row.put("actual_black_paid_count", black);
        row.put("actual_green_paid_count", green); row.put("nissa_entered", nissaOnBattlefield != null); row.put("nissa_loyalty", nissaLoyalty);
        row.put("actual_five_declared_mana_sources_paid", exactFiveSources);
        row.put("actual_X3_paid", actualX3); row.put("native_meathook_entered", hookEntered);
        row.put("actual_original_Elf_deaths", deaths); row.put("actual_no_own_loss", noOwnLoss);
        row.put("own_board_preserved", ownBoardPreserved); row.put("enemy_board_preserved", enemyBoardPreserved);
        row.put("enemy_forests_preserved", forestsRemain); row.put("own_original_Grazer_deaths",
                actor.getCardsIn(ZoneType.Graveyard).stream().filter(c -> grazerIds.contains(c.getId())).count());
        row.put("all_five_lands_tapped", allTapped); row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("owned_native_card_totals_after", List.of(actor.getAllCards().size(), enemy.getAllCards().size()));
        row.put("creatures_after", creatures(enemy));
        row.put("own_creatures_after", creatures(actor));
        row.put("after_selected_action_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_after_selected_action", rng()); row.put("native_game_over", game.isGameOver());
        boolean hookOutcome = choseHook && paid && actualX3 && paidMana.size() == 5 && black >= 2 && exactFiveSources && hookEntered && deaths == 4
                && enemy.getCreaturesInPlay().isEmpty() && noOwnLoss && allTapped && actor.getLife() == 18
                && enemy.getLife() == 20 && forestsRemain;
        boolean nissaOutcome = choseNissa && paid && paidMana.size() == 5 && green >= 2 && exactFiveSources
                && nissaOnBattlefield != null && nissaLoyalty == 5 && noOwnLoss && enemyBoardPreserved
                && allTapped && actor.getLife() == 14 && enemy.getLife() == 20 && forestsRemain;
        boolean passOutcome = chosen == null && !paid && noOwnLoss && enemyBoardPreserved
                && manaIds.stream().allMatch(id -> !in(actor, ZoneType.Battlefield, id).isTapped())
                && actor.getLife() == 14 && enemy.getLife() == 20 && forestsRemain;
        boolean expectedOutcome = main1 ? passOutcome : expectHook ? hookOutcome : nissaOutcome;
        boolean ok = selectionMatches && expectedOutcome && game.getStack().isEmpty() && !game.isGameOver();
        List<String> failures = new ArrayList<>();
        if (!selectionMatches) failures.add("FIRST_ORDINARY_CHOICE_MISMATCH");
        if (chosen != null && !paid) failures.add("ACTUAL_SELECTED_ACTION_NOT_PAID");
        if (!expectedOutcome) failures.add("DECLARED_ACTION_OUTCOME_NOT_OBSERVED_NOT_AN_ENGINE_VERDICT");
        if (!game.getStack().isEmpty() || game.isGameOver()) failures.add("UNEXPECTED_STACK_OR_TERMINAL_STATE");
        row.put("actual_selected_Meathook_full_wipe", hookOutcome); row.put("actual_selected_Nissa_native_outcome", nissaOutcome);
        row.put("expected_action_outcome_observed", expectedOutcome); row.put("failures", failures);
        row.put("policy_red", !ok); row.put("status", ok ? "PASS" : "POLICY_RED");
        row.put("native_outcome_from_actual_selected_action_only", true); row.put("query_purity_claim", false);
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh report-directory argument");
        Path out = Path.of(args[0]); Files.createDirectories(out);
        need(!Files.exists(out.resolve("summary.private.json")), "Once-only report directory");
        MyRandom.setRandom(new Random(SEED));
        NativeEtbSweeperPriority10 probe = new NativeEtbSweeperPriority10(); probe.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int passed = 0, red = 0, errors = 0;
        for (String scene : List.of("MAIN2_THREATENED", "MAIN2_MEATHOOK_ONLY", "MAIN2_EMPTY",
                "MAIN2_FRIENDLY_GRAZERS", "MAIN1_THREATENED")) for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("scene", scene); row.put("seat", seat); row.put("seed", SEED);
            try {
                probe.check(seat, scene, row);
                if (row.get("status").equals("PASS")) passed++; else red++;
            } catch (Throwable error) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error", error.toString()); error.printStackTrace();
            }
            Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW);
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status"))));
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total", 10); summary.put("passed", passed); summary.put("policy_red", red); summary.put("harness_errors", errors);
        summary.put("seed", SEED); summary.put("seed_installations", 1); summary.put("natural_games", 0);
        summary.put("manual_substitutions", 0); summary.put("extra_root_callbacks", 0);
        summary.put("scope", "DECLARED_PRIORITY_CONSISTENCY_NOT_UNIVERSAL_BEST_STRATEGY");
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary));
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
