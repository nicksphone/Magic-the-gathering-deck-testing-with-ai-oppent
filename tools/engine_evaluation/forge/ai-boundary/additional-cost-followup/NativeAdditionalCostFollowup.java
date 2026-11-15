// SPDX-License-Identifier: GPL-3.0-or-later
// Original bounded tests of Forge Team/Card-Forge native work at
// https://github.com/Card-Forge/forge, 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and ../../LICENSE. Tests only; no production rule changes.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.AiCardMemory;
import forge.ai.ComputerUtil;
import forge.ai.ComputerUtilMana;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.ComboPlan;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.card.CardCollection;
import forge.game.card.CounterType;
import forge.game.combat.Combat;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

public final class NativeAdditionalCostFollowup extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;
    private static int completedAttacks;
    private record Decision(Map<String, Object> actorView, List<Map<String, Object>> knownCallbacks,
                            String rngBefore, String rngAfter, String attack,
                            boolean fogAffordable, boolean publicSourceEligible, boolean payerHeldPiece) {}

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void fixture(boolean condition, String message) {
        if (!condition) throw new IllegalStateException("Invalid fixture: " + message);
    }

    private static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static String rngState(Random rng) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) { out.writeObject(rng); }
        return sha(bytes.toByteArray());
    }

    private static void reveal(Player actor, Player owner, Card card,
                               List<Map<String, Object>> callbacks) {
        ZoneType zone = card.getZone().getZoneType();
        ((PlayerControllerAi) actor.getController()).reveal(new CardCollection(List.of(card)),
                zone, owner, "CONTROLLED-NATIVE authorized reveal", true);
        callbacks.add(Map.of("card_id", card.getId(), "name", card.getName(), "zone", zone.name()));
    }

    private Decision decide(int seat, boolean heldPiece, boolean revealUnknown, boolean publicMana) throws Exception {
        MyRandom.setRandom(new Random(SEED));
        Random rng = MyRandom.getRandom();
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("seat" + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "CONTROLLED-NATIVE discard cost"));
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO = false;
        game.AI_FLAT_MONTE_CARLO_MAX = false;
        game.AI_FLAT_MONTE_CARLO_LITE = false;
        game.AI_TIMEOUT = 10;
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), defender = game.getPlayers().get(1 - seat);
        fixture(!((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary heuristic controller required");
        actor.setLife(20, null);
        defender.setLife(2, null);
        Card wurm = addCard("Craw Wurm", actor);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", defender);
        jace.setCounters(CounterType.getType("LOYALTY"), Integer.parseInt(jace.getBaseLoyalty()));
        Card familiar = addCard("Skirge Familiar", defender);
        familiar.setSickness(false);
        // Native discard activation has no tap cost. Tapping prevents it being a blocker.
        familiar.setTapped(true);
        Card swamp = addCard("Swamp", defender);
        swamp.setTapped(!publicMana);
        Card darkness = addCardToZone("Darkness", defender, ZoneType.Hand);
        // Fixed creation order and complete multiset; only hand/library placement changes.
        Card payoff = addCardToZone("Tendrils of Agony", defender, heldPiece ? ZoneType.Hand : ZoneType.Library);
        Card forest = addCardToZone("Forest", defender, heldPiece ? ZoneType.Library : ZoneType.Hand);
        Card unknown = heldPiece ? payoff : forest;
        addCardToZone("Forest", actor, ZoneType.Library);
        addCardToZone("Forest", actor, ZoneType.Library);
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, actor);
        game.getAction().checkStateEffects(true);
        fixture(!game.isGameOver() && jace.isInPlay() && jace.getCurrentLoyalty() == 3, "Nonterminal printed board required");
        fixture(familiar.getView().canBeShownTo(actor.getView())
                && familiar.getView().canFaceDownBeShownTo(actor.getView()), "Actual source identity must be public");
        fixture(!unknown.getView().canBeShownTo(actor.getView()) && !darkness.getView().canBeShownTo(actor.getView()),
                "No current opponent-hand view grant allowed");
        fixture(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).isEmpty(), "No prior reveal history");
        List<Map<String, Object>> callbacks = new ArrayList<>();
        reveal(actor, defender, darkness, callbacks);
        reveal(actor, defender, familiar, callbacks);
        if (revealUnknown) reveal(actor, defender, unknown, callbacks);
        Set<Card> expectedMemory = revealUnknown ? Set.of(darkness, familiar, unknown) : Set.of(darkness, familiar);
        fixture(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).equals(expectedMemory),
                "Only actual authorized callback cards may be remembered");
        Map<String, Object> view = new ActorBoundary(actor).snapshot(game.getView());
        Combat combat = new Combat(actor);
        fixture(combat.getDefendingPlaneswalkers().contains(jace), "Native combat must offer Jace");
        game.getPhaseHandler().setCombat(combat);
        fixture(MyRandom.getRandom() == rng, "RNG instance must remain the original fixture input");
        String before = rngState(rng);
        actor.getController().declareAttackers(actor, combat);
        completedAttacks++;
        String after = rngState(rng);
        fixture(MyRandom.getRandom() == rng, "No RNG replacement during native callback");
        fixture(combat.getAttackers().size() == 1 && combat.isAttacking(wurm), "Native AI must actually attack");
        GameEntity target = combat.getDefenderByAttacker(wurm);
        String attack = target == defender ? "opponent" : target == jace ? "Jace Beleren" : "unexpected";
        fixture(!attack.equals("unexpected"), "Unknown native defender");
        // Diagnostics follow the actual callback and nondestructive ending-RNG capture.
        boolean affordable = ComputerUtil.hasAFogEffect(defender, actor, true);
        boolean source = ComputerUtilMana.getAvailableManaSources(defender, true).contains(familiar);
        boolean held = ComboPlan.holdsKillPiece(defender);
        fixture(source, "The real source must be natively eligible in both variants");
        fixture(darkness.isInZone(ZoneType.Hand) && unknown.isInZone(ZoneType.Hand)
                && payoff.isInZone(heldPiece ? ZoneType.Hand : ZoneType.Library)
                && forest.isInZone(heldPiece ? ZoneType.Library : ZoneType.Hand), "No forecast discard or zone movement");
        fixture(familiar.isInPlay() && familiar.isTapped() && swamp.isTapped() == !publicMana
                && defender.getManaPool().totalMana() == 0, "No activation or manufactured mana");
        fixture(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).equals(expectedMemory),
                "Native forecast must not reveal the private variant");
        fixture(!game.isGameOver(), "No manufactured outcome");
        return new Decision(view, callbacks, before, after, attack, affordable, source, held);
    }

    private void pair(int seat, String family) throws Exception {
        boolean revealed = family.equals("legit-known-hand-control");
        boolean publicMana = family.equals("public-mana-control");
        Decision a = decide(seat, true, revealed, publicMana);
        Decision b = decide(seat, false, revealed, publicMana);
        System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE", "family", family, "seat", seat,
                "variant_a", a, "variant_b", b)));
        fixture(a.actorView.equals(b.actorView), "Physical actor snapshots must be exactly matched");
        fixture(a.rngBefore.equals(b.rngBefore), "Actual pre-decision RNG states must match without restoring them");
        if (revealed) {
            require(!a.knownCallbacks.equals(b.knownCallbacks), "Known-hand control must really disclose different cards");
            require(a.payerHeldPiece && !b.payerHeldPiece, "Native held-piece control must be sensitive");
            require(!a.fogAffordable && b.fogAffordable, "Legitimately known held-piece context must change native affordability");
            require(a.attack.equals("opponent") && b.attack.equals("Jace Beleren"), "Legitimate knowledge control must change the actual attack");
        } else {
            fixture(a.knownCallbacks.equals(b.knownCallbacks), "Observer callback knowledge must match");
            require(a.attack.equals(b.attack), "Unknown hand changed the actual native attack defender");
            require(a.fogAffordable == b.fogAffordable, "Unknown hand changed scoped Fog affordability");
            require(a.rngAfter.equals(b.rngAfter), "Unknown hand changed ending native RNG state");
            if (publicMana) {
                require(a.fogAffordable && b.fogAffordable && a.attack.equals("Jace Beleren"),
                        "Independent public mana must fund the known Fog in both variants");
            }
        }
    }

    private static Map<String, Object> origin(Class<?> type) throws Exception {
        String name = "/" + type.getName().replace('.', '/') + ".class";
        byte[] bytes;
        try (var in = type.getResourceAsStream(name)) { bytes = in.readAllBytes(); }
        return Map.of("class", type.getName(), "resource", type.getResource(name).toString(), "sha256", sha(bytes));
    }

    public static void main(String[] args) throws Exception {
        NativeAdditionalCostFollowup test = new NativeAdditionalCostFollowup();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Class<?>> pinned = List.of(NativeAdditionalCostFollowup.class, Decision.class, AITest.class,
                ActorBoundary.class, ComputerUtil.class, ComputerUtilMana.class, forge.ai.ComputerUtilCost.class,
                Class.forName("forge.ai.ComputerUtilCost$1"), ComboPlan.class, forge.ai.AiAttackController.class,
                forge.ai.AiController.class, PlayerControllerAi.class, Player.class, forge.game.card.CardView.class,
                forge.game.cost.CostDiscard.class, MyRandom.class, Class.forName("forge.util.MyRandom$CountingRandom"));
        List<Map<String, Object>> before = new ArrayList<>();
        for (Class<?> type : pinned) before.add(origin(type));
        Files.writeString(Path.of(args[0], "class-origins.json"), JSON.toJson(before));
        int pass = 0, red = 0, errors = 0;
        for (String family : List.of("strict-unknown-held-piece", "legit-known-hand-control", "public-mana-control")) {
            for (int seat = 0; seat < 2; seat++) {
                try {
                    test.pair(seat, family);
                    pass++;
                    System.out.println("PASS " + family + " seat=" + seat);
                } catch (AssertionError failure) {
                    red++;
                    System.out.println("RED " + family + " seat=" + seat + " " + failure.getMessage());
                } catch (Exception failure) {
                    errors++;
                    failure.printStackTrace();
                }
            }
        }
        List<Map<String, Object>> after = new ArrayList<>();
        for (Class<?> type : pinned) after.add(origin(type));
        fixture(before.equals(after), "Explicit loaded resource origins/hashes changed during test");
        Files.writeString(Path.of(args[0], "class-origins.after.json"), JSON.toJson(after));
        Files.writeString(Path.of(args[0], "summary.json"), JSON.toJson(Map.of("pass", pass, "red", red, "errors", errors,
                "strict_checks", 2, "positive_controls", 4, "actual_attack_decisions", completedAttacks,
                "rng_restores", 0, "controller", "Default heuristic")));
        System.out.println("SUMMARY PASS=" + pass + " RED=" + red + " ERRORS=" + errors);
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
