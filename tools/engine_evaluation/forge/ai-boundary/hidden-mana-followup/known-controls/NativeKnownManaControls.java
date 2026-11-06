// SPDX-License-Identifier: GPL-3.0-or-later
// Original bounded controls using the Forge Team/Card-Forge engine and AITest helpers.
// https://github.com/Card-Forge/forge at 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain native notices and ../../../LICENSE. Controlled positions, not full games.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.AiCardMemory;
import forge.ai.ComputerUtil;
import forge.ai.ComputerUtilCost;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.deck.Deck;
import forge.game.Game;
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
import forge.game.spellability.SpellAbility;
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
import java.util.Set;

public final class NativeKnownManaControls extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;
    private record Pose(Game game, Player actor, Player owner, Card wurm, Card jace,
                        Card fog, Card esg, Card forest) {}

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private Pose pose(int seat, boolean esgHand, boolean publicMana) {
        MyRandom.setRandom(new Random(SEED));
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("seat" + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "CONTROLLED-NATIVE known mana"));
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO = false;
        game.AI_FLAT_MONTE_CARLO_MAX = false;
        game.AI_FLAT_MONTE_CARLO_LITE = false;
        game.AI_TIMEOUT = 10;
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), owner = game.getPlayers().get(1 - seat);
        require(!((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary native AI required");
        actor.setLife(20, null);
        owner.setLife(2, null);
        Card wurm = addCard("Craw Wurm", actor);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", owner);
        jace.setCounters(CounterType.getType("LOYALTY"), Integer.parseInt(jace.getBaseLoyalty()));
        Card forest = addCard("Forest", owner);
        forest.setTapped(!publicMana);
        Card fog = addCardToZone("Fog", owner, ZoneType.Hand);
        Card esg = addCardToZone("Elvish Spirit Guide", owner, esgHand ? ZoneType.Hand : ZoneType.Library);
        addCardToZone("Forest", owner, esgHand ? ZoneType.Library : ZoneType.Hand);
        addCardToZone("Forest", actor, ZoneType.Library);
        addCardToZone("Forest", actor, ZoneType.Library);
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, actor);
        game.getAction().checkStateEffects(true);
        require(!game.isGameOver() && jace.isInPlay() && jace.getCurrentLoyalty() == 3, "Canonical nonterminal board required");
        require(!fog.getView().canBeShownTo(actor.getView()) && !esg.getView().canBeShownTo(actor.getView()),
                "No current opposing-hand viewing grant");
        require(AiCardMemory.getMemorySet(actor, AiCardMemory.MemorySet.REVEALED_CARDS).isEmpty(), "No initial reveal memory");
        return new Pose(game, actor, owner, wurm, jace, fog, esg, forest);
    }

    private void remembered(int seat) {
        Pose p = pose(seat, true, false);
        ((PlayerControllerAi) p.actor.getController()).reveal(new CardCollection(List.of(p.fog, p.esg)),
                ZoneType.Hand, p.owner, "CONTROLLED-NATIVE legitimate two-card reveal", true);
        require(AiCardMemory.getMemorySet(p.actor, AiCardMemory.MemorySet.REVEALED_CARDS).equals(Set.of(p.fog, p.esg)),
                "Both actual cards, and only those cards, must be legitimately remembered");
        Map<String, Object> view = new ActorBoundary(p.actor).snapshot(p.game.getView());
        Combat combat = new Combat(p.actor);
        p.game.getPhaseHandler().setCombat(combat);
        MyRandom.setRandom(new Random(SEED));
        p.actor.getController().declareAttackers(p.actor, combat);
        int tail = MyRandom.getRandom().nextInt();
        require(combat.getAttackers().size() == 1 && combat.isAttacking(p.wurm)
                && combat.getDefenderByAttacker(p.wurm) == p.jace, "Remembered legal hand mana must still fund known Fog and veto assault");
        boolean available = ComputerUtil.hasAFogEffect(p.owner, p.actor, true);
        require(available && p.esg.isInZone(ZoneType.Hand) && p.fog.isInZone(ZoneType.Hand), "Forecast must retain known mana without actually spending it");
        require(!p.game.isGameOver(), "No manufactured outcome");
        System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE", "family", "legit-remembered-esg", "seat", seat,
                "actor_view", view, "attack", "Jace Beleren", "known_fog_affordable", available, "rng_tail", tail)));
    }

    private void ownerPayment(int seat) {
        for (String input : List.of("esg", "public-forest", "unpayable")) {
            boolean esg = input.equals("esg"), publicMana = input.equals("public-forest");
            Pose p = pose(seat, esg, publicMana);
            Combat combat = new Combat(p.actor);
            p.game.getPhaseHandler().setCombat(combat);
            p.actor.getController().declareAttackers(p.actor, combat);
            require(combat.getAttackers().size() == 1 && combat.isAttacking(p.wurm), "Actual native combat required before own payment");
            SpellAbility spell = p.fog.getFirstSpellAbility();
            spell.setActivatingPlayer(p.owner);
            Map<String, Object> before = new ActorBoundary(p.owner).snapshot(p.game.getView());
            // Matched test-action inputs, not a production RNG restore or repair.
            MyRandom.setRandom(new Random(SEED));
            boolean payable = ComputerUtilCost.canPayCost(spell, p.owner, false);
            boolean cast = ComputerUtil.playStack(spell, p.owner, p.game);
            int tail = MyRandom.getRandom().nextInt();
            require(payable == !input.equals("unpayable") && cast == payable, "Legacy own payability/cast result changed");
            if (cast) {
                require(p.game.getStack().size() == 1 && spell.getHostCard().isInZone(ZoneType.Stack), "Real paid Fog must be on the native stack");
                require(p.esg.isInZone(esg ? ZoneType.Exile : ZoneType.Library), "Native ESG payment/exile state incorrect");
                require(p.forest.isTapped(), "Public Forest payment/tapped state incorrect");
            } else {
                require(p.game.getStack().isEmpty() && p.fog.isInZone(ZoneType.Hand), "Unpayable Fog must not be cast");
                require(before.equals(new ActorBoundary(p.owner).snapshot(p.game.getView())), "Rejected owner cast must preserve actor snapshot");
            }
            require(!p.game.isGameOver(), "Payment control must not resolve a game outcome");
            System.out.println(JSON.toJson(Map.of("label", "NATIVE-LEGACY-PAYMENT", "family", "owner-payment-parity", "seat", seat,
                    "input", input, "payable", payable, "cast", cast, "owner_after", new ActorBoundary(p.owner).snapshot(p.game.getView()),
                    "esg_zone", p.esg.getZone().getZoneType().name(), "rng_tail", tail)));
        }
    }

    private static Map<String, Object> origin(Class<?> type) throws Exception {
        String name = "/" + type.getName().replace('.', '/') + ".class";
        byte[] bytes;
        try (var in = type.getResourceAsStream(name)) { bytes = in.readAllBytes(); }
        return Map.of("class", type.getName(), "resource", type.getResource(name).toString(),
                "sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
    }

    public static void main(String[] args) throws Exception {
        NativeKnownManaControls test = new NativeKnownManaControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Class<?>> classes = List.of(NativeKnownManaControls.class, AITest.class, ActorBoundary.class,
                ComputerUtil.class, ComputerUtilCost.class, forge.ai.ComputerUtilMana.class,
                Class.forName("forge.ai.ComputerUtilCost$1"), forge.ai.AiAttackController.class,
                forge.ai.AiController.class, PlayerControllerAi.class, Player.class,
                forge.game.cost.CostExile.class, forge.game.card.CardView.class);
        List<Map<String, Object>> before = new ArrayList<>();
        for (Class<?> type : classes) before.add(origin(type));
        Files.writeString(Path.of(args[0], "class-origins.json"), JSON.toJson(before));
        int pass = 0, red = 0, errors = 0;
        for (String family : List.of("legit-remembered-esg", "owner-payment-parity")) {
            for (int seat = 0; seat < 2; seat++) {
                try {
                    if (family.equals("legit-remembered-esg")) test.remembered(seat); else test.ownerPayment(seat);
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
        require(before.equals(after), "Loaded resource pins changed during new controls");
        Files.writeString(Path.of(args[0], "class-origins.after.json"), JSON.toJson(after));
        Files.writeString(Path.of(args[0], "summary.json"), JSON.toJson(Map.of("pass", pass, "red", red, "errors", errors,
                "remembered_esg_checks", 2, "owner_payment_checks", 2, "owner_payment_attempts", 6)));
        System.out.println("SUMMARY PASS=" + pass + " RED=" + red + " ERRORS=" + errors);
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
