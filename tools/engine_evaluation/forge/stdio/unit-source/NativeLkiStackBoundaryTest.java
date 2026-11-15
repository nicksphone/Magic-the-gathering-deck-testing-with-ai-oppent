// SPDX-License-Identifier: GPL-3.0-or-later
// Native-object fixtures, not paid games or strength evidence. Uses Card-Forge's
// retained LKI APIs; upstream Forge Team/Card-Forge attribution is preserved.
package forge.evaluation;

import forge.ai.simulation.SimulationTest;
import forge.game.Game;
import forge.game.card.Card;
import forge.game.card.CardCopyService;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.SpellAbilityStackInstance;
import forge.game.zone.ZoneType;
import forge.trackable.TrackableProperty;
import java.util.Map;
import java.util.List;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class NativeLkiStackBoundaryTest extends SimulationTest {
    @DataProvider(name="seats") public Object[][] seats() { return new Object[][] {{0},{1}}; }

    private SpellAbilityStackInstance push(Game game, Card source, Player controller) {
        Card template=addCard("Prodigal Pyromancer",controller);
        SpellAbility ability=template.getSpellAbilities().stream().filter(s->!s.isSpell()).findFirst().orElseThrow().copy(source,true);
        ability.setActivatingPlayer(controller);
        ability.getTargets().add(game.getPlayers().get(1-game.getPlayers().indexOf(controller)));
        game.getStack().add(ability);
        return game.getStack().iterator().next();
    }

    @Test(dataProvider="seats") public void retainedPublicBattlefieldSourceProjectsOnlyThroughExactCurrentStack(int seat) {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(seat),owner=game.getPlayers().get(1-seat);
        Card original=addCard("Prodigal Pyromancer",owner);
        Card lki=CardCopyService.getLKICopy(original);
        Assert.assertTrue(lki.isLKI());Assert.assertNull(lki.getView().getZone());
        Assert.assertEquals(lki.getLastKnownZone().getZoneType(),ZoneType.Battlefield);
        var entry=push(game,lki,actor);ActorBoundary boundary=new ActorBoundary(actor);
        Assert.assertSame(entry.getView().getSourceCard(),lki.getView());
        Map<?,?> display=(Map<?,?>)boundary.describe(entry.getView());
        Map<?,?> source=(Map<?,?>)display.get("source");
        Assert.assertEquals(source.get("card_id"),lki.getId());
        Assert.assertEquals(source.get("controller_id"),owner.getId(),"Source controller is not the ability activator");
        Assert.assertEquals(((Map<?,?>)source.get("face")).get("name"),"Prodigal Pyromancer");
        Assert.assertEquals(((java.util.List<?>)boundary.snapshot(game.getView()).get("stack")).size(),1);
        lki.setTapped(true);Assert.assertEquals(source.get("tapped"),Boolean.FALSE,"Previously projected scalars are detached");
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.describe(lki.getView()));
        game.getStack().remove(entry);
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.describe(entry.getView()));
    }

    @Test(dataProvider="seats") public void privateOriginAndFacedownRetainedSourcesRemainFailClosed(int seat) {
        for(ZoneType zone:new ZoneType[]{ZoneType.Hand,ZoneType.Library,ZoneType.Exile,ZoneType.Battlefield}) {
            Game game=initAndCreateGame();Player actor=game.getPlayers().get(seat),opponent=game.getPlayers().get(1-seat);
            Card original=addCardToZone("Willbender",opponent,zone);
            if(zone==ZoneType.Battlefield) Assert.assertTrue(original.turnFaceDown(true));
            Card lki=CardCopyService.getLKICopy(original);var entry=push(game,lki,opponent);
            Assert.assertNull(lki.getView().getZone());
            ActorBoundary boundary=new ActorBoundary(actor);
            Assert.expectThrows(IllegalArgumentException.class,()->boundary.describe(entry.getView()));
            Assert.expectThrows(IllegalArgumentException.class,()->boundary.snapshot(game.getView()));
        }
    }

    @Test(dataProvider="seats") public void nonLkiSourceOnGenuineStackStillRejects(int seat) {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(seat);
        Card source=addCard("Prodigal Pyromancer",actor);
        source.setZone(null);Assert.assertFalse(source.isLKI());
        var entry=push(game,source,actor);ActorBoundary boundary=new ActorBoundary(actor);
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.describe(entry.getView()));
    }

    @Test(dataProvider="seats") public void mismatchedSourceViewOnGenuineStackRejects(int seat) {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(seat);
        var entry=push(game,addCard("Prodigal Pyromancer",actor),actor);
        Card unrelated=addCard("Grizzly Bears",actor);
        entry.getView().set(TrackableProperty.SourceCard,unrelated.getView());
        ActorBoundary boundary=new ActorBoundary(actor);
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.describe(entry.getView()));
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.snapshot(game.getView()));
    }

    @Test(dataProvider="seats") public void sameIdNativeSourceRebindingInvalidatesOfferedAnswer(int seat) {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(seat);
        Card original=addCard("Prodigal Pyromancer",actor);
        Card first=CardCopyService.getLKICopy(original),second=CardCopyService.getLKICopy(original);
        Assert.assertNotSame(first.getView(),second.getView());Assert.assertEquals(first.getId(),second.getId());
        var entry=push(game,first,actor);ActorBoundary boundary=new ActorBoundary(actor);
        Map<String,Object> question=boundary.offer("stack",List.of(entry.getView()),1,1);
        String request=(String)question.get("request_id");
        String token=(String)((Map<?,?>)((List<?>)question.get("choices")).get(0)).get("token");
        entry.getSpellAbility().setHostCard(second);
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.answer(actor,request,List.of(token)));
        entry.getSpellAbility().setHostCard(first);
        Assert.assertSame(boundary.answer(actor,request,List.of(token)).get(0),entry.getView());
    }

    @Test(dataProvider="seats") public void lkiWithoutSavedOriginRejects(int seat) {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(seat);
        Card original=addCard("Prodigal Pyromancer",actor);original.setZone(null);
        Card lki=CardCopyService.getLKICopy(original);Assert.assertTrue(lki.isLKI());Assert.assertNull(lki.getLastKnownZone());
        var entry=push(game,lki,actor);ActorBoundary boundary=new ActorBoundary(actor);
        Assert.expectThrows(IllegalArgumentException.class,()->boundary.describe(entry.getView()));
    }
}
