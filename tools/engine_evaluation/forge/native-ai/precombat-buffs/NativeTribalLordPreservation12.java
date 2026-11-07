// SPDX-License-Identifier: GPL-3.0-or-later
// TRUSTED LORD CONTROLS, NOT NATURAL GAMES OR AN EXPERT CERTIFICATE.
// Derived from frozen c77733... Lord6; negative ordinary choices stay observational.
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

public final class NativeTribalLordPreservation12 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110731L;

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
        boolean main2 = scene.equals("MAIN2_FUNDED_READY");
        boolean opponentOnly = scene.equals("OPPONENT_ONLY_ELVES");
        boolean nonElf = scene.equals("OWN_NON_ELVES");
        boolean humility = scene.equals("HUMILITY_SUPPRESSED");
        boolean tapped = scene.equals("TAPPED_BENEFICIARIES");
        boolean sick = scene.equals("SICK_BENEFICIARIES");
        boolean ownElves = !opponentOnly && !nonElf;
        String beneficiaryName = nonElf ? "Grizzly Bears" : "Elvish Visionary";
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck("trusted-tribal-lord-seat-" + i);
            if (i == seat) {
                deck.getMain().add("Elvish Clancaller", 1);
                if (!opponentOnly) deck.getMain().add(beneficiaryName, 2);
                deck.getMain().add("Forest", opponentOnly ? 59 : 57);
            } else if (opponentOnly) {
                deck.getMain().add("Elvish Visionary", 2);
                deck.getMain().add("Forest", 58);
            } else if (humility) {
                deck.getMain().add("Humility", 1);
                deck.getMain().add("Forest", 59);
            } else deck.getMain().add("Forest", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("trusted-tribal-lord-seat-" + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-LORD-PRESERVATION12"));
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
        game.getPhaseHandler().devModeSet(main2 ? PhaseType.MAIN2 : PhaseType.MAIN1, actor);
        game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>();
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("index", events.size() + 1); e.put("event", event.getClass().getSimpleName());
                e.put("phase", String.valueOf(game.getPhaseHandler().getPhase()));
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    e.put("source_id", cast.si().getSourceCard().getId());
                    for (var item : game.getStack()) if (item.getId() == cast.si().getId()) {
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
        Card lord = game.getAction().moveToHand(library(actor, "Elvish Clancaller"), null);
        int lordId = lord.getId();
        Player beneficiaryOwner = opponentOnly ? enemy : actor;
        List<Integer> beneficiaries = new ArrayList<>();
        beneficiaries.add(pose(beneficiaryOwner, beneficiaryName).getId());
        beneficiaries.add(pose(beneficiaryOwner, beneficiaryName).getId());
        row.put("native_events", events);
        // Humility is posed only after the genuine Visionary entry triggers resolve.
        resolve(game);
        int ownDraws = ownElves ? 2 : 0;
        need(actor.getCardsIn(ZoneType.Hand).size() == 1 + ownDraws
                && actor.getCardsIn(ZoneType.Hand).stream().filter(c -> c.getName().equals("Forest")).count() == ownDraws
                && enemy.getCardsIn(ZoneType.Hand).size() == (opponentOnly ? 2 : 0),
                "Native draw outcomes preserved; opponent hand identities never inspected");
        row.put("after_genuine_ETB_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        Card setupLand = ownDraws > 0 ? actor.getCardsIn(ZoneType.Hand).stream().filter(c -> c.getName().equals("Forest")).findFirst().orElseThrow()
                : game.getAction().moveToHand(library(actor, "Forest"), null);
        actor.playLand(setupLand, null);
        pose(actor, "Forest");
        if (humility) pose(enemy, "Humility");
        resolve(game);
        // Historical readiness/tap states are declared poses, not paid-cast qualifications.
        for (int id : beneficiaries) {
            current(beneficiaryOwner, id).setSickness(sick);
            current(beneficiaryOwner, id).setTapped(tapped);
        }
        for (int id : beneficiaries) {
            Card c = current(beneficiaryOwner, id);
            need(c.isSick() == sick && c.isTapped() == tapped
                    && c.getNetPower() == (nonElf ? 2 : 1) && c.getNetToughness() == (nonElf ? 2 : 1),
                    "Exactly declared native beneficiary type/stats/readiness before chooser");
        }
        actor.setLife(20, null); enemy.setLife(20, null);
        game.getAction().checkStateEffects(true);
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
        need(actor.getLandsPlayedThisTurn() == 1 && game.getStack().isEmpty()
                && actor.getCardsIn(ZoneType.Hand).size() == 1 + Math.max(0, ownDraws - 1),
                "Land allowance consumed by actual setup play");
        need(actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest") && !c.isTapped()).count() == 2,
                "Only ordinary Forest mana; Visionaries have no mana ability");
        row.put("registered_main_totals", List.of(60, 60));
        row.put("trusted_states_not_natural_or_paid_creature_casts", true);
        row.put("trusted_Humility_pose_not_paid_cast", humility);
        row.put("genuine_own_visionary_draw_count", ownDraws);
        row.put("genuine_opponent_draw_count_only", opponentOnly ? 2 : 0);
        row.put("setup_actual_land_plays", actor.getLandsPlayedThisTurn());
        row.put("extra_drawn_Forests_in_hand", Math.max(0, ownDraws - 1));
        row.put("beneficiary_owner_seat", opponentOnly ? 1 - seat : seat);
        row.put("beneficiary_ids", beneficiaries);
        row.put("lord_id", lordId);
        row.put("beneficiaries_before", stats(beneficiaryOwner, beneficiaries));
        row.put("ordinary_choice_judged", main2);
        row.put("phase", String.valueOf(game.getPhaseHandler().getPhase()));
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
        need(paid && current(actor, lordId).getName().equals("Elvish Clancaller"), "Actual full native GG payment and resolution");
        need(actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest")).allMatch(Card::isTapped),
                "Both real Forests actually paid GG, no waived cost");
        List<?> mana = (List<?>) events.stream().filter(e -> Integer.valueOf(lordId).equals(e.get("source_id")))
                .findFirst().orElseThrow().get("paid_mana");
        need(mana != null && mana.size() == 2
                && mana.stream().allMatch(m -> ((Number) ((Map<?, ?>) m).get("color")).intValue() == 16),
                "Actual stack instance records two real G payments");
        row.put("actual_GG_mana", mana);
        boolean receivesBuff = ownElves && !humility;
        int afterStat = nonElf || receivesBuff ? 2 : 1;
        for (int id : beneficiaries) {
            Card c = current(beneficiaryOwner, id);
            need(c.getNetPower() == afterStat && c.getNetToughness() == afterStat
                    && c.isSick() == sick && c.isTapped() == tapped,
                    "Native own-Elf buff or suppression/foreign/non-Elf non-buff, with readiness preserved");
        }
        need(actor.getAllCards().size() == 60 && enemy.getAllCards().size() == 60, "All120 originals retained across native zones");
        row.put("beneficiaries_after", stats(beneficiaryOwner, beneficiaries));
        row.put("after_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("native_game_over", game.isGameOver());
        row.put("native_events", events);
        boolean red = main2 && !aiSelected;
        row.put("policy_red", red);
        row.put("AI_MAIN2_funded_ready_buff", main2 && aiSelected && paid);
        row.put("observational_non_MAIN2", !main2);
        row.put("native_buff_received", receivesBuff);
        row.put("negative_is_not_blanket_PASS_requirement", !main2);
        row.put("status", !main2 ? "OBSERVATIONAL" : red ? "POLICY_RED" : "PASS");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private output directory argument");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED)); // Exactly once before model/game construction.
        NativeTribalLordPreservation12 probe = new NativeTribalLordPreservation12();
        probe.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int errors = 0, red = 0, successes = 0, observations = 0, controls = 0;
        for (String scene : List.of("MAIN2_FUNDED_READY", "HUMILITY_SUPPRESSED", "TAPPED_BENEFICIARIES",
                "SICK_BENEFICIARIES", "OPPONENT_ONLY_ELVES", "OWN_NON_ELVES")) {
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("scene", scene); row.put("seat", seat); row.put("seed", SEED);
                try {
                    probe.check(seat, scene, row);
                    if (Boolean.TRUE.equals(row.get("policy_red"))) red++;
                    if (Boolean.TRUE.equals(row.get("AI_MAIN2_funded_ready_buff"))) successes++;
                    if (Boolean.TRUE.equals(row.get("observational_non_MAIN2"))) observations++;
                    if (scene.equals("MAIN2_FUNDED_READY") && Boolean.TRUE.equals(row.get("manual_rules_control_not_AI_success"))) controls++;
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
        summary.put("label", "TRUSTED-LORD-PRESERVATION12; ONLY MAIN2 IS POLICY-JUDGED");
        summary.put("total", 12); summary.put("policy_red", red); summary.put("harness_errors", errors);
        summary.put("AI_MAIN2_funded_ready_buffs", successes); summary.put("MAIN2_manual_controls", controls);
        summary.put("non_MAIN2_observations", observations);
        summary.put("seed", SEED); summary.put("seed_installations", 1); summary.put("natural_games", 0);
        summary.put("manual_control_is_not_AI_success", true);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary));
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
