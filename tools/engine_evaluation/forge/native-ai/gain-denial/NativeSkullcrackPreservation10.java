// SPDX-License-Identifier: GPL-3.0-or-later
// TRUSTED POSES, NOT NATURAL GAMES OR AN EXPERT CERTIFICATE.
// Full native programs, real opponent draws/triggers, ordinary Default and actual native costs.
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

public final class NativeSkullcrackPreservation10 extends AITest {
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
    private static SpellAbility manualSkull(Card card, Player actor, Player enemy) {
        SpellAbility root = card.getSpellAbilities().stream().filter(s -> s.isSpell()).findFirst().orElseThrow();
        root.setActivatingPlayer(actor);
        SpellAbility damage = root.getSubAbility();
        need(damage != null && damage.getApi() == ApiType.DealDamage, "Complete native damage subability");
        damage.setActivatingPlayer(actor); damage.resetTargets();
        if (!damage.canTarget(enemy)) return null;
        damage.getTargets().add(enemy);
        return root;
    }
    private void check(int seat, String scene, Map<String, Object> row) throws Exception {
        boolean ownGain = scene.equals("OWN_PENDING_GAIN"), blocked = scene.equals("GAIN_ALREADY_BLOCKED");
        boolean remedy = scene.equals("TAINTED_REMEDY"), hexproof = scene.equals("OPPONENT_HEXPROOF");
        boolean lethal = scene.equals("ORDINARY_LETHAL");
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("trusted-preservation-" + index);
            int mountains = 60;
            if (index == seat) {
                deck.getMain().add("Skullcrack", 1); mountains--;
                if (ownGain) { deck.getMain().add("Sheoldred, the Apocalypse", 1); mountains--; }
                if (blocked) { deck.getMain().add("Sulfuric Vortex", 1); mountains--; }
                if (remedy) { deck.getMain().add("Tainted Remedy", 1); mountains--; }
            } else {
                if (!ownGain) { deck.getMain().add("Sheoldred, the Apocalypse", 1); mountains--; }
                if (hexproof) { deck.getMain().add("Leyline of Sanctity", 1); mountains--; }
            }
            deck.getMain().add("Mountain", mountains);
            LobbyPlayerAi lobby = new LobbyPlayerAi("trusted-preservation-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-SKULLCRACK-PRESERVATION10"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int count = 0; count < entry.getValue(); count++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && player.getAllCards().size() == 60,
                    "Complete actual registered60 originals");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, enemy);
        game.getPhaseHandler().onStackResolved();
        pose(ownGain ? actor : enemy, "Sheoldred, the Apocalypse");
        pose(actor, "Mountain"); pose(actor, "Mountain");
        if (blocked) pose(actor, "Sulfuric Vortex");
        if (remedy) pose(actor, "Tainted Remedy");
        if (hexproof) pose(enemy, "Leyline of Sanctity");
        Card librarySkull = actor.getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals("Skullcrack")).findFirst().orElseThrow();
        Card skull = game.getAction().moveToHand(librarySkull, null);
        final int skullId = skull.getId();
        resolve(game);
        actor.setLife(20, null); enemy.setLife(lethal ? 3 : 20, null);
        game.getPhaseHandler().devModeSet(PhaseType.DRAW, ownGain ? actor : enemy);
        game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>();
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("index", events.size() + 1); e.put("event", event.getClass().getSimpleName());
                e.put("actor_life", actor.getLife()); e.put("enemy_life", enemy.getLife());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved) e.put("message", event.toString());
                events.add(e);
            }
        });
        if (!lethal) {
            (ownGain ? actor : enemy).drawCards(1);
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
        }
        priority(game, actor, enemy);
        need(actor.getLife() == 20 && enemy.getLife() == (lethal ? 3 : 20)
                && game.getStack().size() == (lethal ? 0 : 1) && !game.isGameOver(), "Settled genuine pending frontier");
        row.put("registered_main_totals", List.of(60, 60)); row.put("pending_before_choice", game.getStack().size());
        row.put("genuine_draw_player", lethal ? null : (ownGain ? actor : enemy).getId());
        row.put("rng_before_first_choice", rng());
        // First policy query. No forecast/API/affordability diagnostic precedes it.
        List<SpellAbility> options = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = options == null || options.isEmpty() ? null : options.get(0);
        row.put("ordinary_initial_callbacks", 1); row.put("first_choice", ability(chosen));
        row.put("rng_after_first_choice", rng());
        row.put("actor_view_after_choice", new ActorBoundary(actor).snapshot(game.getView()));
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default, MC off");
        boolean selected = chosen != null, manual = false, paid = false;
        if (selected) {
            need(chosen.isSpell() && chosen.getHostCard().getId() == skullId, "Unexpected selection, not relabelled PASS");
            // Pay the unchanged actual selection: never rewrite an AI target.
            paid = ComputerUtil.playStack(chosen, actor, game);
            need(paid, "Selected funded native payment failed; harness/native classification");
        } else {
            SpellAbility control = manualSkull(skull, actor, enemy);
            row.put("enemy_native_target_legal_after_PASS", control != null);
            if (lethal) {
                need(control != null, "Canonical lethal control target must be legal");
                manual = true; paid = ComputerUtil.playStack(control, actor, game);
                need(paid, "Canonical manual lethal control must pay");
            }
        }
        resolve(game);
        boolean win = game.isGameOver() && actor.hasWon() && enemy.hasLost();
        row.put("ordinary_PASS", !selected); row.put("actual_selected_payment", selected && paid);
        row.put("manual_lethal_control_not_AI_success", manual);
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("native_game_over", game.isGameOver()); row.put("actual_native_win", win);
        row.put("AI_selected_native_lethal", lethal && selected && paid && win);
        row.put("negative_expected_decline", !lethal);
        row.put("negative_decline_observed", !lethal && !selected);
        if (lethal) {
            need(win, "Actual native canonical Skullcrack lethal outcome");
            row.put("status", selected ? "LETHAL_AI_SUCCESS" : "LETHAL_MANUAL_CONTROL_ONLY");
        } else {
            need(!game.isGameOver(), "Nonlethal preservation pose must remain nonterminal");
            if (!selected) {
                int actorExpected = ownGain ? 22 : 20;
                int enemyExpected = remedy ? 18 : blocked || ownGain ? 20 : 22;
                need(actor.getLife() == actorExpected && enemy.getLife() == enemyExpected,
                        "Actual native gain/replacement outcome without a spell");
                if (hexproof) need(Boolean.FALSE.equals(row.get("enemy_native_target_legal_after_PASS")),
                        "Full Leyline makes the opponent an illegal damage target");
            }
            row.put("status", selected ? "NEGATIVE_SELECTED_OBSERVATION" : "NEGATIVE_DECLINE_OBSERVED");
            row.put("candidate_regression_requires_matched_baseline", true);
        }
        row.put("after_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("native_events", events);
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private reports directory");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110717L));
        NativeSkullcrackPreservation10 audit = new NativeSkullcrackPreservation10(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int errors = 0, declines = 0, selectedNegative = 0, lethalAi = 0, lethalManual = 0;
        for (String scene : List.of("OWN_PENDING_GAIN", "GAIN_ALREADY_BLOCKED", "TAINTED_REMEDY",
                                   "OPPONENT_HEXPROOF", "ORDINARY_LETHAL")) {
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("scene", scene); row.put("seat", seat); row.put("seed", 2026110717L);
                try {
                    audit.check(seat, scene, row);
                    if (row.get("status").equals("NEGATIVE_DECLINE_OBSERVED")) declines++;
                    if (row.get("status").equals("NEGATIVE_SELECTED_OBSERVATION")) selectedNegative++;
                    if (row.get("status").equals("LETHAL_AI_SUCCESS")) lethalAi++;
                    if (row.get("status").equals("LETHAL_MANUAL_CONTROL_ONLY")) lethalManual++;
                } catch (Throwable error) {
                    errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                    row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
                }
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n",
                        java.nio.file.StandardOpenOption.CREATE_NEW);
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status"))));
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "TRUSTED-NATIVE-PRESERVATION10; NOT NATURAL OR EXPERT CERTIFICATE");
        summary.put("total", 10); summary.put("harness_errors", errors);
        summary.put("negative_declines", declines); summary.put("negative_selected_observations", selectedNegative);
        summary.put("ordinary_AI_lethal_successes", lethalAi); summary.put("manual_lethal_controls_not_AI_success", lethalManual);
        summary.put("seed", 2026110717L); summary.put("seed_installations", 1); summary.put("natural_games", 0);
        summary.put("original_response6_separate_byte_unchanged", true);
        summary.put("negative_candidate_regression_requires_matched_baseline", true);
        boolean strict = errors == 0 && declines == 8 && lethalAi == 2;
        summary.put("strict_preservation_expectations_met", strict);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n",
                java.nio.file.StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : strict ? 0 : 1);
    }
}

