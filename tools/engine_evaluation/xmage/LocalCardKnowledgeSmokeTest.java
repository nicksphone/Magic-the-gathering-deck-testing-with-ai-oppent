package org.mage.test.cards.compatibility;

import mage.abilities.keyword.HasteAbility;
import mage.constants.PhaseStep;
import mage.constants.Zone;
import org.junit.Test;
import org.mage.test.player.TestPlayer;
import org.mage.test.serverside.base.CardTestPlayerBase;

/**
 * Original local compatibility assertions, not upstream-authored tests.
 * Uses the XMage contributors' native engine and test API under their MIT license.
 * Source: https://github.com/magefree/mage
 * Pinned revision: 987fd4e9c73e9f113e235f8d8f98628f2d391667.
 * Existing upstream source, tests, copyright notices and LICENSE remain unchanged.
 */
public class LocalCardKnowledgeSmokeTest extends CardTestPlayerBase {

    private TestPlayer actor(boolean secondSeat) {
        TestPlayer actor = secondSeat ? playerB : playerA;
        // Select the starting player through the native test harness on each seat.
        activePlayer = actor;
        setStrictChooseMode(true);
        return actor;
    }

    private TestPlayer opponent(boolean secondSeat) {
        return secondSeat ? playerA : playerB;
    }

    private void cloudblazer(boolean secondSeat) {
        TestPlayer actor = actor(secondSeat);
        addCard(Zone.BATTLEFIELD, actor, "Plains", 3);
        addCard(Zone.BATTLEFIELD, actor, "Island", 2);
        addCard(Zone.HAND, actor, "Cloudblazer");
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, actor, "Cloudblazer");
        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();
        assertPermanentCount(actor, "Cloudblazer", 1);
        assertPowerToughness(actor, "Cloudblazer", 2, 2);
        assertLife(actor, 22);
        assertHandCount(actor, 2);
        assertLife(opponent(secondSeat), 20);
        assertHandCount(opponent(secondSeat), 0);
    }

    private void growthSpiral(boolean secondSeat) {
        TestPlayer actor = actor(secondSeat);
        addCard(Zone.BATTLEFIELD, actor, "Island");
        addCard(Zone.BATTLEFIELD, actor, "Forest");
        addCard(Zone.HAND, actor, "Growth Spiral");
        addCard(Zone.HAND, actor, "Plains");
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, actor, "Growth Spiral");
        setChoice(actor, true);
        setChoice(actor, "Plains");
        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();
        assertPermanentCount(actor, "Plains", 1);
        assertGraveyardCount(actor, "Growth Spiral", 1);
        assertHandCount(actor, 1);
        assertHandCount(opponent(secondSeat), 0);
    }

    private void rayOfCommand(boolean secondSeat) {
        TestPlayer actor = actor(secondSeat);
        TestPlayer opponent = opponent(secondSeat);
        addCard(Zone.BATTLEFIELD, actor, "Island", 4);
        addCard(Zone.HAND, actor, "Ray of Command");
        addCard(Zone.BATTLEFIELD, opponent, "Silvercoat Lion", 1, true);
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, actor, "Ray of Command", "Silvercoat Lion");
        checkPermanentCount("initial control", 1, PhaseStep.BEGIN_COMBAT,
                actor, "Silvercoat Lion", 1);
        checkPermanentTapped("untapped by Ray", 1, PhaseStep.BEGIN_COMBAT,
                actor, "Silvercoat Lion", false, 1);
        checkAbility("haste from Ray", 1, PhaseStep.BEGIN_COMBAT,
                actor, "Silvercoat Lion", HasteAbility.class, true);
        attack(1, actor, "Silvercoat Lion", opponent);
        setStopAt(1, PhaseStep.END_COMBAT);
        execute();
        assertPermanentCount(actor, "Silvercoat Lion", 1);
        assertPermanentCount(opponent, "Silvercoat Lion", 0);
        assertLife(opponent, 18);
        assertGraveyardCount(actor, "Ray of Command", 1);
        // This test stops before cleanup: no control-return/loss-trigger claim.
    }

    private void inspiration(boolean secondSeat) {
        TestPlayer actor = actor(secondSeat);
        TestPlayer recipient = opponent(secondSeat);
        addCard(Zone.BATTLEFIELD, actor, "Island", 4);
        addCard(Zone.HAND, actor, "Inspiration");
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, actor, "Inspiration", recipient);
        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();
        assertHandCount(actor, 0);
        assertHandCount(recipient, 2);
        assertGraveyardCount(actor, "Inspiration", 1);
    }

    @Test public void cloudblazerSeatA() { cloudblazer(false); }
    @Test public void cloudblazerSeatB() { cloudblazer(true); }
    @Test public void growthSpiralSeatA() { growthSpiral(false); }
    @Test public void growthSpiralSeatB() { growthSpiral(true); }
    @Test public void rayOfCommandSeatA() { rayOfCommand(false); }
    @Test public void rayOfCommandSeatB() { rayOfCommand(true); }
    @Test public void inspirationSeatA() { inspiration(false); }
    @Test public void inspirationSeatB() { inspiration(true); }
}
