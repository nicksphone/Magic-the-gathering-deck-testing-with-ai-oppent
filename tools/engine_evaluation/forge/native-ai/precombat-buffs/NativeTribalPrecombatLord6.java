// SPDX-License-Identifier: GPL-3.0-or-later
// TRUSTED READY-ELF POSES, NOT NATURAL GAMES OR AN EXPERT CERTIFICATE.
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

public final class NativeTribalPrecombatLord6 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110730L;

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
    private void check(int seat, String scene, Map<String, Object> row) throws Exception {
        boolean ready = !scene.equals("NO_BENEFICIARY_FUNDED");
        boolean funded = !scene.equals("READY_UNFUNDED");
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck("trusted-tribal-lord-seat-" + i);
            if (i == seat) {
                deck.getMain().add("Elvish Clancaller", 1);
                deck.getMain().add("Elvish Visionary", 2);
                deck.getMain().add("Forest", 57);
            } else deck.getMain().add("Forest", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("trusted-tribal-lord-seat-" + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-TRIBAL-PRECOMBAT-LORD6"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player p : game.getPlayers()) {
            for (var entry : p.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), p, ZoneType.Library);
            need(p.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && p.getAllCards().size() == 60,
                    "Complete registered60 originals, no extra fixture cards");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor);
        game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>();
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("index", events.size() + 1); e.put("event", event.getClass().getSimpleName());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved
                        || event instanceof forge.game.event.GameEventLandPlayed) e.put("message", event.toString());
                events.add(e);
            }
        });
        Card lord = game.getAction().moveToHand(library(actor, "Elvish Clancaller"), null);
        int lordId = lord.getId();
        List<Integer> beneficiaries = new ArrayList<>();
        if (ready) {
            beneficiaries.add(pose(actor, "Elvish Visionary").getId());
            beneficiaries.add(pose(actor, "Elvish Visionary").getId());
        }
        // All nonland originals have left this library before the two real draw triggers resolve.
        resolve(game);
        need(actor.getCardsIn(ZoneType.Hand).size() == (ready ? 3 : 1)
                && actor.getCardsIn(ZoneType.Hand).stream().filter(c -> c.getName().equals("Forest")).count() == (ready ? 2 : 0),
                "Full Visionary ETBs really drew exactly two Forests; no discarded/hidden setup cards");
        Card setupLand = ready ? actor.getCardsIn(ZoneType.Hand).stream().filter(c -> c.getName().equals("Forest")).findFirst().orElseThrow()
                : game.getAction().moveToHand(library(actor, "Forest"), null);
        actor.playLand(setupLand, null);
        if (funded) pose(actor, "Forest");
        resolve(game);
        // Established ready creatures are an explicit trusted-pose assumption, not simulated history.
        for (int id : beneficiaries) current(actor, id).setSickness(false);
        for (int id : beneficiaries) {
            Card c = current(actor, id);
            need(!c.isSick() && !c.isTapped() && c.getNetPower() == 1 && c.getNetToughness() == 1,
                    "Exactly two established ready1/1 beneficiaries before the first chooser");
        }
        actor.setLife(20, null); enemy.setLife(20, null);
        game.getAction().checkStateEffects(true);
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
        need(actor.getLandsPlayedThisTurn() == 1 && game.getStack().isEmpty()
                && enemy.getCardsIn(ZoneType.Battlefield).isEmpty() && enemy.getCardsIn(ZoneType.Hand).isEmpty()
                && actor.getCardsIn(ZoneType.Hand).size() == (ready ? 2 : 1), "Land allowance consumed by actual setup play");
        need(actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest") && !c.isTapped()).count() == (funded ? 2 : 1),
                "Only ordinary Forest mana; Visionaries have no mana ability");
        row.put("registered_main_totals", List.of(60, 60));
        row.put("trusted_ready_established_not_natural", true);
        row.put("genuine_visionary_draw_count", ready ? 2 : 0);
        row.put("setup_actual_land_plays", actor.getLandsPlayedThisTurn());
        row.put("extra_drawn_Forests_in_hand", ready ? 1 : 0);
        row.put("beneficiary_ids", beneficiaries);
        row.put("lord_id", lordId);
        row.put("beneficiaries_before", stats(actor, beneficiaries));
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        // First policy query: no affordability/API/target/forecast diagnostics before this call.
        List<SpellAbility> options = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility selected = options == null || options.isEmpty() ? null : options.get(0);
        row.put("ordinary_initial_callbacks", 1);
        row.put("first_choice", choice(selected));
        row.put("returned_choice_count", options == null ? 0 : options.size());
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default, MC off");
        need(selected == null || selected.isSpell() && selected.getHostCard().getId() == lordId,
                "Unexpected selected action is a harness review, never a refusal-negative PASS");
        boolean aiSelected = selected != null;
        SpellAbility actual = selected;
        if (actual == null) {
            actual = lord.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
            actual.setActivatingPlayer(actor);
        }
        boolean paid = ComputerUtil.playStack(actual, actor, game);
        row.put("AI_selected_lord", aiSelected);
        row.put("manual_rules_control_not_AI_success", !aiSelected);
        row.put("native_GG_payment_succeeded", paid);
        resolve(game);
        need(!game.isGameOver() && game.getStack().isEmpty() && actor.getLife() == 20 && enemy.getLife() == 20,
                "No forced game winner or life change");
        if (funded) {
            need(paid && current(actor, lordId).getName().equals("Elvish Clancaller"), "Actual full native GG payment and resolution");
            need(actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest")).allMatch(Card::isTapped),
                    "Both real Forests actually paid GG, no waived cost");
            for (int id : beneficiaries) need(current(actor, id).getNetPower() == 2 && current(actor, id).getNetToughness() == 2,
                    "Full native lord actually buffs both existing Visionaries +1/+1");
        } else {
            need(!paid && actor.getCardsIn(ZoneType.Hand).stream().anyMatch(c -> c.getId() == lordId), "One Forest cannot pay GG");
            for (int id : beneficiaries) need(current(actor, id).getNetPower() == 1 && current(actor, id).getNetToughness() == 1,
                    "Unfunded beneficiary stats unchanged");
        }
        need(actor.getAllCards().size() == 60 && enemy.getAllCards().size() == 60, "All120 originals retained across native zones");
        row.put("beneficiaries_after", stats(actor, beneficiaries));
        row.put("after_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("native_game_over", game.isGameOver());
        row.put("native_events", events);
        boolean red = ready && (funded ? !aiSelected : aiSelected);
        row.put("policy_red", red);
        row.put("AI_funded_ready_buff", ready && funded && aiSelected && paid);
        row.put("unfunded_ordinary_decline", ready && !funded && !aiSelected);
        row.put("observational_no_beneficiary", !ready);
        row.put("status", !ready ? "OBSERVATIONAL" : red ? "POLICY_RED" : "PASS");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private output directory argument");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED)); // Exactly once before model/game construction.
        NativeTribalPrecombatLord6 probe = new NativeTribalPrecombatLord6();
        probe.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int errors = 0, red = 0, successes = 0, declines = 0, observations = 0, controls = 0;
        for (String scene : List.of("READY_FUNDED", "READY_UNFUNDED", "NO_BENEFICIARY_FUNDED")) {
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("scene", scene); row.put("seat", seat); row.put("seed", SEED);
                try {
                    probe.check(seat, scene, row);
                    if (Boolean.TRUE.equals(row.get("policy_red"))) red++;
                    if (Boolean.TRUE.equals(row.get("AI_funded_ready_buff"))) successes++;
                    if (Boolean.TRUE.equals(row.get("unfunded_ordinary_decline"))) declines++;
                    if (Boolean.TRUE.equals(row.get("observational_no_beneficiary"))) observations++;
                    if (scene.equals("READY_FUNDED") && Boolean.TRUE.equals(row.get("manual_rules_control_not_AI_success"))) controls++;
                } catch (Throwable e) {
                    errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", e.getClass().getName());
                    row.put("error", String.valueOf(e.getMessage())); e.printStackTrace(System.err);
                }
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW);
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status"))));
                System.out.flush();
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "TRUSTED-PRECOMBAT-LORD6; NOT NATURAL OR EXPERT CERTIFICATE");
        summary.put("total", 6); summary.put("policy_red", red); summary.put("harness_errors", errors);
        summary.put("AI_funded_ready_buffs", successes); summary.put("funded_ready_manual_controls", controls);
        summary.put("unfunded_declines", declines); summary.put("no_beneficiary_observations", observations);
        summary.put("seed", SEED); summary.put("seed_installations", 1); summary.put("natural_games", 0);
        summary.put("manual_control_is_not_AI_success", true);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary));
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
