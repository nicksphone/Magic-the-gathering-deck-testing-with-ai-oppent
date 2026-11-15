// SPDX-License-Identifier: GPL-3.0-or-later
// Original controlled audit using Card-Forge 61e9442c433711a82258daca3236f936a1d6f70e.
// Canonical programs unchanged; disclosed-list premise only; no product override.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.AITest;
import forge.ai.AiCardMemory;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.card.CardStateName;
import forge.deck.Deck;
import forge.game.*;
import forge.game.card.Card;
import forge.game.card.CounterType;
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

public final class NativeChalicePartitionAudit extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110601L;
    private static void need(boolean ok, String why) {
        if (!ok) throw new IllegalStateException("HARNESS: " + why);
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) {
            stream.writeObject(MyRandom.getRandom());
        }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Integer> inventory(Player player) {
        Map<String, Integer> result = new TreeMap<>();
        for (Card card : player.getAllCards()) result.merge(card.getName(), 1, Integer::sum);
        return result;
    }
    private static Map<String, Integer> registered(Player player) {
        Map<String, Integer> result = new TreeMap<>();
        for (var entry : player.getRegisteredPlayer().getDeck().getMain()) {
            result.merge(entry.getKey().getName(), entry.getValue(), Integer::sum);
        }
        return result;
    }
    private record Case(Game game, Player actor, Player opponent, Card chalice, Map<String, Object> row) {}

    private Case firstChoice(Path out, int seat, String scene) throws Exception {
        boolean publicHand = scene.equals("C") || scene.equals("D");
        boolean bearInHand = scene.equals("A") || scene.equals("C");
        // Fresh independent fixture seed BEFORE any game/card construction, never reset afterward.
        MyRandom.setRandom(new Random(SEED + seat));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck(i == seat ? "actor-disclosed" : "opponent-disclosed");
            if (i == seat) {
                deck.getMain().add("Chalice of the Void", 1);
                if (publicHand) deck.getMain().add("Telepathy", 1);
                deck.getMain().add("Island", publicHand ? 58 : 59);
            } else {
                deck.getMain().add("Island", 55);
                deck.getMain().add("Opt", 4);
                deck.getMain().add("Runeclaw Bear", 1);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("audit-seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-CHALICE-PARTITION"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1 - seat);
        actor.setLife(20, null); opponent.setLife(20, null);
        Card chalice = addCardToZone("Chalice of the Void", actor, ZoneType.Hand);
        addCard("Island", actor); addCard("Island", actor);
        for (int i = 0; i < (publicHand ? 56 : 57); i++) addCardToZone("Island", actor, ZoneType.Library);
        if (publicHand) addCard("Telepathy", actor);
        // Identical complete construction order; only the later hidden partition differs.
        for (int i = 0; i < 55; i++) addCardToZone("Island", opponent, ZoneType.Library);
        List<Card> opts = new ArrayList<>();
        for (int i = 0; i < 4; i++) opts.add(addCardToZone("Opt", opponent, ZoneType.Library));
        Card bear = addCardToZone("Runeclaw Bear", opponent, ZoneType.Library);
        Card hand = game.getAction().moveToHand(bearInHand ? bear : opts.get(0), null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor);
        game.getPhaseHandler().setPriority(actor);
        game.getAction().checkStateEffects(true);
        Map<String, Integer> actorDeck = registered(actor), opponentDeck = registered(opponent);
        need(actorDeck.equals(inventory(actor)) && actorDeck.values().stream().mapToInt(Integer::intValue).sum() == 60,
                "Actual own inventory must equal disclosed registered60");
        need(opponentDeck.equals(Map.of("Island", 55, "Opt", 4, "Runeclaw Bear", 1))
                && opponentDeck.equals(inventory(opponent)), "Same full opponent60-card inventory");
        need(opponent.getCardsIn(ZoneType.Hand).size() == 1 && opponent.getCardsIn(ZoneType.Library).size() == 59,
                "Declared opponent zone counts");
        need(actor.getCardsIn(ZoneType.Hand).size() == 1
                && actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Island") && !c.isTapped()).count() == 2,
                "Only Chalice in hand and exactly two funded untapped Islands");
        need(game.getPhaseHandler().getPlayerTurn() == actor && game.getPhaseHandler().getPriorityPlayer() == actor,
                "Own MAIN2 priority");
        need(hand.getView().canBeShownTo(actor.getView()) == publicHand, "Actual canonical Telepathy visibility/absence");
        var revealed = AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS);
        if (!publicHand) need(revealed == null || revealed.isEmpty(), "No legitimate reveal-memory difference in private pair");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary heuristic Default");
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        input.put("disclosed_actor_registered_deck", actorDeck);
        input.put("disclosed_opponent_registered_deck", opponentDeck);
        input.put("actor_has_priority", true);
        input.put("legitimate_revealed_memory_count", revealed == null ? 0 : revealed.size());
        String incoming = rng();
        // Exactly one genuine Default choice. No named policy, cost/max-X or forecast probe precedes it.
        List<SpellAbility> chosen = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        String outgoing = rng();
        List<Object> semantic = new ArrayList<>(), raw = new ArrayList<>();
        if (chosen != null) for (SpellAbility ability : chosen) {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("source", ability.getHostCard().getName()); value.put("is_spell", ability.isSpell());
            value.put("api", String.valueOf(ability.getApi())); value.put("native_X", ability.getXManaCostPaid());
            semantic.add(value);
            Map<String, Object> nativeValue = new LinkedHashMap<>(value);
            nativeValue.put("ability_id", ability.getId()); nativeValue.put("source_card_id", ability.getHostCard().getId());
            raw.add(nativeValue);
        }
        Map<String, Object> action = Map.of("container", chosen == null ? "null" : chosen.isEmpty() ? "empty" : "list",
                "selected_action_X", semantic);
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("label", "CONTROLLED-FIRST-DEFAULT-CHOICE"); row.put("seat", seat); row.put("scene", scene);
        row.put("actor_input", input); row.put("incoming_full_RNG", incoming); row.put("ending_choice_full_RNG", outgoing);
        row.put("output_action_X", action); row.put("raw_native_selection", raw);
        List<Integer> nativeXFields = new ArrayList<>();
        for (SpellAbility ability : chalice.getSpellAbilities()) if (ability.isSpell()) nativeXFields.add(ability.getXManaCostPaid());
        row.put("native_cast_X_fields_after_first_choice", nativeXFields);
        row.put("actual_opponent_inventory", inventory(opponent)); row.put("actual_actor_inventory", inventory(actor));
        row.put("opponent_hand_visible", publicHand); row.put("first_default_choice_calls", 1);
        row.put("declared_hidden_hand", hand.getName()); row.put("native_game_over", game.isGameOver());
        Files.writeString(out.resolve("first-" + seat + "-" + scene + ".private.json"), JSON.toJson(row) + "\n");

        // Only actually selected native output may execute. Never set X or force an alternative.
        Map<String, Object> execution = new LinkedHashMap<>();
        execution.put("chosen", chosen != null && !chosen.isEmpty());
        if (chosen != null && !chosen.isEmpty()) {
            need(chosen.size() == 1 && chosen.get(0).isSpell() && chosen.get(0).getHostCard() == chalice,
                    "Only selected canonical Chalice may execute");
            SpellAbility ability = chosen.get(0);
            Integer x = ability.getXManaCostPaid();
            boolean paid = ComputerUtil.playStack(ability, actor, game);
            execution.put("native_X_before_payment", x); execution.put("native_payment_succeeded", paid);
            execution.put("native_total_mana_spent", ability.getTotalManaSpent());
            execution.put("native_stack_size", game.getStack().size());
            need(paid && game.getStack().size() == 1, "A genuinely selected cast must pay and enter native stack");
            game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
            Card resolved = actor.getCardsIn(ZoneType.Battlefield).stream()
                    .filter(c -> c.getName().equals("Chalice of the Void")).findFirst().orElseThrow();
            execution.put("native_charge_counters", resolved.getCounters(CounterType.getType("CHARGE")));
            execution.put("tapped_Islands", actor.getCardsIn(ZoneType.Battlefield).stream()
                    .filter(c -> c.getName().equals("Island") && c.isTapped()).count());
        }
        execution.put("native_game_over", game.isGameOver());
        Files.writeString(out.resolve("execution-" + seat + "-" + scene + ".private.json"), JSON.toJson(execution) + "\n");
        return new Case(game, actor, opponent, chalice, row);
    }

    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED));
        NativeChalicePartitionAudit audit = new NativeChalicePartitionAudit();
        audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        Map<String, Case> cases = new LinkedHashMap<>();
        int errors = 0, privacyRed = 0, privacyPass = 0, harnessPairs = 0, publicValid = 0;
        for (int seat = 0; seat < 2; seat++) for (String scene : List.of("A", "B")) {
            try { cases.put(seat + scene, audit.firstChoice(out, seat, scene)); }
            catch (Throwable error) { errors++; error.printStackTrace(System.err); }
        }
        // All four private first-choice rows are written before any privacy assertion/branch diagnostic.
        for (int seat = 0; seat < 2; seat++) {
            Case a = cases.get(seat + "A"), b = cases.get(seat + "B");
            boolean preconditions = a != null && b != null
                    && a.row.get("actor_input").equals(b.row.get("actor_input"))
                    && a.row.get("incoming_full_RNG").equals(b.row.get("incoming_full_RNG"));
            boolean same = preconditions && a.row.get("output_action_X").equals(b.row.get("output_action_X"));
            if (!preconditions) harnessPairs++; else if (same) privacyPass++; else privacyRed++;
            Files.writeString(out.resolve("private-pair-" + seat + ".json"), JSON.toJson(Map.of(
                    "preconditions_equal", preconditions, "action_X_equal", same,
                    "status", !preconditions ? "HARNESS_PRECONDITION_FAIL" : same ? "PASS" : "POLICY_RED")) + "\n");
        }
        for (int seat = 0; seat < 2; seat++) for (String scene : List.of("C", "D")) {
            try { cases.put(seat + scene, audit.firstChoice(out, seat, scene)); }
            catch (Throwable error) { errors++; error.printStackTrace(System.err); }
        }
        for (int seat = 0; seat < 2; seat++) {
            Case c = cases.get(seat + "C"), d = cases.get(seat + "D");
            boolean valid = c != null && d != null && !c.row.get("actor_input").equals(d.row.get("actor_input"))
                    && c.row.get("opponent_hand_visible").equals(true) && d.row.get("opponent_hand_visible").equals(true);
            if (valid) publicValid++; else harnessPairs++;
            Files.writeString(out.resolve("public-pair-" + seat + ".json"), JSON.toJson(Map.of(
                    "visibility_contrast_valid", valid, "noninterference_not_required", true)) + "\n");
        }
        // Passive source-matched counts only after all first decisions; no direct PermanentAi probe.
        for (var entry : cases.entrySet()) {
            long count = entry.getValue().opponent.getAllCards().stream()
                    .filter(card -> card.isInZone(ZoneType.Library) || !card.isInZone(ZoneType.Hand))
                    .filter(card -> card.getState(CardStateName.Original).getManaCost() != null
                            && card.getState(CardStateName.Original).getManaCost().getCMC() == 1).count();
            Files.writeString(out.resolve("post-branch-count-" + entry.getKey() + ".json"), JSON.toJson(Map.of(
                    "library_or_nonhand_manaValue1", count, "disclosed_total_Opt", 4,
                    "label", "POST-DECISION read-only source-count diagnostic, not policy evaluation")) + "\n");
        }
        Map<String, Object> summary = Map.of("first_case_rows", cases.size(), "private_pairs_policy_red", privacyRed,
                "private_pairs_pass", privacyPass, "public_control_pairs_valid", publicValid,
                "harness_errors", errors, "harness_precondition_pairs_fail", harnessPairs,
                "natural_game", false, "disclosed_registered_deck_premise", true);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary));
        System.exit(errors != 0 || harnessPairs != 0 ? 2 : privacyRed != 0 ? 1 : 0);
    }
}
