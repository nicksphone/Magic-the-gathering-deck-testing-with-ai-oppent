// SPDX-License-Identifier: GPL-3.0-or-later
// Original controlled diagnostic using Card-Forge 61e9442c433711a82258daca3236f936a1d6f70e.
// Canonical card bodies unchanged. Not natural gameplay or a production policy fix.
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.function.Predicate;

public final class NativeFogActivationAudit extends AITest {
    private static final Gson JSON = new Gson();
    private static final long SEED = 2026110601L;
    private static void need(boolean ok, String why) {
        if (!ok) throw new IllegalStateException("HARNESS: " + why);
    }

    private Map<String, Object> runCase(int seat, String scene) throws Exception {
        String named = scene.equals("NeedleOther") ? "Craw Wurm" : "Spore Frog";
        int[] nameCalls = {0};
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby;
            if (i == seat) lobby = new LobbyPlayerAi("observer-seat" + i, null);
            else lobby = new LobbyPlayerAi("defender-seat" + i, null) {
                @Override public Player createIngamePlayer(Game game, int id) {
                    Player p = new Player(getName(), game, id);
                    PlayerControllerAi controller = new PlayerControllerAi(game, p, this) {
                        @Override public String chooseCardName(SpellAbility ability, Predicate<ICardFace> valid,
                                                               String selector, String prompt) {
                            need(ability.getHostCard().getName().equals("Pithing Needle"), "Only canonical Needle setup choice overridden");
                            ICardFace face = StaticData.instance().getCommonCards().getFaceByName(named);
                            need(face != null && valid.test(face), "Declared card name must be a legal native choice");
                            nameCalls[0]++;
                            return named;
                        }
                        @Override public String chooseCardName(SpellAbility ability, List<ICardFace> faces, String prompt) {
                            need(ability.getHostCard().getName().equals("Pithing Needle")
                                    && faces.stream().anyMatch(face -> face.getName().equals(named)), "Legal finite name choice");
                            nameCalls[0]++;
                            return named;
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
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED Fog activation " + scene));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player observer = game.getPlayers().get(seat), defender = game.getPlayers().get(1 - seat);
        need(observer.getController().getClass() == PlayerControllerAi.class, "Attacker controller must remain native Default");
        need(!((PlayerControllerAi) observer.getController()).getAi().usesSimulation(), "Native heuristic actor required");
        observer.setLife(20, null);
        defender.setLife(2, null);
        Card wurm = addCard("Craw Wurm", observer);
        wurm.setSickness(false);
        Card jace = addCard("Jace Beleren", defender);
        jace.setCounters(CounterType.getType("LOYALTY"), Integer.parseInt(jace.getBaseLoyalty()));
        Card frog = addCard("Spore Frog", defender);
        frog.setTapped(true); // No tap cost: removes blocking, not the canonical sacrifice ability.
        Card hiddenFog = addCardToZone("Fog", defender, ZoneType.Library);
        addCardToZone("Forest", defender, ZoneType.Library);
        addCardToZone("Forest", observer, ZoneType.Library);
        addCardToZone("Forest", observer, ZoneType.Library);
        Card needle = null;
        if (!scene.equals("Absent")) {
            Card pending = addCardToZone("Pithing Needle", defender, ZoneType.Hand);
            // Controlled board entry, not a paid cast: actual native ETB replacement names the card.
            needle = game.getAction().moveToPlay(pending, defender, null, AbilityKey.newMap());
            need(needle != null && needle.isInPlay() && needle.getNamedCards().contains(named), "Genuine native named Needle entry");
            need(nameCalls[0] == 1, "Exactly one native name-choice callback");
            if (scene.equals("NeedleLeaves")) {
                needle = game.getAction().moveToGraveyard(needle, null);
                need(needle.isInZone(ZoneType.Graveyard), "Needle genuinely departed battlefield");
            }
        } else need(nameCalls[0] == 0, "Absent case must not create Needle");
        game.getPhaseHandler().devModeSet(PhaseType.COMBAT_DECLARE_ATTACKERS, observer);
        game.getAction().checkStateEffects(true);
        need(!game.isGameOver() && wurm.isInPlay() && frog.isInPlay() && jace.getCurrentLoyalty() == 3,
                "Canonical nonterminal attack board");
        need(!hiddenFog.getView().canBeShownTo(observer.getView()), "Library identity must remain private");
        need(frog.getView().canBeShownTo(observer.getView()), "Fog permanent is genuinely public");
        Map<String, Object> beforeAttack = new ActorBoundary(observer).snapshot(game.getView());
        long beforeDecision = MyRandom.callCount();
        Combat combat = new Combat(observer);
        need(combat.getDefendingPlaneswalkers().contains(jace), "Actual native defender menu contains Jace");
        game.getPhaseHandler().setCombat(combat);
        // First and only Default attack decision. No earlier Fog, restriction or cost probes.
        observer.getController().declareAttackers(observer, combat);
        long afterDecision = MyRandom.callCount();
        need(combat.getAttackers().size() == 1 && combat.isAttacking(wurm), "Exactly one native Wurm attack");
        GameEntity target = combat.getDefenderByAttacker(wurm);
        String attack = target == defender ? "opponent" : target == jace ? "Jace Beleren" : "unexpected";
        need(!attack.equals("unexpected") && !game.isGameOver(), "No forced winner or unknown target");

        // Diagnostic queries begin only after the actual decision is retained.
        Map<String, Object> beforeDiagnostics = new ActorBoundary(observer).snapshot(game.getView());
        long beforeQueries = MyRandom.callCount();
        SpellAbility fog = frog.getSpellAbilities().stream().filter(a -> a.getApi() == ApiType.Fog).findFirst().orElseThrow();
        boolean activationLegal = fog.checkRestrictions(frog, defender);
        boolean forecast = ComputerUtil.hasAFogEffect(defender, observer, true);
        long afterQueries = MyRandom.callCount();
        Map<String, Object> afterDiagnostics = new ActorBoundary(observer).snapshot(game.getView());
        boolean hiddenPrivateAfter = !hiddenFog.getView().canBeShownTo(observer.getView());
        boolean viewPure = beforeDiagnostics.equals(afterDiagnostics);
        boolean rngPure = beforeQueries == afterQueries;
        boolean expectedAvailable = !scene.equals("NeedleFrog");
        String expectedAttack = expectedAvailable ? "Jace Beleren" : "opponent";
        List<String> controlFailures = new ArrayList<>(), policyFailures = new ArrayList<>();
        if (activationLegal != expectedAvailable) controlFailures.add("Native activation restriction differs from declared public prohibition");
        if (!viewPure) controlFailures.add("Diagnostic queries changed actor view");
        if (!rngPure) controlFailures.add("Diagnostic queries consumed RNG; no pure-query claim");
        if (!hiddenPrivateAfter) controlFailures.add("Concealed library card became visible");
        if (forecast != expectedAvailable) policyFailures.add("Fog forecast disagrees with public activation legality");
        if (!attack.equals(expectedAttack)) policyFailures.add("Actual attack defender disagrees with declared lethal/public-Fog expectation");
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("label", "CONTROLLED-NATIVE-ACTIVATION-DIAGNOSTIC");
        row.put("seat", seat); row.put("scene", scene); row.put("native_attack_callbacks", 1);
        row.put("name_callbacks", nameCalls[0]); row.put("declared_name", needle == null ? "absent" : named);
        row.put("needle_zone", needle == null ? "absent" : needle.getZone().getZoneType().name());
        row.put("native_activation_legal", activationLegal); row.put("fog_forecast", forecast);
        row.put("attack", attack); row.put("expected_attack", expectedAttack);
        row.put("actor_view_before_attack", beforeAttack); row.put("actor_view_after_attack", beforeDiagnostics);
        row.put("diagnostic_actor_view_unchanged", viewPure); row.put("diagnostic_rng_unchanged", rngPure);
        row.put("rng_before_decision", beforeDecision); row.put("rng_after_decision", afterDecision);
        row.put("rng_before_queries", beforeQueries); row.put("rng_after_queries", afterQueries);
        row.put("hidden_library_identity_still_private", hiddenPrivateAfter);
        row.put("native_ai_timeout", game.AI_TIMEOUT); row.put("native_game_over", game.isGameOver());
        row.put("controls_failed", controlFailures); row.put("policy_failed", policyFailures);
        row.put("status", !controlFailures.isEmpty() ? "CONTROL_FAIL" : policyFailures.isEmpty() ? "PASS" : "POLICY_RED");
        return row;
    }

    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED)); // Declared once before model initialization, never restored/reset.
        NativeFogActivationAudit audit = new NativeFogActivationAudit();
        audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, control = 0, errors = 0;
        for (int seat = 0; seat < 2; seat++) for (String scene : List.of("NeedleFrog", "NeedleOther", "NeedleLeaves", "Absent")) {
            try {
                Map<String, Object> row = audit.runCase(seat, scene);
                Files.writeString(out.resolve("case-" + seat + "-" + scene + ".private.json"), JSON.toJson(row) + "\n");
                switch ((String) row.get("status")) {
                    case "PASS" -> pass++;
                    case "POLICY_RED" -> red++;
                    default -> control++;
                }
                System.out.println(row.get("status") + " seat=" + seat + " scene=" + scene
                        + " attack=" + row.get("attack") + " legal=" + row.get("native_activation_legal")
                        + " forecast=" + row.get("fog_forecast"));
            } catch (Throwable error) {
                errors++;
                error.printStackTrace(System.err);
                Files.writeString(out.resolve("case-" + seat + "-" + scene + ".error.txt"), error.toString() + "\n");
            }
        }
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(Map.of("cases", 8, "pass", pass,
                "policy_red", red, "control_fail", control, "harness_errors", errors,
                "natural_game", false, "seed_once_before_model", SEED)) + "\n");
        System.exit(errors != 0 || control != 0 ? 2 : red != 0 ? 1 : 0);
    }
}
