// SPDX-License-Identifier: GPL-3.0-or-later
// Original controlled-native supplement for Card-Forge 61e9442c433711a82258daca3236f936a1d6f70e.
// Forge Team/Card-Forge rules and notices retained; no production policy overrides.
package forge.evaluation;

import com.google.gson.Gson;
import forge.StaticData;
import forge.ai.*;
import forge.card.ICardFace;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.AbilityKey;
import forge.game.ability.ApiType;
import forge.game.card.Card;
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
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;
import java.util.function.Predicate;

public final class NativeFogActivationControls extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;
    private static void need(boolean ok, String reason) {
        if (!ok) throw new IllegalStateException("HARNESS: " + reason);
    }

    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) {
            stream.writeObject(MyRandom.getRandom());
        }
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.toByteArray()));
    }

    private Map<String, Object> supplement(int seat, String scene) throws Exception {
        boolean manifest = scene.startsWith("Manifest");
        // Fresh controlled fixture seed BEFORE constructing this game; never reset after setup/choice.
        MyRandom.setRandom(new Random(SEED + (manifest ? 100 : 200) + seat));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby;
            if (i == seat || manifest) lobby = new LobbyPlayerAi("supplement-seat" + i, null);
            else lobby = new LobbyPlayerAi("supplement-seat" + i, null) {
                @Override public Player createIngamePlayer(Game game, int id) {
                    Player p = new Player(getName(), game, id);
                    PlayerControllerAi controller = new PlayerControllerAi(game, p, this) {
                        @Override public String chooseCardName(SpellAbility sa, Predicate<ICardFace> valid,
                                                               String selector, String prompt) {
                            need(sa.getHostCard().getName().equals("Pithing Needle"), "Canonical Needle name input only");
                            need(valid.test(StaticData.instance().getCommonCards().getFaceByName("Fog")), "Fog is a legal card name");
                            return "Fog";
                        }
                        @Override public String chooseCardName(SpellAbility sa, List<ICardFace> faces, String prompt) {
                            need(sa.getHostCard().getName().equals("Pithing Needle")
                                    && faces.stream().anyMatch(face -> face.getName().equals("Fog")), "Legal offered name");
                            return "Fog";
                        }
                    };
                    controller.getAi().setUseSimulation(null);
                    p.setFirstController(controller);
                    return p;
                }
            };
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED Fog preservation"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player observer = game.getPlayers().get(seat), defender = game.getPlayers().get(1 - seat);
        need(observer.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) observer.getController()).getAi().usesSimulation(), "Unmodified heuristic Default actor");
        observer.setLife(20, null);
        defender.setLife(2, null);
        Card wurm = addCard("Craw Wurm", observer);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", defender);
        jace.setCounters(CounterType.getType("LOYALTY"), 3);
        addCardToZone("Forest", observer, ZoneType.Library);
        addCardToZone("Forest", observer, ZoneType.Library);
        Card source;
        if (manifest) {
            addCardToZone("Fog", defender, ZoneType.Library);
            addCardToZone("Forest", defender, ZoneType.Library);
            Card scroll = addCard("Scroll of Fate", defender);
            Card hidden = addCardToZone(scene.equals("ManifestFrog") ? "Spore Frog" : "Forest", defender, ZoneType.Hand);
            game.getPhaseHandler().devModeSet(PhaseType.MAIN2, defender);
            SpellAbility ability = scroll.getSpellAbilities().stream()
                    .filter(sa -> sa.getApi() == ApiType.Manifest).findFirst().orElseThrow();
            ability.setActivatingPlayer(defender);
            // Trusted setup action, NOT an AI policy pass: actual canonical ability pays its tap cost.
            need(ComputerUtil.playStack(ability, defender, game), "Native Manifest setup must pay and enter stack");
            need(scroll.isTapped() && game.getStack().size() == 1, "Actual Scroll tap payment and stack");
            game.getStack().resolveStack();
            game.getAction().checkStateEffects(true);
            source = defender.getCardsIn(ZoneType.Battlefield).stream().filter(Card::isFaceDown).findFirst().orElseThrow();
            need(source.isManifested() && source.getId() == hidden.getId()
                    && defender.getCardsIn(ZoneType.Hand).isEmpty(), "Actual canonical Manifest moved the sole selected card");
            need(source.getNetPower() == 2 && source.getNetToughness() == 2, "Native manifest characteristics");
            source.setTapped(true); // Controlled blocker isolation, not a natural turn-history claim.
            need(!source.getView().canFaceDownBeShownTo(observer.getView()), "Manifest identity unknown to observer");
        } else {
            addCard("Future Sight", defender);
            Card forest = addCard("Forest", defender);
            forest.setTapped(scene.equals("InstantUnfunded"));
            source = addCardToZone("Fog", defender, ZoneType.Library);
            addCardToZone("Forest", defender, ZoneType.Library);
            Card pending = addCardToZone("Pithing Needle", defender, ZoneType.Hand);
            Card needle = game.getAction().moveToPlay(pending, defender, null, AbilityKey.newMap());
            need(needle.isInPlay() && needle.getNamedCards().contains("Fog"), "Native Needle entry names the instant");
        }
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, observer);
        game.getAction().checkStateEffects(true);
        need(!game.isGameOver() && jace.getCurrentLoyalty() == 3, "Nonterminal controlled board");
        if (!manifest) need(source.getView().canBeShownTo(observer.getView()), "Future Sight genuinely exposes the instant");
        Map<String, Object> before = new ActorBoundary(observer).snapshot(game.getView());
        String rngBefore = rng();
        Combat combat = new Combat(observer);
        game.getPhaseHandler().setCombat(combat);
        observer.getController().declareAttackers(observer, combat);
        String rngAfter = rng();
        need(combat.getAttackers().size() == 1 && combat.isAttacking(wurm), "One genuine Default attack callback");
        GameEntity defenderChosen = combat.getDefenderByAttacker(wurm);
        String attack = defenderChosen == defender ? "opponent" : defenderChosen == jace ? "Jace Beleren" : "unexpected";
        Map<String, Object> diagnosticBefore = new ActorBoundary(observer).snapshot(game.getView());
        String queryBefore = rng();
        boolean forecast = ComputerUtil.hasAFogEffect(defender, observer, true);
        boolean ownerForecast = ComputerUtil.hasAFogEffect(defender, defender, false);
        String queryAfter = rng();
        Map<String, Object> diagnosticAfter = new ActorBoundary(observer).snapshot(game.getView());
        boolean expected = scene.equals("InstantFunded");
        List<String> failed = new ArrayList<>();
        if (forecast != expected || ownerForecast != expected) failed.add("Knowledge/owner affordability preservation");
        if (!attack.equals(expected ? "Jace Beleren" : "opponent")) failed.add("Default attack preservation");
        if (!diagnosticBefore.equals(diagnosticAfter) || !queryBefore.equals(queryAfter)) failed.add("Diagnostic actor/RNG mutation");
        if (game.isGameOver()) failed.add("Unexpected manufactured outcome");
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("label", "NEW-CONTROLLED-PRESERVATION"); row.put("seat", seat); row.put("scene", scene);
        row.put("actor_view", before); row.put("rng_before_attack", rngBefore); row.put("rng_after_attack", rngAfter);
        row.put("attack", attack); row.put("fog_forecast", forecast); row.put("owner_forecast", ownerForecast);
        row.put("diagnostic_actor_view_unchanged", diagnosticBefore.equals(diagnosticAfter));
        row.put("diagnostic_rng_unchanged", queryBefore.equals(queryAfter));
        row.put("rng_before_queries", queryBefore); row.put("rng_after_queries", queryAfter);
        row.put("failed", failed); row.put("status", failed.isEmpty() ? "PASS" : "CONTROL_FAIL");
        return row;
    }

    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED));
        NativeFogActivationAudit original = new NativeFogActivationAudit();
        original.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        Method check = NativeFogActivationAudit.class.getDeclaredMethod("runCase", int.class, String.class);
        check.setAccessible(true);
        int oldPass = 0, oldRed = 0, errors = 0, newPass = 0, controlFail = 0, pairPass = 0;
        for (int seat = 0; seat < 2; seat++) for (String scene : List.of("NeedleFrog", "NeedleOther", "NeedleLeaves", "Absent")) {
            try {
                @SuppressWarnings("unchecked") Map<String, Object> row = (Map<String, Object>) check.invoke(original, seat, scene);
                Files.writeString(out.resolve("original-" + seat + "-" + scene + ".private.json"), JSON.toJson(row) + "\n");
                if (row.get("status").equals("PASS")) oldPass++;
                else if (row.get("status").equals("POLICY_RED")) oldRed++;
                else controlFail++;
            } catch (Throwable error) {
                errors++; (error instanceof InvocationTargetException ? error.getCause() : error).printStackTrace(System.err);
            }
        }
        NativeFogActivationControls test = new NativeFogActivationControls();
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> frog = null, forest = null;
            for (String scene : List.of("ManifestFrog", "ManifestForest", "InstantFunded", "InstantUnfunded")) {
                try {
                    Map<String, Object> row = test.supplement(seat, scene);
                    Files.writeString(out.resolve("supplement-" + seat + "-" + scene + ".private.json"), JSON.toJson(row) + "\n");
                    if (row.get("status").equals("PASS")) newPass++; else controlFail++;
                    if (scene.equals("ManifestFrog")) frog = row;
                    if (scene.equals("ManifestForest")) forest = row;
                } catch (Throwable error) { errors++; error.printStackTrace(System.err); }
            }
            boolean same = frog != null && forest != null && frog.get("actor_view").equals(forest.get("actor_view"))
                    && frog.get("rng_before_attack").equals(forest.get("rng_before_attack"))
                    && frog.get("rng_after_attack").equals(forest.get("rng_after_attack"))
                    && frog.get("attack").equals(forest.get("attack"));
            Files.writeString(out.resolve("privacy-pair-" + seat + ".json"), JSON.toJson(Map.of("pass", same,
                    "label", "actual same-view/incoming-and-ending-RNG hidden manifest pair")) + "\n");
            if (same) pairPass++; else controlFail++;
        }
        Map<String, Object> summary = Map.of("original8", Map.of("pass", oldPass, "policy_red", oldRed),
                "supplement8", Map.of("pass", newPass), "privacy_pairs_pass", pairPass,
                "control_fail", controlFail, "harness_errors", errors, "natural_game", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary));
        System.exit(errors != 0 || controlFail != 0 ? 2 : oldRed != 0 ? 1 : 0);
    }
}
