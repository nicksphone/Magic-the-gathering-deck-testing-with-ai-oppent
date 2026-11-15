// SPDX-License-Identifier: GPL-3.0-or-later
// Original bounded controls using Forge Team/Card-Forge at
// 61e9442c433711a82258daca3236f936a1d6f70e. See NOTICE.md.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.ComputerUtil;
import forge.ai.ComputerUtilCost;
import forge.ai.ComputerUtilMana;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.ComboPlan;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
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
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class NativeHeldPieceOwnerControls extends AITest {
    private static final Gson JSON = new Gson();
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    private static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    private static String rngState(Random rng) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) { out.writeObject(rng); }
        return sha(bytes.toByteArray());
    }
    private void owner(int seat) throws Exception {
        for (String input : List.of("held-piece", "ordinary-hand", "public-mana")) {
            boolean held = !input.equals("ordinary-hand"), publicMana = input.equals("public-mana");
            MyRandom.setRandom(new Random(2026110601L));
            Random rng = MyRandom.getRandom();
            List<RegisteredPlayer> registered = new ArrayList<>();
            for (int i = 0; i < 2; i++) {
                LobbyPlayerAi lobby = new LobbyPlayerAi("seat" + i, null);
                lobby.setAiProfile("Default");
                registered.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
            }
            GameRules rules = new GameRules(GameType.Constructed);
            rules.setAllowCheatShuffle(false);
            Game game = new Game(registered, rules, new Match(rules, registered, "CONTROLLED-NATIVE owner held piece"));
            game.setAge(GameStage.Play);
            game.AI_FLAT_MONTE_CARLO = false;
            game.AI_FLAT_MONTE_CARLO_MAX = false;
            game.AI_FLAT_MONTE_CARLO_LITE = false;
            game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
            Player owner = game.getPlayers().get(seat), other = game.getPlayers().get(1 - seat);
            require(!((PlayerControllerAi) owner.getController()).getAi().usesSimulation(), "Ordinary controller required");
            owner.setLife(20, null); other.setLife(20, null);
            Card familiar = addCard("Skirge Familiar", owner);
            familiar.setTapped(true);
            Card swamp = addCard("Swamp", owner);
            swamp.setTapped(!publicMana);
            Card darkness = addCardToZone("Darkness", owner, ZoneType.Hand);
            Card payoff = addCardToZone("Tendrils of Agony", owner, held ? ZoneType.Hand : ZoneType.Library);
            Card forest = addCardToZone("Forest", owner, held ? ZoneType.Library : ZoneType.Hand);
            addCardToZone("Forest", other, ZoneType.Library);
            game.getPhaseHandler().devModeSet(PhaseType.MAIN1, owner);
            game.getAction().checkStateEffects(true);
            require(darkness.getView().canBeShownTo(owner.getView()), "Own hand is legitimately visible");
            SpellAbility sa = darkness.getFirstSpellAbility();
            sa.setActivatingPlayer(owner);
            Map<String, Object> view = new ActorBoundary(owner).snapshot(game.getView());
            String before = rngState(rng);
            boolean legacy = ComputerUtilCost.canPayCost(sa, owner, false);
            boolean explicitNull = ComputerUtilCost.canPayCost(sa, owner, false, null);
            boolean allKnown = ComputerUtilCost.canPayCost(sa, owner, false, c -> true);
            boolean ownFog = ComputerUtil.hasAFogEffect(owner, owner, false);
            String after = rngState(rng);
            require(legacy == (!held || publicMana), "Native legacy held-piece policy changed");
            require(explicitNull == legacy && allKnown == legacy && ownFog == legacy,
                    "Null, all-known and own-Fog paths must retain legacy affordability");
            require(ComboPlan.holdsKillPiece(owner) == held, "Native own held-piece classifier changed");
            require(MyRandom.getRandom() == rng && view.equals(new ActorBoundary(owner).snapshot(game.getView()))
                    && familiar.isTapped() && swamp.isTapped() == !publicMana && owner.getManaPool().totalMana() == 0
                    && payoff.isInZone(held ? ZoneType.Hand : ZoneType.Library)
                    && forest.isInZone(held ? ZoneType.Library : ZoneType.Hand) && !game.isGameOver(),
                    "Forecast must preserve real native fixture/RNG identity without spending or restoration");
            System.out.println(JSON.toJson(Map.of("label", "CONTROLLED-NATIVE owner held-piece parity", "seat", seat,
                    "input", input, "legacy", legacy, "explicit_null", explicitNull, "all_known", allKnown,
                    "own_fog", ownFog, "owner_view", view, "rng_before", before, "rng_after", after)));
        }
    }
    private static Map<String, Object> origin(Class<?> type) throws Exception {
        String path = "/" + type.getName().replace('.', '/') + ".class";
        try (var in = type.getResourceAsStream(path)) {
            return Map.of("class", type.getName(), "resource", type.getResource(path).toString(), "sha256", sha(in.readAllBytes()));
        }
    }
    public static void main(String[] args) throws Exception {
        NativeHeldPieceOwnerControls test = new NativeHeldPieceOwnerControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Class<?>> pinned = List.of(NativeHeldPieceOwnerControls.class, AITest.class, ActorBoundary.class,
                ComputerUtil.class, ComputerUtilCost.class, Class.forName("forge.ai.ComputerUtilCost$1"),
                ComputerUtilMana.class, ComboPlan.class, PlayerControllerAi.class, MyRandom.class,
                Class.forName("forge.util.MyRandom$CountingRandom"));
        List<Map<String, Object>> before = new ArrayList<>();
        for (Class<?> type : pinned) before.add(origin(type));
        Files.writeString(Path.of(args[0], "class-origins.json"), JSON.toJson(before));
        int pass = 0, red = 0, errors = 0;
        for (int seat = 0; seat < 2; seat++) {
            try { test.owner(seat); pass++; }
            catch (AssertionError failure) { red++; failure.printStackTrace(); }
            catch (Exception failure) { errors++; failure.printStackTrace(); }
        }
        List<Map<String, Object>> after = new ArrayList<>();
        for (Class<?> type : pinned) after.add(origin(type));
        require(before.equals(after), "Loaded class resources changed");
        Files.writeString(Path.of(args[0], "class-origins.after.json"), JSON.toJson(after));
        Files.writeString(Path.of(args[0], "summary.json"), JSON.toJson(Map.of("pass", pass, "red", red,
                "errors", errors, "poses_per_seat", 3, "rng_restores", 0)));
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
