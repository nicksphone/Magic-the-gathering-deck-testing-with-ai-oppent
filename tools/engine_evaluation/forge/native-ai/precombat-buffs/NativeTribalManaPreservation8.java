// SPDX-License-Identifier: GPL-3.0-or-later
// TRUSTED READY-MANA-ELF POSES, NOT NATURAL GAMES OR AN EXPERT CERTIFICATE.
// Adapted from NativeDrainTactics8 and NativeSkullcrackResponse6 helpers.
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeTribalManaPreservation8 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110732L;

    private static void need(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true);
        return card;
    }
    private static Card library(Player p, String name) {
        return p.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
    }
    private static Card pose(Player p, String name) {
        return p.getGame().getAction().moveToPlay(library(p, name), p, null, AbilityKey.newMap());
    }
    private static void resolve(Game game) {
        for (int i = 0; i < 20; i++) {
            need(!game.isGameOver(), "Nonterminal trusted setup/control");
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        need(false, "Bounded native stack resolution");
    }
    private static Card current(Player p, int id) {
        return p.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getId() == id).findFirst().orElseThrow();
    }
    private static Map<String, Object> choice(SpellAbility sa) {
        return sa == null ? Map.of("choice", "PASS") : Map.of("source", sa.getHostCard().getName(),
                "source_id", sa.getHostCard().getId(), "ability_id", sa.getId(),
                "api", String.valueOf(sa.getApi()), "is_spell", sa.isSpell());
    }
    private static List<Map<String, Object>> stats(Player p, List<Integer> ids) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (int id : ids) {
            Card c = current(p, id);
            result.add(Map.of("card_id", id, "power", c.getNetPower(), "toughness", c.getNetToughness(),
                    "sick", c.isSick(), "tapped", c.isTapped()));
        }
        return result;
    }
    private void check(int seat, String scene, String lordName, Map<String, Object> row) throws Exception {
        boolean landFunded = scene.equals("READY_MANA_ELVES_FUNDED");
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck("trusted-mana-elves-seat-" + i);
            if (i == seat) {
                deck.getMain().add(lordName, 1);
                deck.getMain().add("Llanowar Elves", 1);
                deck.getMain().add("Elvish Archdruid", 1);
                deck.getMain().add("Forest", 57);
            } else deck.getMain().add("Forest", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("trusted-mana-elves-seat-" + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-LORD-MANA-PRESERVATION8"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player p : game.getPlayers()) {
            for (var entry : p.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), p, ZoneType.Library);
            need(p.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && p.getAllCards().size() == 60,
                    "Exactly sixty registered originals per seat");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor);
        game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>();
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("index", events.size() + 1); e.put("event", event.getClass().getSimpleName());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    e.put("source_id", cast.si().getSourceCard().getId());
                    e.put("source_name", cast.si().getSourceCard().getCurrentState().getName());
                    e.put("is_spell", cast.sa().isSpell());
                    e.put("paid_mana_observed", false);
                    for (var item : game.getStack()) {
                        if (item.getId() == cast.si().getId()) {
                            e.put("paid_mana_observed", true);
                            e.put("paid_mana", item.getSpellAbility().getPayingMana().stream().map(m -> Map.of(
                                    "color", (int) m.getColor(), "source_id", m.getSourceCard() == null ? -1 : m.getSourceCard().getId())).toList());
                            break;
                        }
                    }
                }
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved
                        || event instanceof forge.game.event.GameEventLandPlayed) e.put("message", event.toString());
                events.add(e);
            }
        });
        Card lord = game.getAction().moveToHand(library(actor, lordName), null);
        int lordId = lord.getId();
        List<Integer> elves = List.of(pose(actor, "Llanowar Elves").getId(), pose(actor, "Elvish Archdruid").getId());
        Card setupLand = game.getAction().moveToHand(library(actor, "Forest"), null);
        actor.playLand(setupLand, null);
        if (landFunded) { pose(actor, "Forest"); pose(actor, "Forest"); }
        resolve(game);
        // Explicit established-ready trusted state, not a claimed simulated prior turn.
        for (int id : elves) current(actor, id).setSickness(false);
        actor.setLife(20, null); enemy.setLife(20, null);
        game.getAction().checkStateEffects(true);
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
        Set<Integer> forests = new HashSet<>();
        for (Card c : actor.getCardsIn(ZoneType.Battlefield)) if (c.getName().equals("Forest")) forests.add(c.getId());
        need(forests.size() == (landFunded ? 3 : 1) && actor.getCardsIn(ZoneType.Battlefield).size() == forests.size() + 2
                && actor.getCardsIn(ZoneType.Battlefield).stream().noneMatch(Card::isTapped)
                && actor.getCardsIn(ZoneType.Hand).size() == 1 && actor.getCardsIn(ZoneType.Hand).get(0).getId() == lordId
                && actor.getLandsPlayedThisTurn() == 1 && enemy.getCardsIn(ZoneType.Battlefield).isEmpty()
                && enemy.getCardsIn(ZoneType.Hand).isEmpty() && game.getStack().isEmpty(), "Exact trusted hand/mana/land allowance frontier");
        for (int id : elves) {
            Card c = current(actor, id);
            need(!c.isSick() && !c.isTapped() && c.getNetPower() == 2 && c.getNetToughness() == 2,
                    "Actual Archdruid static establishes both ready Elves2/2");
        }
        row.put("registered_main_totals", List.of(60, 60));
        row.put("trusted_ready_established_not_natural", true);
        row.put("land_only_funding_declared", landFunded);
        row.put("unfunded_means_noncreature_witness_not_total_unaffordability", !landFunded);
        row.put("forest_ids", new TreeSet<>(forests)); row.put("beneficiary_ids", elves); row.put("lord_id", lordId);
        row.put("setup_actual_land_plays", actor.getLandsPlayedThisTurn());
        row.put("beneficiaries_before", stats(actor, elves));
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        // First policy call; no helper reflection, API/affordability/forecast/target queries precede it.
        List<SpellAbility> options = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility selected = options == null || options.isEmpty() ? null : options.get(0);
        row.put("ordinary_initial_callbacks", 1); row.put("first_choice", choice(selected));
        row.put("returned_choice_count", options == null ? 0 : options.size());
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default heuristic, MC off");
        need(selected == null || selected.isSpell() && selected.getHostCard().getId() == lordId,
                "Unexpected action requires harness review, never counted as ordinary decline");
        boolean aiSelected = selected != null;
        SpellAbility actual = selected;
        if (actual == null) {
            actual = lord.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
            actual.setActivatingPlayer(actor);
        }
        boolean paid = ComputerUtil.playStack(actual, actor, game);
        row.put("AI_selected_lord", aiSelected); row.put("manual_rules_control_not_AI_success", !aiSelected);
        row.put("native_GG_payment_succeeded", paid);
        resolve(game);
        need(paid && current(actor, lordId).getName().equals(lordName), "Real native GG cast resolves, no waived costs");
        Map<String, Object> paidEvent = events.stream().filter(e -> Boolean.TRUE.equals(e.get("is_spell"))
                && Integer.valueOf(lordId).equals(e.get("source_id"))).findFirst().orElseThrow();
        need(Boolean.TRUE.equals(paidEvent.get("paid_mana_observed")), "Actual public cast paying-mana observation required");
        @SuppressWarnings("unchecked")
        List<Map<String, Integer>> mana = (List<Map<String, Integer>>) paidEvent.get("paid_mana");
        need(mana.size() == 2 && mana.stream().allMatch(m -> m.get("color") == 16), "Actual two green mana units paid");
        boolean twoForests = mana.stream().allMatch(m -> forests.contains(m.get("source_id")))
                && mana.stream().map(m -> m.get("source_id")).distinct().count() == 2;
        long tappedForests = forests.stream().filter(id -> current(actor, id).isTapped()).count();
        boolean elvesUntapped = elves.stream().noneMatch(id -> current(actor, id).isTapped());
        for (int id : elves) need(current(actor, id).getNetPower() == 3 && current(actor, id).getNetToughness() == 3,
                "Full canonical lord actually buffs both native Elves2/2 to3/3");
        need(!game.isGameOver() && actor.getLife() == 20 && enemy.getLife() == 20 && game.getStack().isEmpty()
                && actor.getAllCards().size() == 60 && enemy.getAllCards().size() == 60, "Nonterminal full120 originals, no forced outcome");
        if (!landFunded) need(!elvesUntapped && mana.stream().anyMatch(m -> elves.contains(m.get("source_id"))),
                "One-Forest rules control really uses creature mana; not an unaffordable fixture");
        boolean preserved = twoForests && tappedForests == 2 && elvesUntapped;
        boolean red = landFunded ? !aiSelected || !preserved : aiSelected;
        row.put("actual_paid_mana", mana); row.put("paid_two_distinct_Forests", twoForests);
        row.put("tapped_Forest_count", tappedForests); row.put("both_ready_Elves_untapped_after_payment", elvesUntapped);
        row.put("funded_native_mana_preservation", landFunded && preserved);
        row.put("AI_funded_mana_preservation", landFunded && aiSelected && preserved);
        row.put("ordinary_decline_without_noncreature_funding", !landFunded && !aiSelected);
        row.put("manual_native_control_proves_creature_funding", !landFunded && !aiSelected);
        row.put("beneficiaries_after", stats(actor, elves)); row.put("native_game_over", game.isGameOver());
        row.put("after_actor_view", new ActorBoundary(actor).snapshot(game.getView())); row.put("native_events", events);
        row.put("policy_red", red); row.put("status", red ? "POLICY_RED" : "PASS");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private output directory argument");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED)); // Exactly once before model/game construction.
        NativeTribalManaPreservation8 probe = new NativeTribalManaPreservation8(); probe.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int errors = 0, red = 0, preserved = 0, declined = 0;
        for (String lordName : List.of("Elvish Clancaller", "Leaf-Crowned Visionary")) {
            String lordKey = lordName.equals("Elvish Clancaller") ? "CLANCALLER" : "LEAF_CROWNED";
            for (String scene : List.of("READY_MANA_ELVES_FUNDED", "READY_MANA_ELVES_UNFUNDED")) {
                for (int seat = 0; seat < 2; seat++) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("lord_name", lordName); row.put("lord_key", lordKey);
                    row.put("scene", scene); row.put("seat", seat); row.put("seed", SEED);
                    try {
                        probe.check(seat, scene, lordName, row);
                        if (Boolean.TRUE.equals(row.get("policy_red"))) red++;
                        if (Boolean.TRUE.equals(row.get("AI_funded_mana_preservation"))) preserved++;
                        if (Boolean.TRUE.equals(row.get("ordinary_decline_without_noncreature_funding"))) declined++;
                    } catch (Throwable e) {
                        errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", e.getClass().getName());
                        row.put("error", String.valueOf(e.getMessage())); e.printStackTrace(System.err);
                    }
                    Files.writeString(out.resolve(lordKey + "-" + scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW);
                    System.out.println(JSON.toJson(Map.of("lord_key", lordKey, "scene", scene, "seat", seat, "status", row.get("status"))));
                    System.out.flush();
                }
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "TRUSTED-MANA-PRESERVATION8; NOT NATURAL OR EXPERT CERTIFICATE");
        summary.put("total", 8); summary.put("policy_red", red); summary.put("harness_errors", errors);
        summary.put("AI_funded_mana_preservations", preserved); summary.put("ordinary_declines_without_noncreature_funding", declined);
        summary.put("seed", SEED); summary.put("seed_installations", 1); summary.put("natural_games", 0);
        summary.put("manual_control_is_not_AI_success", true);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
