// SPDX-License-Identifier: GPL-3.0-or-later
// Original MTG Deck Testing Lab evaluation assertions, using Card-Forge's engine
// and test helpers. Upstream work: Forge Team and Card-Forge contributors,
// https://github.com/Card-Forge/forge, commit 61e9442c433711a82258daca3236f936a1d6f70e.
// Their original notices are retained; this test uses the accompanying GPL LICENSE,
// not the application's root Apache-2.0 license.
// Constructed boards test native paid spell simulation, not complete-game AI strength.
package forge.ai.simulation;

import forge.game.Game;
import forge.game.card.Card;
import forge.game.keyword.Keyword;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class ExternalCardKnowledgeTest extends SimulationTest {
    @DataProvider(name = "seats")
    public Object[][] seats() {
        return new Object[][] {{0}, {1}};
    }

    private Game position(int seat) {
        Game game = initAndCreateGame();
        for (Player player : game.getPlayers()) {
            for (int i = 0; i < 12; i++) {
                addCardToZone("Island", player, ZoneType.Library);
            }
        }
        Player player = game.getPlayers().get(seat);
        addCards("Island", 4, player);
        addCard("Plains", player);
        addCard("Forest", player);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, player);
        return game;
    }

    private Game cast(Player player, Card card, Object target) {
        SpellAbility spell = card.getSpellAbilities().get(0);
        spell.setActivatingPlayer(player);
        if (target instanceof Player) {
            spell.getTargets().add((Player) target);
        } else if (target instanceof Card) {
            spell.getTargets().add((Card) target);
        }
        GameSimulator simulator = createSimulator(player);
        simulator.simulateSpellAbility(spell);
        return simulator.getSimulatedGameState();
    }

    private long tappedLands(Player player) {
        return player.getCardsIn(ZoneType.Battlefield).stream()
                .filter(card -> card.isLand() && card.isTapped()).count();
    }

    @Test(dataProvider = "seats")
    public void inspirationDrawsTwoForTheChosenPlayer(int seat) {
        Game game = position(seat);
        Player player = game.getPlayers().get(seat);
        Card spell = addCardToZone("Inspiration", player, ZoneType.Hand);
        Game resolved = cast(player, spell, player);
        Player actor = resolved.getPlayer(player.getId());
        Assert.assertEquals(actor.getCardsIn(ZoneType.Hand).size(), 2);
        Assert.assertEquals(resolved.getPlayers().get(1-seat).getCardsIn(ZoneType.Hand).size(), 0);
        Assert.assertEquals(tappedLands(actor), 4L);
    }

    @Test(dataProvider = "seats")
    public void cloudblazerGainsTwoAndDrawsTwo(int seat) {
        Game game = position(seat);
        Player player = game.getPlayers().get(seat);
        Card spell = addCardToZone("Cloudblazer", player, ZoneType.Hand);
        Game resolved = cast(player, spell, null);
        Player actor = resolved.getPlayer(player.getId());
        Assert.assertEquals(actor.getLife(), 22);
        Assert.assertEquals(actor.getCardsIn(ZoneType.Hand).size(), 2);
        Assert.assertNotNull(findCardWithName(resolved, "Cloudblazer"));
        Assert.assertEquals(tappedLands(actor), 5L);
    }

    @Test(dataProvider = "seats")
    public void growthSpiralDrawsThenCanPutLandIntoPlay(int seat) {
        Game game = position(seat);
        Player player = game.getPlayers().get(seat);
        Card spell = addCardToZone("Growth Spiral", player, ZoneType.Hand);
        addCardToZone("Island", player, ZoneType.Hand);
        Game resolved = cast(player, spell, null);
        Player actor = resolved.getPlayer(player.getId());
        Assert.assertEquals(actor.getCardsIn(ZoneType.Battlefield).size(), 7);
        Assert.assertEquals(actor.getCardsIn(ZoneType.Hand).size(), 1);
        Assert.assertEquals(tappedLands(actor), 2L);
    }

    @Test(dataProvider = "seats")
    public void rayUntapsAndGrantsTemporaryControlAndHaste(int seat) {
        Game game = position(seat);
        Player player = game.getPlayers().get(seat);
        Card creature = addCard("Grizzly Bears", game.getPlayers().get(1-seat));
        creature.setTapped(true);
        Card spell = addCardToZone("Ray of Command", player, ZoneType.Hand);
        Game resolved = cast(player, spell, creature);
        Card borrowed = findCardWithName(resolved, "Grizzly Bears");
        Assert.assertEquals(borrowed.getController().getId(), player.getId());
        Assert.assertFalse(borrowed.isTapped());
        Assert.assertTrue(borrowed.hasKeyword(Keyword.HASTE));
        Assert.assertEquals(tappedLands(resolved.getPlayer(player.getId())), 4L);
        // Loss-of-control delayed-tap timing is outside this initial-resolution test.
    }
}
