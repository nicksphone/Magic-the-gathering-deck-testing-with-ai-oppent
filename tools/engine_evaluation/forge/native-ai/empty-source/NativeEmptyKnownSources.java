// SPDX-License-Identifier: GPL-3.0-or-later
// Original synthetic API-boundary checks using Forge Team/Card-Forge native work.
// Forge 61e9442c433711a82258daca3236f936a1d6f70e; retain ../NOTICE.md and ../../LICENSE.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.AITest;
import forge.ai.ComputerUtilMana;
import forge.ai.LobbyPlayerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.mana.ManaCostBeingPaid;
import forge.card.mana.ManaCostShard;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Synthetic AI preference metadata, not canonical Oracle or a full game. */
public final class NativeEmptyKnownSources extends AITest {
    private void check(int seat, boolean allow) {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("synthetic-seat" + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "SYNTHETIC chooser boundary"));
        game.setAge(GameStage.Play);
        Player payer = game.getPlayers().get(seat);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, payer);
        Card land = addCard("Forest", payer);
        Card host = addCardToZone("Fog", payer, ZoneType.Hand);
        SpellAbility spell = host.getFirstSpellAbility(), mana = land.getManaAbilities().get(0);
        spell.setActivatingPlayer(payer);
        mana.setActivatingPlayer(payer);
        spell.putParam("AIManaPref", "Treasure");
        Map<String, Object> before = new ActorBoundary(payer).snapshot(game.getView());
        SpellAbility chosen;
        try {
            chosen = ComputerUtilMana.chooseManaAbility(new ManaCostBeingPaid(spell.getPayCosts().getTotalMana()),
                    spell, payer, ManaCostShard.GREEN, List.of(mana), true, card -> allow);
        } catch (RuntimeException failure) {
            throw new AssertionError("Scoped rejection must return null before preference indexing", failure);
        }
        if (chosen != (allow ? mana : null)) throw new AssertionError("Incorrect scoped source choice");
        if (allow && ComputerUtilMana.chooseManaAbility(new ManaCostBeingPaid(spell.getPayCosts().getTotalMana()),
                spell, payer, ManaCostShard.GREEN, List.of(mana), true) != chosen) {
            throw new AssertionError("Known-source and legacy choice must agree");
        }
        if (!before.equals(new ActorBoundary(payer).snapshot(game.getView())) || land.isTapped()
                || !host.isInZone(ZoneType.Hand) || !game.getStack().isEmpty()) {
            throw new AssertionError("Forecast must not pay or mutate native card/zone state");
        }
    }

    public static void main(String[] args) throws Exception {
        NativeEmptyKnownSources test = new NativeEmptyKnownSources();
        test.initializeModel();
        int passed = 0, red = 0;
        for (int seat : new int[]{0, 1}) {
            for (boolean allow : new boolean[]{false, true}) {
                try {
                    test.check(seat, allow);
                    passed++;
                } catch (AssertionError failure) {
                    red++;
                    System.err.println("RED seat=" + seat + " allow=" + allow);
                    failure.printStackTrace();
                }
            }
        }
        String result = new Gson().toJson(Map.of("label", "SYNTHETIC-NATIVE-CHOOSER", "passed", passed,
                "red", red, "errors", 0, "full_games", 0));
        Files.writeString(Path.of(args[0], "summary.json"), result);
        System.out.println(result);
        System.exit(red == 0 ? 0 : 1);
    }
}
