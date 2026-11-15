// SPDX-License-Identifier: GPL-3.0-or-later
// Original controlled-native tests using the Forge Team/Card-Forge engine and AITest helpers.
// https://github.com/Card-Forge/forge at 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and ../LICENSE. No natural games, policy overrides, or forced outcomes.
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

public final class NativeFogKnowledgeControls extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;
    private record Pose(Game game, Player observer, Player defender, Card wurm, Card jace,
                        Card fog, Card forest) {}
    private record Decision(Map<String, Object> actorView, boolean fogAvailable, String attack, int rngTail) {}

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private Pose pose(int seat, String family, boolean fogFirst, boolean payable) {
        MyRandom.setRandom(new Random(SEED));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-NATIVE fog knowledge"));
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO = false;
        game.AI_FLAT_MONTE_CARLO_MAX = false;
        game.AI_FLAT_MONTE_CARLO_LITE = false;
        game.AI_TIMEOUT = 10;
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player observer = game.getPlayers().get(seat);
        Player defender = game.getPlayers().get(1 - seat);
        require(!((PlayerControllerAi) observer.getController()).getAi().usesSimulation(), "Heuristic native AI required");
        observer.setLife(20, null);
        defender.setLife(2, null);
        Card wurm = addCard("Craw Wurm", observer);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", defender);
        jace.setCounters(CounterType.getType("LOYALTY"), Integer.parseInt(jace.getBaseLoyalty()));
        addCard("Forest", defender).setTapped(!payable);
        if (family.startsWith("public-top")) addCard("Future Sight", defender);
        if (family.equals("visible-hand")) addCard("Telepathy", observer);
        if (family.equals("owner-private-top")) addCard("Experimental Frenzy", defender);
        if (family.equals("public-permanent")) {
            // Sacrifice has no tap cost; tapping prevents this 1/1 being a blocker.
            addCard("Spore Frog", defender).setTapped(true);
        }
        ZoneType zone = family.contains("hand") ? ZoneType.Hand : ZoneType.Library;
        Card fog = addCardToZone("Fog", defender, zone);
        Card forest = addCardToZone("Forest", defender, zone);
        defender.getZone(zone).setCards(fogFirst ? List.of(fog, forest) : List.of(forest, fog));
        if (zone == ZoneType.Hand) {
            Card moved = fogFirst ? forest : fog;
            defender.getZone(zone).remove(moved);
            defender.getZone(ZoneType.Library).add(moved);
            addCardToZone("Forest", defender, ZoneType.Library);
        }
        addCardToZone("Forest", observer, ZoneType.Library);
        addCardToZone("Forest", observer, ZoneType.Library);
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, observer);
        game.getAction().checkStateEffects(true);
        require(!game.isGameOver() && jace.isInPlay() && jace.getCurrentLoyalty() == 3, "Nonterminal canonical board required");
        require(AiCardMemory.getMemorySet(observer, AiCardMemory.MemorySet.REVEALED_CARDS).isEmpty(), "No reveal-memory shortcut");
        if (family.startsWith("public-top")) {
            Card top = defender.getCardsIn(ZoneType.Library).getFirst();
            require(top.getView().canBeShownTo(observer.getView()), "Future Sight must publicly expose the actual top card");
            require(defender.getCardsActivatableInExternalZones(true).contains(top), "Public top must be a native external option");
        } else if (family.equals("visible-hand")) {
            Card hand = defender.getCardsIn(ZoneType.Hand).getFirst();
            require(hand.getView().canBeShownTo(observer.getView()), "Telepathy must expose the actual hand without reveal memory");
        } else {
            require(!fog.getView().canBeShownTo(observer.getView()), "Fog must remain private from the opponent");
        }
        return new Pose(game, observer, defender, wurm, jace, fog, forest);
    }

    private Decision attack(int seat, String family, boolean fogFirst) {
        Pose p = pose(seat, family, fogFirst, !family.equals("public-top-unpayable"));
        Map<String, Object> view = new ActorBoundary(p.observer).snapshot(p.game.getView());
        MyRandom.setRandom(new Random(SEED));
        Combat combat = new Combat(p.observer);
        require(combat.getDefendingPlaneswalkers().contains(p.jace), "Native defender menu must retain Jace");
        p.game.getPhaseHandler().setCombat(combat);
        p.observer.getController().declareAttackers(p.observer, combat);
        require(combat.getAttackers().size() == 1 && combat.isAttacking(p.wurm), "Native callback must declare Craw Wurm");
        GameEntity target = combat.getDefenderByAttacker(p.wurm);
        String attack = target == p.defender ? "opponent" : target == p.jace ? "Jace Beleren" : "unexpected";
        require(!attack.equals("unexpected") && !p.game.isGameOver(), "No unknown defender or forced outcome");
        int tail = MyRandom.getRandom().nextInt();
        boolean known = ComputerUtil.hasAFogEffect(p.defender, p.observer, true);
        return new Decision(view, known, attack, tail);
    }

    private void pair(int seat, String family) {
        Decision fog = attack(seat, family, true);
        Decision forest = attack(seat, family, false);
        System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE", "family", family, "seat", seat,
                "fog_variant", fog, "forest_variant", forest)));
        if (family.equals("public-permanent")) {
            require(fog.fogAvailable && forest.fogAvailable, "Public sacrificial Fog permanent must remain known");
            require(fog.attack.equals("Jace Beleren") && forest.attack.equals("Jace Beleren"), "Public permanent must veto lethal assault");
            require(fog.actorView.equals(forest.actorView) && fog.rngTail == forest.rngTail, "Hidden permutation must not alter public-permanent decision context/RNG");
        } else if (family.equals("public-top-unpayable")) {
            require(!fog.fogAvailable && !forest.fogAvailable, "Visibility must not bypass the native mana cost");
            require(fog.attack.equals("opponent") && forest.attack.equals("opponent"), "Unpayable public Fog must not veto assault");
            require(fog.rngTail == forest.rngTail, "Unpayable alternatives must retain matched decision RNG");
            require(!fog.actorView.equals(forest.actorView), "Publicly different top cards must not be redacted as equal");
        } else {
            require(fog.fogAvailable && !forest.fogAvailable, "Currently visible Fog must be known without remembered reveals");
            require(fog.attack.equals("Jace Beleren") && forest.attack.equals("opponent"), "Visible Fog must change the actual native attack defender");
            require(!fog.actorView.equals(forest.actorView), "The currently visible identities must appear in actor snapshots");
        }
    }

    private void owner(int seat, String family) {
        for (boolean payable : List.of(true, false)) {
            for (boolean fogFirst : List.of(true, false)) {
                Pose p = pose(seat, family, fogFirst, payable);
                Card selected = family.equals("owner-hand") ? p.defender.getCardsIn(ZoneType.Hand).getFirst()
                        : p.defender.getCardsIn(ZoneType.Library).getFirst();
                require(selected.getView().canBeShownTo(p.defender.getView()), "Native owner knowledge required");
                require(!selected.getView().canBeShownTo(p.observer.getView()), "Owner-only card must remain hidden to opponent");
                if (family.equals("owner-private-top")) {
                    require(p.defender.getCardsActivatableInExternalZones(true).contains(selected), "Owner private top must be a native external option");
                }
                Map<String, Object> before = new ActorBoundary(p.defender).snapshot(p.game.getView());
                MyRandom.setRandom(new Random(SEED));
                boolean result = ComputerUtil.hasAFogEffect(p.defender, p.defender, false);
                int tail = MyRandom.getRandom().nextInt();
                require(before.equals(new ActorBoundary(p.defender).snapshot(p.game.getView())), "Knowledge query must not mutate actor view");
                System.out.println(JSON.toJson(Map.of("label", "NATIVE-HELPER-CONTROL", "family", family, "seat", seat,
                        "payable", payable, "fog_first", fogFirst, "actor_view", before, "result", result, "rng_tail", tail)));
                require(result == (payable && fogFirst), "Owner checkingOther=false must retain private knowledge and native mana costs");
            }
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
        NativeFogKnowledgeControls test = new NativeFogKnowledgeControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Class<?>> classes = List.of(NativeFogKnowledgeControls.class, AITest.class, ActorBoundary.class,
                ComputerUtil.class, forge.ai.AiAttackController.class, forge.ai.AiController.class,
                PlayerControllerAi.class, forge.ai.ComputerUtilCost.class, Player.class,
                forge.game.zone.PlayerZone.class, forge.game.card.CardView.class,
                forge.game.staticability.StaticAbilityContinuous.class);
        List<Map<String, Object>> before = new ArrayList<>();
        for (Class<?> type : classes) before.add(origin(type));
        Files.writeString(Path.of(args[0], "class-origins.json"), JSON.toJson(before));
        int pass = 0, red = 0, errors = 0;
        for (String family : List.of("public-top-payable", "public-top-unpayable", "visible-hand", "public-permanent", "owner-hand", "owner-private-top")) {
            for (int seat = 0; seat < 2; seat++) {
                try {
                    if (family.startsWith("owner-")) test.owner(seat, family); else test.pair(seat, family);
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
        for (Class<?> type : classes) after.add(origin(type));
        require(before.equals(after), "Loaded class resources changed during controls");
        Files.writeString(Path.of(args[0], "class-origins.after.json"), JSON.toJson(after));
        Files.writeString(Path.of(args[0], "summary.json"), JSON.toJson(Map.of("pass", pass, "red", red, "errors", errors,
                "attack_pairs", 8, "owner_helper_checks", 4, "owner_helper_invocations", 16)));
        System.out.println("SUMMARY PASS=" + pass + " RED=" + red + " ERRORS=" + errors);
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
