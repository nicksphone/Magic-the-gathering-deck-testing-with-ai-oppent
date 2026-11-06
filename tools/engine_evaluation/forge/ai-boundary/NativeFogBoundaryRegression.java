// SPDX-License-Identifier: GPL-3.0-or-later
// Original controlled-native audit using the Forge Team/Card-Forge engine and AITest helpers.
// Upstream: https://github.com/Card-Forge/forge at 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and ../LICENSE. Not a natural game or a fairness certificate.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.AiCardMemory;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class NativeFogBoundaryRegression extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;

    private record Decision(Map<String, Object> actorView, boolean fogAvailable,
                            String attack, int rngTail) {}

    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private Game position(int seat) {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-NATIVE fog boundary"));
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO = false;
        game.AI_FLAT_MONTE_CARLO_MAX = false;
        game.AI_FLAT_MONTE_CARLO_LITE = false;
        game.AI_TIMEOUT = 10;
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        require(!((PlayerControllerAi) game.getPlayers().get(seat).getController()).getAi().usesSimulation(),
                "Ordinary native heuristic controller required");
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, game.getPlayers().get(seat));
        return game;
    }

    private Decision decide(int seat, String family, boolean fogFirst) {
        MyRandom.setRandom(new Random(SEED));
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat);
        Player defender = game.getPlayers().get(1 - seat);
        actor.setLife(20, null);
        defender.setLife(2, null);
        Card wurm = addCard("Craw Wurm", actor);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", defender);
        // Direct constructed-zone insertion does not run the native ETB loyalty replacement.
        jace.setCounters(CounterType.getType("LOYALTY"), Integer.parseInt(jace.getBaseLoyalty()));
        addCard("Forest", defender);
        boolean frenzy = family.equals("concealed-library-frenzy");
        if (frenzy) addCard("Experimental Frenzy", defender);

        // Create identities in the same order; change only the concealed permutation.
        ZoneType zone = family.contains("hand") ? ZoneType.Hand : ZoneType.Library;
        Card fog = addCardToZone("Fog", defender, zone);
        Card forest = addCardToZone("Forest", defender, zone);
        defender.getZone(zone).setCards(fogFirst ? List.of(fog, forest) : List.of(forest, fog));
        if (zone == ZoneType.Hand) {
            addCardToZone("Forest", defender, ZoneType.Library);
            // Hand order alone cannot test identity use. Move the other named card into
            // the library, preserving the complete deck multiset and all public counts.
            Card hidden = fogFirst ? forest : fog;
            defender.getZone(ZoneType.Hand).remove(hidden);
            defender.getZone(ZoneType.Library).add(hidden);
        }
        addCardToZone("Forest", actor, ZoneType.Library);
        addCardToZone("Forest", actor, ZoneType.Library);
        game.getAction().checkStateEffects(true);
        require(!game.isGameOver(), "Fixture must remain a nonterminal native position");
        require(jace.isInPlay() && jace.getCurrentLoyalty() == 3, "Canonical Jace must survive native state actions");
        require(!fog.getView().canBeShownTo(actor.getView()), "Fog must not be visible to the attacker");
        require(!forest.getView().canBeShownTo(actor.getView()), "Concealed Forest must not be visible to attacker");
        require(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).isEmpty(),
                "No prior reveal memory allowed");
        if (frenzy) {
            Card top = defender.getCardsIn(ZoneType.Library).getFirst();
            require(top.getView().canBeShownTo(defender.getView()), "Frenzy must grant defender-only top visibility");
            require(!top.getView().canBeShownTo(actor.getView()), "Frenzy must not grant attacker top visibility");
            require(defender.getCardsActivatableInExternalZones(true).contains(top), "Top must be natively playable");
        }
        if (family.equals("revealed-hand")) {
            // Explicit native reveal callback is legitimate knowledge, not a hidden leak.
            ((PlayerControllerAi) actor.getController()).reveal(
                    new CardCollection(defender.getCardsIn(ZoneType.Hand)), ZoneType.Hand, defender,
                    "CONTROLLED-NATIVE public reveal", true);
        }
        Map<String, Object> view = new ActorBoundary(actor).snapshot(game.getView());
        // A fresh matched RNG begins immediately before the actual native decision.
        MyRandom.setRandom(new Random(SEED));
        Combat combat = new Combat(actor);
        require(combat.getDefendingPlaneswalkers().contains(jace), "Native combat must offer Jace as a defender");
        game.getPhaseHandler().setCombat(combat);
        actor.getController().declareAttackers(actor, combat);
        require(combat.getAttackers().size() == 1 && combat.isAttacking(wurm),
                "Native callback must actually declare the one legal attacker");
        GameEntity target = combat.getDefenderByAttacker(wurm);
        String attack = target == defender ? "opponent" : target instanceof Card card ? card.getName() : "unexpected";
        require(!attack.equals("unexpected"), "Unexpected native defender");
        require(!game.isGameOver(), "No game outcome may be manufactured");
        int rngTail = MyRandom.getRandom().nextInt();
        // Inspect the suspect helper only after the callback, so this diagnostic
        // cannot prime its cost evaluator or spell's activating-player field.
        boolean available = ComputerUtil.hasAFogEffect(defender, actor, true);
        return new Decision(view, available, attack, rngTail);
    }

    private void pair(int seat, String family) {
        Decision a = decide(seat, family, true);
        Decision b = decide(seat, family, false);
        System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE", "family", family,
                "seat", seat, "fog_variant", a, "forest_variant", b)));
        require(a.actorView.equals(b.actorView), "Matched actor snapshots must be exactly equal");
        if (family.equals("revealed-hand")) {
            require(a.fogAvailable && !b.fogAvailable, "Native reveal must alter legitimate fog knowledge");
            require(!a.attack.equals(b.attack), "Public-knowledge control must change the actual native decision");
        } else {
            require(a.attack.equals(b.attack), "Concealed variant changed actual native attack defender");
            require(a.rngTail == b.rngTail, "Concealed variant changed ending RNG");
        }
    }

    private static Map<String, Object> origin(Class<?> type) throws Exception {
        String resource = "/" + type.getName().replace('.', '/') + ".class";
        byte[] bytes;
        try (var in = type.getResourceAsStream(resource)) { bytes = in.readAllBytes(); }
        return Map.of("class", type.getName(), "resource", type.getResource(resource).toString(),
                "sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
    }

    public static void main(String[] args) throws Exception {
        NativeFogBoundaryRegression test = new NativeFogBoundaryRegression();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Map<String, Object>> origins = new ArrayList<>();
        List<Class<?>> pinned = List.of(NativeFogBoundaryRegression.class, AITest.class, ActorBoundary.class,
                forge.ai.AiAttackController.class, ComputerUtil.class, PlayerControllerAi.class,
                forge.ai.ComputerUtilCost.class, forge.ai.AiController.class,
                forge.game.player.Player.class, forge.game.zone.PlayerZone.class,
                forge.game.card.CardView.class, forge.game.staticability.StaticAbilityContinuous.class);
        for (Class<?> type : pinned) origins.add(origin(type));
        Files.writeString(Path.of(args[0], "class-origins.json"), JSON.toJson(origins));
        int passed = 0, red = 0, errors = 0;
        for (String family : List.of("concealed-library-frenzy", "concealed-library-no-grant", "concealed-hand", "revealed-hand")) {
            for (int seat = 0; seat < 2; seat++) {
                try {
                    test.pair(seat, family);
                    passed++;
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
        require(origins.equals(after), "Loaded resource bytes/origins changed during execution");
        Files.writeString(Path.of(args[0], "class-origins.after.json"), JSON.toJson(after));
        Files.writeString(Path.of(args[0], "summary.json"), JSON.toJson(Map.of("label", "CONTROLLED-NATIVE",
                "passed", passed, "red", red, "errors", errors, "seed", SEED,
                "profile", "Default", "flat_monte_carlo", false, "filtered_hands", false)));
        System.out.println("SUMMARY PASS=" + passed + " RED=" + red + " ERRORS=" + errors);
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
