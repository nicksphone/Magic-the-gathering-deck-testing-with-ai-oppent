// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled canonical native goldens; Card-Forge61e944 attribution/license retained.
// No production edit, injected keyword, forced X, or natural-history claim.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.deck.Deck;
import forge.card.CardStateName;
import forge.game.*;
import forge.game.ability.AbilityKey;
import forge.game.card.Card;
import forge.game.card.CardCollection;
import forge.game.card.CounterType;
import forge.game.keyword.Keyword;
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
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public final class NativeChaliceGoldenAudit extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110601L;
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true); // Trusted registered-main setup, matching Match.preparePlayerZone.
        return card;
    }
    private static void need(boolean ok, String why) {
        if (!ok) throw new IllegalStateException("HARNESS: " + why);
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream output = new ObjectOutputStream(bytes)) { output.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Integer> registered(Player player) {
        Map<String, Integer> counts = new TreeMap<>();
        for (var entry : player.getRegisteredPlayer().getDeck().getMain()) counts.merge(entry.getKey().getName(), entry.getValue(), Integer::sum);
        return counts;
    }
    private static Map<String, Integer> originals(Player player) {
        Map<String, Integer> counts = new TreeMap<>();
        for (Card card : player.getAllCards()) counts.merge(card.getState(CardStateName.Original).getName(), 1, Integer::sum);
        return counts;
    }
    private static Map<String, Object> oldRow(Object value) throws Exception {
        Method row = value.getClass().getDeclaredMethod("row"); row.setAccessible(true);
        @SuppressWarnings("unchecked") Map<String, Object> result = (Map<String, Object>) row.invoke(value);
        return result;
    }

    private Map<String, Object> golden(Path out, int seat, String scene) throws Exception {
        boolean exile = scene.startsWith("Exile"), breach = scene.equals("BreachEscape"), returned = scene.equals("ReturnedKnown");
        MyRandom.setRandom(new Random(SEED + 100 + seat)); // Before independent fixture construction only.
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck(i == seat ? "actor-disclosed" : "opponent-disclosed");
            if (i == seat) { deck.getMain().add("Chalice of the Void", 1); deck.getMain().add("Island", 59); }
            else {
                deck.getMain().add("Island", breach ? 54 : 55); deck.getMain().add("Opt", 4);
                deck.getMain().add("Runeclaw Bear", 1); if (breach) deck.getMain().add("Underworld Breach", 1);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("audit-seat" + i, null); lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-CHALICE-GOLDENS"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false); game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1 - seat);
        actor.setLife(20, null); opponent.setLife(20, null);
        Card chalice = addCardToZone("Chalice of the Void", actor, ZoneType.Hand);
        addCard("Island", actor); addCard("Island", actor);
        for (int i = 0; i < 57; i++) addCardToZone("Island", actor, ZoneType.Library);
        List<Card> islands = new ArrayList<>();
        for (int i = 0; i < (breach ? 54 : 55); i++) islands.add(addCardToZone("Island", opponent, ZoneType.Library));
        game.getAction().moveToHand(islands.get(0), null);
        Card target;
        if (exile) {
            // Opaque ID slot is fixed by construction; printed identity is never mutated.
            target = createCard(scene.equals("ExileOpt") ? "Opt" : "Runeclaw Bear", opponent);
            target.setGameTimestamp(game.getNextTimestamp());
            need(target.turnFaceDown(true), "Canonical card accepts native face-down current state");
            opponent.getZone(ZoneType.Exile).add(target);
            for (int i = 0; i < (scene.equals("ExileOpt") ? 3 : 4); i++) addCardToZone("Opt", opponent, ZoneType.Library);
            if (scene.equals("ExileOpt")) addCardToZone("Runeclaw Bear", opponent, ZoneType.Library);
        } else {
            List<Card> opts = new ArrayList<>();
            for (int i = 0; i < 4; i++) opts.add(addCardToZone("Opt", opponent, ZoneType.Library));
            addCardToZone("Runeclaw Bear", opponent, ZoneType.Library);
            target = game.getAction().moveToGraveyard(opts.get(0), null);
            if (returned) {
                target = game.getAction().moveToHand(target, null);
                game.getAction().reveal(new CardCollection(target), opponent);
            }
            if (breach) {
                addCard("Underworld Breach", opponent);
                game.getAction().moveToPlay(islands.get(1), opponent, null, AbilityKey.newMap());
                for (int i = 2; i < 5; i++) game.getAction().moveToGraveyard(islands.get(i), null);
            }
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor, 5);
        game.getPhaseHandler().setPriority(actor); game.getAction().checkStateEffects(true);
        need(registered(actor).equals(originals(actor)) && registered(opponent).equals(originals(opponent)), "Actual original inventories equal registered decks");
        need(actor.getAllCards().stream().allMatch(Card::isCollectible)
                && opponent.getAllCards().stream().allMatch(Card::isCollectible), "Every NEW original uses registered collectible producer contract");
        need(registered(actor).values().stream().mapToInt(Integer::intValue).sum() == 60
                && registered(opponent).values().stream().mapToInt(Integer::intValue).sum() == 60, "Two legal60-card original inventories");
        need(game.getPhaseHandler().getPriorityPlayer() == actor && !game.isGameOver(), "Actor MAIN2 priority, nonterminal");
        Set<Card> memory = AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS);
        boolean remembered = memory != null && memory.contains(target);
        if (exile) {
            need(target.isFaceDown() && !target.getView().canFaceDownBeShownTo(actor.getView()), "Exiled identity unknown to observer");
            need(memory == null || memory.isEmpty(), "Unknown exile has no reveal-memory shortcut");
            need(opponent.getCardsIn(ZoneType.Hand).size() == 1 && opponent.getCardsIn(ZoneType.Library).size() == 58,
                    "Same exile-pair hand/library/exile counts");
        } else if (returned) need(remembered && target.isInZone(ZoneType.Hand), "Real native reveal remembers returned Opt");
        else need(target.isInZone(ZoneType.Graveyard) && target.getView().canBeShownTo(actor.getView()), "Public face-up Opt GY");

        Map<String, Object> input = new LinkedHashMap<>();
        input.put("actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        input.put("disclosed_actor_registered_deck", registered(actor)); input.put("disclosed_opponent_registered_deck", registered(opponent));
        input.put("priority_actor", true); input.put("known_returned_Opt", remembered);
        String incoming = rng();
        // First and only ordinary Default choice, before native cost/alternative-policy diagnostics.
        List<SpellAbility> chosen = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        String outgoing = rng();
        List<Object> selection = new ArrayList<>();
        if (chosen != null) for (SpellAbility ability : chosen) {
            Map<String, Object> action = new LinkedHashMap<>();
            action.put("source", ability.getHostCard().getName()); action.put("native_X", ability.getXManaCostPaid());
            action.put("is_spell", ability.isSpell()); selection.add(action);
        }
        Map<String, Object> output = Map.of("container", chosen == null ? "null" : chosen.isEmpty() ? "empty" : "list", "selection", selection);
        boolean selectedX1 = chosen != null && chosen.size() == 1 && chosen.get(0).isSpell()
                && chosen.get(0).getHostCard().getName().equals("Chalice of the Void") && Integer.valueOf(1).equals(chosen.get(0).getXManaCostPaid());
        boolean decline = chosen == null || chosen.isEmpty();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("label", "NEW-CONTROLLED-GOLDEN"); row.put("seat", seat); row.put("scene", scene);
        row.put("actor_input", input); row.put("incoming_full_RNG", incoming); row.put("ending_choice_full_RNG", outgoing);
        row.put("output_action_X", output); row.put("actual_original_inventory", originals(opponent));
        row.put("registered_collectible_setup", true);
        row.put("opaque_exile_card_id", exile ? target.getId() : null); row.put("first_default_choice_calls", 1);
        Files.writeString(out.resolve("new-first-" + seat + "-" + scene + ".private.json"), JSON.toJson(row) + "\n");
        List<String> controls = new ArrayList<>();
        if (breach) {
            boolean granted = target.hasKeyword(Keyword.ESCAPE);
            int alternatives = 0; boolean payable = false, restriction = false;
            for (SpellAbility base : target.getSpellAbilities()) if (base.isSpell()) {
                for (SpellAbility alternative : GameActionUtil.getAlternativeCosts(base, opponent, true)) if (alternative.isEscape()) {
                    alternatives++; restriction |= alternative.checkRestrictions(opponent);
                    payable |= ComputerUtilCost.canPayCost(alternative, opponent, false);
                }
            }
            row.put("native_escape_keyword_granted", granted); row.put("native_escape_alternatives", alternatives);
            row.put("native_escape_restriction_pass", restriction); row.put("native_escape_cost_feasible", payable);
            row.put("other_public_GY_material", opponent.getCardsIn(ZoneType.Graveyard).size() - 1);
            if (!granted || alternatives == 0 || !restriction || !payable) controls.add("Real Breach escape grant/cost control failed");
        }
        boolean golden = exile || (scene.equals("SpentOptGY") ? decline : selectedX1);
        row.put("expected", exile ? "Same opaque input/RNG implies same output+X in pair" : scene.equals("SpentOptGY") ? "DECLINE futurebucket3" : "CAST nativeX1 futurebucket4");
        row.put("strict_golden_pass", golden); row.put("control_failures", controls);
        row.put("status", !controls.isEmpty() ? "CONTROL_FAIL" : golden ? "PASS" : "POLICY_RED");
        // Only actual chosen native output executes; no X or alternative is forced.
        if (chosen != null && !chosen.isEmpty()) {
            need(chosen.size() == 1 && chosen.get(0).getHostCard().getName().equals("Chalice of the Void"), "Only selected Chalice may execute");
            SpellAbility ability = chosen.get(0);
            boolean paid = ComputerUtil.playStack(ability, actor, game);
            need(paid && game.getStack().size() == 1, "Selected native Chalice pays and enters stack");
            int spent = ability.getTotalManaSpent();
            game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
            Card result = actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Chalice of the Void")).findFirst().orElseThrow();
            row.put("actual_native_mana_spent", spent); row.put("actual_native_charge_counters", result.getCounters(CounterType.getType("CHARGE")));
        }
        row.put("native_game_over", game.isGameOver());
        Files.writeString(out.resolve("new-result-" + seat + "-" + scene + ".private.json"), JSON.toJson(row) + "\n");
        return row;
    }

    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]); MyRandom.setRandom(new Random(SEED));
        NativeChalicePartitionAudit old = new NativeChalicePartitionAudit(); old.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        Method first = NativeChalicePartitionAudit.class.getDeclaredMethod("firstChoice", Path.class, int.class, String.class); first.setAccessible(true);
        Map<String, Map<String, Object>> oldRows = new LinkedHashMap<>();
        int errors = 0, oldPrivateRed = 0, oldPublicValid = 0, controls = 0;
        for (int seat = 0; seat < 2; seat++) for (String scene : List.of("A", "B", "C", "D")) {
            try { oldRows.put(seat + scene, oldRow(first.invoke(old, out, seat, scene))); }
            catch (Throwable error) { errors++; (error instanceof InvocationTargetException ? error.getCause() : error).printStackTrace(System.err); }
        }
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> a = oldRows.get(seat + "A"), b = oldRows.get(seat + "B"), c = oldRows.get(seat + "C"), d = oldRows.get(seat + "D");
            boolean valid = a != null && b != null && a.get("actor_input").equals(b.get("actor_input")) && a.get("incoming_full_RNG").equals(b.get("incoming_full_RNG"));
            if (!valid) controls++; else if (!a.get("output_action_X").equals(b.get("output_action_X"))) oldPrivateRed++;
            boolean publicValid = c != null && d != null && !c.get("actor_input").equals(d.get("actor_input"))
                    && c.get("opponent_hand_visible").equals(true) && d.get("opponent_hand_visible").equals(true);
            if (publicValid) oldPublicValid++; else controls++;
            Files.writeString(out.resolve("old-pair-" + seat + ".json"), JSON.toJson(Map.of("private_preconditions", valid,
                    "private_action_X_equal", valid && a.get("output_action_X").equals(b.get("output_action_X")),
                    "public_visibility_contrast_valid", publicValid, "public_output_divergence_required", false)) + "\n");
        }
        NativeChaliceGoldenAudit test = new NativeChaliceGoldenAudit();
        Map<String, Map<String, Object>> rows = new LinkedHashMap<>(); int newPass = 0, newRed = 0, exilePairsPass = 0;
        for (String scene : List.of("ExileOpt", "ExileBear", "SpentOptGY", "ReturnedKnown", "BreachEscape")) for (int seat = 0; seat < 2; seat++) {
            try {
                Map<String, Object> row = test.golden(out, seat, scene); rows.put(seat + scene, row);
                if (row.get("status").equals("PASS")) newPass++; else if (row.get("status").equals("POLICY_RED")) newRed++; else controls++;
            } catch (Throwable error) { errors++; error.printStackTrace(System.err); }
        }
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> a = rows.get(seat + "ExileOpt"), b = rows.get(seat + "ExileBear");
            boolean valid = a != null && b != null && a.get("actor_input").equals(b.get("actor_input"))
                    && a.get("incoming_full_RNG").equals(b.get("incoming_full_RNG")) && a.get("opaque_exile_card_id").equals(b.get("opaque_exile_card_id"));
            boolean equal = valid && a.get("output_action_X").equals(b.get("output_action_X"));
            if (!valid) controls++; else if (equal) exilePairsPass++; else newRed++;
            Files.writeString(out.resolve("exile-pair-" + seat + ".json"), JSON.toJson(Map.of("preconditions_equal_including_opaque_id", valid,
                    "output_action_X_equal", equal)) + "\n");
        }
        Map<String, Object> summary = Map.of("old8", Map.of("rows", oldRows.size(), "private_pairs_red", oldPrivateRed,
                "public_control_pairs_valid", oldPublicValid), "new10", Map.of("rows", rows.size(), "pass_cases", newPass,
                "strict_policy_red_cases", newRed, "exile_pairs_pass", exilePairsPass), "control_fail", controls,
                "harness_errors", errors, "synthetic_cases_run", 0, "natural_game", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n"); System.out.println(JSON.toJson(summary));
        System.exit(errors != 0 || controls != 0 ? 2 : oldPrivateRed != 0 || newRed != 0 ? 1 : 0);
    }
}
