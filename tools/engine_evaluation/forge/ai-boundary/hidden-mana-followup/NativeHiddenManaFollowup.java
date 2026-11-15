// SPDX-License-Identifier: GPL-3.0-or-later
// Original bounded native cost-channel follow-up using Forge Team/Card-Forge work.
// https://github.com/Card-Forge/forge at 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain the native notices and ../../LICENSE. No production changes or natural games.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.AiCardMemory;
import forge.ai.ComputerUtil;
import forge.ai.ComputerUtilMana;
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

public final class NativeHiddenManaFollowup extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;
    private record Decision(Map<String, Object> actorView, String attack, int rngTail,
                            boolean knownFogAffordable, boolean concealedManaSourceListed) {}

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private Decision decide(int seat, boolean esgInHand, boolean tapped) {
        MyRandom.setRandom(new Random(SEED));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-NATIVE concealed mana"));
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO = false;
        game.AI_FLAT_MONTE_CARLO_MAX = false;
        game.AI_FLAT_MONTE_CARLO_LITE = false;
        game.AI_TIMEOUT = 10;
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat);
        Player defender = game.getPlayers().get(1 - seat);
        require(!((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary native heuristic required");
        actor.setLife(20, null);
        defender.setLife(2, null);
        Card wurm = addCard("Craw Wurm", actor);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", defender);
        jace.setCounters(CounterType.getType("LOYALTY"), Integer.parseInt(jace.getBaseLoyalty()));
        Card land = addCard("Forest", defender);
        land.setTapped(tapped);
        Card fog = addCardToZone("Fog", defender, ZoneType.Hand);
        // Keep native identity creation order and the full deck multiset fixed.
        Card esg = addCardToZone("Elvish Spirit Guide", defender, esgInHand ? ZoneType.Hand : ZoneType.Library);
        Card other = addCardToZone("Forest", defender, esgInHand ? ZoneType.Library : ZoneType.Hand);
        addCardToZone("Forest", actor, ZoneType.Library);
        addCardToZone("Forest", actor, ZoneType.Library);
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, actor);
        game.getAction().checkStateEffects(true);
        require(!game.isGameOver() && jace.isInPlay() && jace.getCurrentLoyalty() == 3, "Canonical nonterminal board required");
        for (Card c : List.of(fog, esg, other)) {
            require(!c.getView().canBeShownTo(actor.getView()), "No current attacker viewing grant allowed");
        }
        require(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).isEmpty(), "No initial reveal memory");
        // Reveal ONLY Fog. Revealing the whole hand would disclose the mana source
        // and would not be an imperfect-information invariance test.
        ((PlayerControllerAi) actor.getController()).reveal(new CardCollection(List.of(fog)),
                ZoneType.Hand, defender, "CONTROLLED-NATIVE Fog-only reveal", true);
        require(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).equals(java.util.Set.of(fog)),
                "Only the legitimately revealed Fog may be remembered");
        Map<String, Object> view = new ActorBoundary(actor).snapshot(game.getView());
        MyRandom.setRandom(new Random(SEED));
        Combat combat = new Combat(actor);
        require(combat.getDefendingPlaneswalkers().contains(jace), "Native combat must retain Jace defender");
        game.getPhaseHandler().setCombat(combat);
        actor.getController().declareAttackers(actor, combat);
        require(combat.getAttackers().size() == 1 && combat.isAttacking(wurm), "Native AI must actually declare the attacker");
        GameEntity target = combat.getDefenderByAttacker(wurm);
        String attack = target == defender ? "opponent" : target == jace ? "Jace Beleren" : "unexpected";
        require(!attack.equals("unexpected"), "Unexpected native attack defender");
        int tail = MyRandom.getRandom().nextInt();
        // Inspect the cost channel only AFTER the actual decision and RNG sample.
        boolean affordable = ComputerUtil.hasAFogEffect(defender, actor, true);
        boolean listed = ComputerUtilMana.getAvailableManaSources(defender, true).contains(esg);
        require(esg.isInZone(esgInHand ? ZoneType.Hand : ZoneType.Library) && fog.isInZone(ZoneType.Hand),
                "Test-only affordability must not exile or cast a card");
        require(land.isTapped() == tapped && defender.getManaPool().totalMana() == 0,
                "No actual mana payment or fabricated pool allowed");
        require(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).equals(java.util.Set.of(fog)),
                "Native decision must not learn the concealed mana identity through a reveal");
        require(!game.isGameOver(), "No terminal outcome may be manufactured");
        return new Decision(view, attack, tail, affordable, listed);
    }

    private void hiddenPair(int seat, boolean publicMana) {
        Decision a = decide(seat, true, !publicMana);
        Decision b = decide(seat, false, !publicMana);
        String family = publicMana ? "public-mana-masks-concealed-variant" : "strict-concealed-mana";
        System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE", "family", family, "seat", seat,
                "variant_a", a, "variant_b", b)));
        require(a.actorView.equals(b.actorView), "Matched actor snapshots must be exactly equal");
        require(a.attack.equals(b.attack), "Concealed mana identity changed actual native attack defender");
        require(a.rngTail == b.rngTail, "Concealed mana identity changed ending RNG");
        if (publicMana) {
            require(a.knownFogAffordable && b.knownFogAffordable, "Public untapped Forest must fund known Fog in both variants");
            require(a.attack.equals("Jace Beleren"), "Publicly payable known Fog must still veto lethal assault");
        }
    }

    private void publicTappedControl(int seat) {
        Decision untapped = decide(seat, false, false);
        Decision tapped = decide(seat, false, true);
        System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE", "family", "public-mana-tapped-toggle",
                "seat", seat, "untapped", untapped, "tapped", tapped)));
        require(!untapped.actorView.equals(tapped.actorView), "Public tapped status must be visible");
        require(untapped.knownFogAffordable && !tapped.knownFogAffordable, "Native affordability must follow the public Forest state");
        require(untapped.attack.equals("Jace Beleren") && tapped.attack.equals("opponent"), "Public mana/tapped control must change actual attack decision");
    }

    private static Map<String, Object> origin(Class<?> type) throws Exception {
        String resource = "/" + type.getName().replace('.', '/') + ".class";
        byte[] bytes;
        try (var in = type.getResourceAsStream(resource)) { bytes = in.readAllBytes(); }
        return Map.of("class", type.getName(), "resource", type.getResource(resource).toString(),
                "sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
    }

    public static void main(String[] args) throws Exception {
        NativeHiddenManaFollowup test = new NativeHiddenManaFollowup();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Class<?>> pinned = List.of(NativeHiddenManaFollowup.class, AITest.class, ActorBoundary.class,
                ComputerUtil.class, ComputerUtilMana.class, forge.ai.ComputerUtilCost.class,
                forge.ai.AiAttackController.class, forge.ai.AiController.class, PlayerControllerAi.class,
                Player.class, forge.game.card.CardView.class, forge.game.zone.PlayerZone.class,
                forge.game.cost.CostExile.class);
        List<Map<String, Object>> before = new ArrayList<>();
        for (Class<?> type : pinned) before.add(origin(type));
        Files.writeString(Path.of(args[0], "class-origins.json"), JSON.toJson(before));
        int pass = 0, red = 0, errors = 0;
        for (String family : List.of("strict-concealed-mana", "public-mana-masks-concealed-variant", "public-mana-tapped-toggle")) {
            for (int seat = 0; seat < 2; seat++) {
                try {
                    if (family.equals("public-mana-tapped-toggle")) test.publicTappedControl(seat);
                    else test.hiddenPair(seat, family.equals("public-mana-masks-concealed-variant"));
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
        require(before.equals(after), "Loaded class resources changed during follow-up");
        Files.writeString(Path.of(args[0], "class-origins.after.json"), JSON.toJson(after));
        Files.writeString(Path.of(args[0], "summary.json"), JSON.toJson(Map.of("pass", pass, "red", red, "errors", errors,
                "strict_checks", 2, "public_controls", 4, "native_attack_decisions", 12)));
        System.out.println("SUMMARY PASS=" + pass + " RED=" + red + " ERRORS=" + errors);
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
