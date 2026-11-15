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

public final class NativeSkullcrackResponse6 extends AITest {
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
        need(damage != null && damage.getApi() == ApiType.DealDamage, "Full canonical Skullcrack damage subability");
        damage.setActivatingPlayer(actor); damage.resetTargets(); damage.getTargets().add(enemy);
        return root;
    }
    private void check(int seat, String scene, Map<String, Object> row) throws Exception {
        boolean pending = !scene.equals("NO_PENDING_FUNDED"), funded = !scene.equals("PENDING_UNFUNDED");
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("trusted-skullcrack-seat-" + index);
            if (index == seat) { deck.getMain().add("Skullcrack", 1); deck.getMain().add("Mountain", 59); }
            else { deck.getMain().add("Sheoldred, the Apocalypse", 1); deck.getMain().add("Mountain", 59); }
            LobbyPlayerAi lobby = new LobbyPlayerAi("trusted-skullcrack-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-SKULLCRACK-RESPONSE6"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int count = 0; count < entry.getValue(); count++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && player.getAllCards().size() == 60,
                    "Exactly sixty real registered originals per player");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, enemy);
        game.getPhaseHandler().onStackResolved();
        Card sheoldred = pose(enemy, "Sheoldred, the Apocalypse");
        pose(actor, "Mountain"); if (funded) pose(actor, "Mountain");
        Card librarySkull = actor.getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals("Skullcrack")).findFirst().orElseThrow();
        Card skull = game.getAction().moveToHand(librarySkull, null);
        final int skullId = skull.getId();
        resolve(game);
        actor.setLife(20, null); enemy.setLife(20, null);
        game.getPhaseHandler().devModeSet(PhaseType.DRAW, enemy);
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
        if (pending) {
            enemy.drawCards(1);
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
        }
        priority(game, actor, enemy);
        need(actor.getLife() == 20 && enemy.getLife() == 20 && !game.isGameOver()
                && game.getStack().size() == (pending ? 1 : 0), "Actual draw leaves the native gain trigger pending");
        need(actor.getCardsIn(ZoneType.Hand).size() == 1 && actor.getCardsIn(ZoneType.Hand).get(0).getId() == skullId
                && actor.getCardsIn(ZoneType.Battlefield).size() == (funded ? 2 : 1)
                && actor.getCardsIn(ZoneType.Battlefield).stream().allMatch(c -> c.getName().equals("Mountain") && !c.isTapped())
                && enemy.getCardsIn(ZoneType.Hand).size() == (pending ? 1 : 0),
                "Declared physical hand/mana inventory; no seeded mana or fake draw");
        row.put("registered_main_totals", List.of(60, 60));
        row.put("pending_requested", pending); row.put("funded_requested", funded);
        row.put("genuine_enemy_draw_calls", pending ? 1 : 0);
        row.put("pending_count_before_choice", game.getStack().size());
        row.put("initial_actor_life", actor.getLife()); row.put("initial_enemy_life", enemy.getLife());
        row.put("rng_before_first_choice", rng());
        // First policy query: no API/forecast/affordability diagnostic precedes this callback.
        List<SpellAbility> options = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = options == null || options.isEmpty() ? null : options.get(0);
        row.put("ordinary_initial_callbacks", 1); row.put("first_choice", ability(chosen));
        row.put("rng_after_first_choice", rng());
        row.put("actor_view_after_choice_before_payment", new ActorBoundary(actor).snapshot(game.getView()));
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary Default, MC off");
        if (pending) {
            SpellAbility actual = game.getStack().peekAbility();
            need(actual.getHostCard().getId() == sheoldred.getId(), "Pending ability comes from the real Sheoldred");
            row.put("native_pending_api_after_first_choice", String.valueOf(actual.getApi()));
        }
        boolean selected = chosen != null;
        boolean selectedSkull = selected && chosen.getHostCard().getId() == skullId && chosen.isSpell();
        need(chosen == null || selectedSkull, "Unexpected ordinary choice is a harness review, never silently PASS");
        row.put("AI_selected_Skullcrack", selectedSkull); row.put("ordinary_PASS", !selected);
        boolean paid = ComputerUtil.playStack(selected ? chosen : manualSkull(skull, actor, enemy), actor, game);
        row.put("native_payment_succeeded", paid);
        row.put("manual_rules_control_not_AI_success", !selected);
        resolve(game);
        need(!game.isGameOver() && game.getStack().isEmpty(), "Nonterminal real stack completion");
        if (funded) {
            need(paid, "Funded native spell payment failed: harness/native result, not policy");
            if (!selected) need(actor.getLife() == 20 && enemy.getLife() == 17,
                    "Manual full native Skullcrack control: three damage and pending gain prevented");
        } else {
            need(!paid && actor.getLife() == 20 && enemy.getLife() == 22
                    && actor.getCardsIn(ZoneType.Hand).stream().anyMatch(c -> c.getId() == skullId),
                    "Unfunded native payment rejected; genuine pending gain resolves for two");
        }
        boolean correctResponse = pending && funded && selectedSkull && paid
                && actor.getLife() == 20 && enemy.getLife() == 17;
        boolean policyRed = pending && (funded ? !correctResponse : selected);
        row.put("funded_pending_AI_response", correctResponse);
        row.put("unfunded_ordinary_decline", !funded && !selected);
        row.put("policy_red", policyRed); row.put("observational_no_pending", !pending);
        row.put("status", policyRed ? "POLICY_RED" : pending ? "PASS" : "OBSERVATIONAL");
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("native_game_over", game.isGameOver());
        row.put("after_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("native_events", events);
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private output directory");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110716L));
        NativeSkullcrackResponse6 audit = new NativeSkullcrackResponse6(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int errors = 0, red = 0, responses = 0, controls = 0, declined = 0, observations = 0;
        for (String scene : List.of("PENDING_FUNDED", "PENDING_UNFUNDED", "NO_PENDING_FUNDED")) {
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("scene", scene); row.put("seat", seat); row.put("seed", 2026110716L);
                try {
                    audit.check(seat, scene, row);
                    if (Boolean.TRUE.equals(row.get("policy_red"))) red++;
                    if (Boolean.TRUE.equals(row.get("funded_pending_AI_response"))) responses++;
                    if (scene.equals("PENDING_FUNDED") && Boolean.TRUE.equals(row.get("manual_rules_control_not_AI_success"))) controls++;
                    if (Boolean.TRUE.equals(row.get("unfunded_ordinary_decline"))) declined++;
                    if (Boolean.TRUE.equals(row.get("observational_no_pending"))) observations++;
                } catch (Throwable error) {
                    errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                    row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
                }
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n",
                        java.nio.file.StandardOpenOption.CREATE_NEW);
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status"))));
                System.out.flush();
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "TRUSTED-NATIVE-SKULLCRACK-RESPONSE6; NOT NATURAL OR EXPERT CERTIFICATE");
        summary.put("total", 6); summary.put("harness_errors", errors); summary.put("policy_red", red);
        summary.put("funded_pending_AI_responses", responses); summary.put("funded_pending_manual_controls", controls);
        summary.put("unfunded_declines", declined); summary.put("no_pending_observations", observations);
        summary.put("seed", 2026110716L); summary.put("seed_installations", 1);
        summary.put("natural_games", 0); summary.put("manual_control_is_not_AI_success", true);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n",
                java.nio.file.StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}

