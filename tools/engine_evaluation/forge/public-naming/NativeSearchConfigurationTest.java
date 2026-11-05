// SPDX-License-Identifier: GPL-3.0-or-later
// Original tests of the Forge Team/Card-Forge native search configuration.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import forge.ai.LobbyPlayerAi;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.player.RegisteredPlayer;
import java.util.List;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class NativeSearchConfigurationTest extends SimulationTest {
    @DataProvider(name="modes")
    public Object[][] modes() { return new Object[][] {{false}, {true}}; }

    @Test(dataProvider="modes")
    public void declaredSearchModeControlsTheRealNativeGame(boolean enabled) {
        List<RegisteredPlayer> players = List.of(
                new RegisteredPlayer(new Deck("A")).setPlayer(new LobbyPlayerAi("A",null)),
                new RegisteredPlayer(new Deck("B")).setPlayer(new LobbyPlayerAi("B",null)));
        Game game = new Match(new GameRules(GameType.Constructed),players,"Search config").createGame();
        game.AI_FLAT_MONTE_CARLO = !enabled;
        game.AI_FLAT_MONTE_CARLO_MAX = true;
        game.AI_FLAT_MONTE_CARLO_LITE = true;
        game.AI_TIMEOUT = 999;
        NativeNameMatchProbe.configureSearch(game,enabled);
        Assert.assertEquals(game.AI_FLAT_MONTE_CARLO,enabled);
        Assert.assertFalse(game.AI_FLAT_MONTE_CARLO_MAX);
        Assert.assertFalse(game.AI_FLAT_MONTE_CARLO_LITE);
        Assert.assertEquals(game.AI_TIMEOUT,5);
    }
}
