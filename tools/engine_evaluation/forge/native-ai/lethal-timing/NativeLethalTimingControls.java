// SPDX-License-Identifier: GPL-3.0-or-later
// Canonical controlled positions using Forge Team/Card-Forge native rules and AI.
// Upstream 61e9442c433711a82258daca3236f936a1d6f70e; see ../NOTICE.md.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Full, unmodified canonical card bodies; constructed positions, not natural games. */
public final class NativeLethalTimingControls extends AITest {
    private final List<Map<String, Object>> results = new ArrayList<>();

    private void check(int seat, String scenario, String spellName, boolean expectCast, PhaseType phase) {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("canonical-seat" + i, null) {
                @Override public Player createIngamePlayer(Game game, int id) {
                    Player player = new Player(getName(), game, id);
                    player.setFirstController(new PublicNameController(game, player, this, Map.of()));
                    return player;
                }
            };
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "Canonical lethal timing control"));
        game.setAge(GameStage.Play);
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        actor.setLife(2, null);
        enemy.setLife(scenario.equals("nonlethal") ? 10 : scenario.equals("nonlethal-endstep") ? 6
                : scenario.equals("partial-prevention") ? 4 : 1, null);
        game.getPhaseHandler().devModeSet(phase, phase == PhaseType.END_OF_TURN ? enemy : actor);
        game.getPhaseHandler().onStackResolved();
        fillLibrary(actor, 8);
        fillLibrary(enemy, 8);
        List<Card> lands = new ArrayList<>();
        lands.add(addCard("Mountain", actor));
        lands.add(addCard("Plains", actor));
        if (!scenario.equals("tax-unpayable")) lands.add(addCard("Mountain", actor));
        // Thalia is present even in the positive: the winning spell must pay the native tax.
        addCard("Thalia, Guardian of Thraben", enemy);
        switch (scenario) {
            case "partial-prevention": addCard("Urza's Armor", enemy); break;
            case "full-prevention": addCard("Glacial Chasm", enemy); break;
            case "hexproof": addCard("Leyline of Sanctity", enemy); break;
            case "cannot-lose": addCard("Platinum Angel", enemy); break;
            case "zero-life-not-loss": addCard("Phyrexian Unlife", enemy); break;
            case "own-backlash": addCard("Eidolon of the Great Revel", actor); break;
            default: break;
        }
        boolean activated = spellName.equals("Goblin Fireslinger");
        Card card = addCardToZone(spellName, actor, activated ? ZoneType.Battlefield : ZoneType.Hand);
        if (activated) card.setSickness(false);
        if (scenario.equals("infect-not-life-lethal")) addCard("Phyresis", actor).attachToEntity(card, null);
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        if (scenario.equals("infect-not-life-lethal")) {
            require(card.isInfectDamage(enemy), "Canonical aura did not grant infect");
        }
        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        List<SpellAbility> selected = controller.chooseSpellAbilityToPlay();
        SpellAbility spell = selected == null || selected.isEmpty() ? null : selected.get(0);
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("seat", seat);
        row.put("scenario", scenario);
        row.put("spell", spellName);
        row.put("phase", phase.name());
        row.put("expect_cast", expectCast);
        row.put("selected", spell == null ? "PASS" : spell.getHostCard().getName());
        results.add(row);
        if (!expectCast) {
            require(spell == null, "Safety/nonlethal control unexpectedly selected " + row);
            require(card.isInZone(activated ? ZoneType.Battlefield : ZoneType.Hand) && game.getStack().isEmpty()
                    && !card.isTapped()
                    && lands.stream().noneMatch(Card::isTapped), "Decline must not pay or move the card");
            row.put("passed", true);
            return;
        }
        require(spell != null && spell.getHostCard().getId() == card.getId(),
                "Native controller withheld the canonical winning spell: " + row);
        require(controller.playWithRollback(spell, null), "Native payment/targeting rejected selected spell");
        require(card.isInZone(activated ? ZoneType.Battlefield : ZoneType.Stack) && !game.getStack().isEmpty(),
                "Chosen spell/ability did not enter native stack");
        long tapped = lands.stream().filter(Card::isTapped).count();
        row.put("paid_lands", tapped);
        require(tapped == (activated ? 0 : 3), "Native spell must consume three lands including tax; ability no mana");
        if (activated) require(card.isTapped(), "Native activated tap cost was not paid");
        int resolutions = 0;
        while (!game.getStack().isEmpty() && !game.isGameOver() && resolutions++ < 8) {
            game.getStack().resolveStack();
            game.getAction().checkStateEffects(true);
        }
        row.put("enemy_life", enemy.getLife());
        row.put("actor_life", actor.getLife());
        row.put("native_game_over", game.isGameOver());
        row.put("native_actor_won", actor.hasWon());
        if (scenario.equals("nonlethal-endstep")) {
            require(enemy.getLife() == 2 && actor.getLife() == 2 && !game.isGameOver(),
                    "Existing nonlethal end-step policy/payment/resolution changed");
        } else {
            require(enemy.getLife() <= 0 && actor.getLife() == 2, "Lethal damage did not resolve safely");
            require(game.isGameOver() && actor.hasWon() && enemy.hasLost(), "Native rules did not award the win");
        }
        row.put("passed", true);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        NativeLethalTimingControls test = new NativeLethalTimingControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        int failures = 0, errors = 0;
        for (int seat : new int[]{0, 1}) {
            for (String scenario : List.of("lethal-mode", "lethal-instant", "nonlethal", "partial-prevention",
                    "full-prevention", "hexproof", "tax-unpayable", "cannot-lose", "zero-life-not-loss", "own-backlash",
                    "lethal-activated", "infect-not-life-lethal", "nonlethal-endstep")) {
                try {
                    test.check(seat, scenario, scenario.equals("lethal-instant") ? "Skullcrack"
                            : scenario.equals("lethal-activated") || scenario.equals("infect-not-life-lethal")
                            ? "Goblin Fireslinger" : "Boros Charm",
                            scenario.startsWith("lethal-") || scenario.equals("nonlethal-endstep"),
                            scenario.equals("nonlethal-endstep") ? PhaseType.END_OF_TURN : PhaseType.MAIN1);
                } catch (AssertionError failure) {
                    failures++;
                    System.err.println("RED seat=" + seat + " scenario=" + scenario + ": " + failure.getMessage());
                } catch (Throwable failure) {
                    errors++;
                    failure.printStackTrace();
                }
            }
        }
        Map<String, Object> summary = Map.of("label", "CANONICAL-NATIVE-CONTROLLED-POSITIONS",
                "passed", 26 - failures - errors, "failures", failures, "errors", errors,
                "natural_games", 0, "cases", test.results);
        String json = new Gson().toJson(summary);
        Files.writeString(Path.of(args[0], "summary.json"), json + "\n");
        System.out.println(json);
        System.exit(failures == 0 && errors == 0 ? 0 : 1);
    }
}
