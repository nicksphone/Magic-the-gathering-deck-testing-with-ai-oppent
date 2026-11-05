// SPDX-License-Identifier: GPL-3.0-or-later
// Original paired-information tests using the Forge Team/Card-Forge engine/AI.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.util.List;
import java.util.Map;
import java.util.Random;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class NativeNameInformationTest extends SimulationTest {
    private static final Gson JSON = new Gson();

    @DataProvider(name = "spellsAndSeats")
    public Object[][] spellsAndSeats() {
        return new Object[][] {{"Cabal Therapy",0},{"Cabal Therapy",1},{"Predict",0},{"Predict",1}};
    }
    @DataProvider(name = "seats")
    public Object[][] seats() { return new Object[][] {{0},{1}}; }

    private record Scene(Game game, Player actor, Player opponent, SpellAbility spell) { }
    private record Result(String actorInput, String name, int paid, int actorHand, int opposingHand,
                          int graveyard, int ownLibrary, int opposingLibrary) { }

    private Deck deck(String name, Map<String,Integer> cards) {
        Deck deck = new Deck(name);
        cards.forEach((card,count) -> deck.getMain().add(card,count));
        Assert.assertEquals(deck.getMain().countAll(),60);
        return deck;
    }

    private LobbyPlayerAi lobby(String name, Map<Integer,Map<String,Integer>> disclosed) {
        LobbyPlayerAi lobby = new LobbyPlayerAi(name,null) {
            @Override public Player createIngamePlayer(Game game, int id) {
                Player player = new Player(getName(),game,id);
                player.setFirstController(new PublicNameController(game,player,this,disclosed));
                return player;
            }
        };
        lobby.setAiProfile("Default");
        return lobby;
    }

    private Scene scene(String spellName, int seat, boolean swap) {
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);
        MyRandom.setRandom(new Random(29172371));
        String land = spellName.equals("Cabal Therapy") ? "Swamp" : "Island";
        Map<String,Integer> own = Map.of(spellName,4,land,56);
        Map<String,Integer> opposing = Map.of("Counterspell",4,"Lightning Bolt",4,"Island",52);
        Map<Integer,Map<String,Integer>> disclosed = seat==0 ? Map.of(0,own,1,opposing) : Map.of(0,opposing,1,own);
        RegisteredPlayer first = new RegisteredPlayer(deck("A",disclosed.get(0))).setPlayer(lobby("A",disclosed));
        RegisteredPlayer second = new RegisteredPlayer(deck("B",disclosed.get(1))).setPlayer(lobby("B",disclosed));
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Match match = new Match(rules,List.of(first,second),"Public deck list information test");
        Game game = new Game(List.of(first,second),rules,match);
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO=false;
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1,actor);
        int mana = spellName.equals("Cabal Therapy") ? 1 : 2;
        for (int i=0;i<mana;i++) addCard(land,actor);
        Card spell = addCardToZone(spellName,actor,ZoneType.Hand);
        for (int i=0;i<3;i++) addCardToZone(spellName,actor,ZoneType.Library);
        for (int i=0;i<56-mana;i++) addCardToZone(land,actor,ZoneType.Library);
        for (int i=0;i<4;i++) addCardToZone(swap?"Counterspell":"Lightning Bolt",opponent,ZoneType.Hand);
        for (int i=0;i<4;i++) addCardToZone(swap?"Lightning Bolt":"Counterspell",opponent,ZoneType.Library);
        for (int i=0;i<52;i++) addCardToZone("Island",opponent,ZoneType.Library);
        Assert.assertEquals(actor.getAllCards().size(),60);
        Assert.assertEquals(opponent.getAllCards().size(),60);
        SpellAbility ability = spell.getFirstSpellAbility();
        ability.setActivatingPlayer(actor);
        for (SpellAbility part=ability;part!=null;part=part.getSubAbility()) {
            if (part.usesTargeting()) { part.resetTargets(); part.getTargets().add(opponent); }
        }
        return new Scene(game,actor,opponent,ability);
    }

    private Result cast(Scene scene) {
        String input = JSON.toJson(new ActorBoundary(scene.actor()).snapshot(scene.game().getView()));
        Assert.assertTrue(ComputerUtil.playStack(scene.spell(),scene.actor(),scene.game()),"Real native cost payment must succeed");
        Assert.assertFalse(scene.game().getStack().isEmpty(),"A real spell must be waiting on the stack");
        scene.game().getStack().resolveStack();
        Assert.assertTrue(scene.game().getStack().isEmpty());
        String name = scene.actor().getNamedCard();
        Assert.assertFalse(name.isBlank(),"The actual resolution must call the native naming controller");
        int paid = (int) scene.actor().getCardsIn(ZoneType.Battlefield).stream().filter(Card::isTapped).count();
        Result result = new Result(input,name,paid,scene.actor().getCardsIn(ZoneType.Hand).size(),
                scene.opponent().getCardsIn(ZoneType.Hand).size(),scene.actor().getCardsIn(ZoneType.Graveyard).size(),
                scene.actor().getCardsIn(ZoneType.Library).size(),scene.opponent().getCardsIn(ZoneType.Library).size());
        System.out.println("@@NATIVE_NAME_RESULT "+JSON.toJson(Map.of("seat",scene.actor().getId(),
                "spell",scene.spell().getHostCard().getName(),"chosen_name",name,"paid",paid,
                "actor_hand",result.actorHand(),"opposing_hand",result.opposingHand(),"graveyard",result.graveyard())));
        return result;
    }

    @Test(dataProvider="spellsAndSeats")
    public void blindNameDoesNotDependOnUnseenHandLibraryPartition(String spell,int seat) {
        Result first = cast(scene(spell,seat,false));
        Result second = cast(scene(spell,seat,true));
        Assert.assertEquals(first.paid(),spell.equals("Cabal Therapy")?1:2);
        Assert.assertEquals(second.paid(),first.paid());
        Assert.assertEquals(first.graveyard(),1);
        Assert.assertEquals(second.graveyard(),1);
        Assert.assertEquals(first.actorInput(),second.actorInput(),"Actual actor-visible bytes are identical before the cast");
        Assert.assertEquals(first.name(),second.name(),"A blind deterministic name must not disclose an unseen partition");
    }

    @Test(dataProvider="seats")
    public void genuineRevealedHandKnowledgeStillGuidesThePaidDiscard(int seat) {
        Scene scene = scene("Cabal Therapy",seat,true);
        scene.actor().getController().reveal(scene.opponent().getCardsIn(ZoneType.Hand),
                ZoneType.Hand,scene.opponent(),"Previously revealed",false);
        Result result = cast(scene);
        Assert.assertEquals(result.name(),"Counterspell");
        Assert.assertEquals(result.opposingHand(),0);
        Assert.assertEquals(result.paid(),1);
    }

    @Test(dataProvider="seats")
    public void legitimatelyKnownTopCardCanGuideThePaidPrediction(int seat) {
        Scene scene = scene("Predict",seat,false);
        Card known = scene.opponent().getCardsIn(ZoneType.Library).get(0);
        known.addMayLookTemp(scene.actor());
        Result result = cast(scene);
        Assert.assertEquals(result.name(),known.getName());
        Assert.assertEquals(result.actorHand(),2,"Matching the legitimately known top must draw two real cards");
        Assert.assertEquals(result.paid(),2);
    }

    @Test(dataProvider="seats")
    public void successiveAuthorizedPartialRevealsDoNotEraseEarlierKnowledge(int seat) {
        Scene scene = scene("Cabal Therapy",seat,false);
        for (int i=0;i<2;i++) {
            Card bolt = scene.opponent().getCardsIn(ZoneType.Hand).get(0);
            scene.game().getAction().moveToLibrary(bolt,-1,null);
            Card counter = scene.opponent().getCardsIn(ZoneType.Library).stream()
                    .filter(c -> c.getName().equals("Counterspell")).findFirst().orElseThrow();
            scene.game().getAction().moveToHand(counter,null);
        }
        var counters = new forge.game.card.CardCollection(scene.opponent().getCardsIn(ZoneType.Hand).stream()
                .filter(c -> c.getName().equals("Counterspell")).toList());
        var oneBolt = new forge.game.card.CardCollection(List.of(scene.opponent().getCardsIn(ZoneType.Hand).stream()
                .filter(c -> c.getName().equals("Lightning Bolt")).findFirst().orElseThrow()));
        scene.actor().getController().reveal(counters,ZoneType.Hand,scene.opponent(),"Known pair",false);
        scene.actor().getController().reveal(oneBolt,ZoneType.Hand,scene.opponent(),"Another reveal",false);
        Result result = cast(scene);
        Assert.assertEquals(result.name(),"Counterspell","Two known copies outrank one known copy");
        Assert.assertEquals(result.opposingHand(),2);
    }

    @Test(dataProvider="seats")
    public void absenceOfPublicDecklistsDoesNotAuthorizePrivatePartitionReads(int seat) {
        Scene first = scene("Cabal Therapy",seat,false), second = scene("Cabal Therapy",seat,true);
        first.actor().dangerouslySetController(new PublicNameController(first.game(),first.actor(),
                first.actor().getLobbyPlayer(),Map.of()));
        second.actor().dangerouslySetController(new PublicNameController(second.game(),second.actor(),
                second.actor().getLobbyPlayer(),Map.of()));
        Result a=cast(first), b=cast(second);
        Assert.assertEquals(a.actorInput(),b.actorInput());
        Assert.assertEquals(a.name(),b.name());
        Assert.assertFalse(FModel.getMagicDb().getCommonCards().getFaceByName(a.name()).getType().isLand());
    }

    private Scene afterPaidPeekResponseToBrainstorm(int seat,boolean swap) {
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);
        MyRandom.setRandom(new Random(29172371));
        Map<String,Integer> own=Map.of("Cabal Therapy",4,"Peek",4,"Swamp",48,"Island",4);
        Map<String,Integer> opposing=Map.of("Counterspell",4,"Lightning Bolt",4,"Brainstorm",4,"Island",48);
        Map<Integer,Map<String,Integer>> lists=seat==0?Map.of(0,own,1,opposing):Map.of(0,opposing,1,own);
        RegisteredPlayer a=new RegisteredPlayer(deck("A",lists.get(0))).setPlayer(lobby("A",lists));
        RegisteredPlayer b=new RegisteredPlayer(deck("B",lists.get(1))).setPlayer(lobby("B",lists));
        GameRules rules=new GameRules(GameType.Constructed);rules.setAllowCheatShuffle(false);
        Game game=new Game(List.of(a,b),rules,new Match(rules,List.of(a,b),"Paid private-response pair"));
        game.setAge(GameStage.Play);game.AI_FLAT_MONTE_CARLO=false;
        Player actor=game.getPlayers().get(seat),opponent=game.getPlayers().get(1-seat);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1,actor);
        addCard("Swamp",actor);addCard("Island",actor);
        Card therapy=addCardToZone("Cabal Therapy",actor,ZoneType.Hand);
        Card peek=addCardToZone("Peek",actor,ZoneType.Hand);
        for (int i=0;i<3;i++) {addCardToZone("Cabal Therapy",actor,ZoneType.Library);addCardToZone("Peek",actor,ZoneType.Library);}
        for (int i=0;i<47;i++) addCardToZone("Swamp",actor,ZoneType.Library);
        for (int i=0;i<3;i++) addCardToZone("Island",actor,ZoneType.Library);
        addCard("Island",opponent);
        Card brainstorm=addCardToZone("Brainstorm",opponent,ZoneType.Hand);
        for (int i=0;i<2;i++) {addCardToZone("Counterspell",opponent,ZoneType.Hand);addCardToZone("Lightning Bolt",opponent,ZoneType.Hand);}
        for (String name:swap?List.of("Lightning Bolt","Lightning Bolt","Counterspell","Counterspell"):
                List.of("Counterspell","Counterspell","Lightning Bolt","Lightning Bolt")) addCardToZone(name,opponent,ZoneType.Library);
        for (int i=0;i<3;i++) addCardToZone("Brainstorm",opponent,ZoneType.Library);
        for (int i=0;i<47;i++) addCardToZone("Island",opponent,ZoneType.Library);
        Assert.assertEquals(actor.getAllCards().size(),60);Assert.assertEquals(opponent.getAllCards().size(),60);
        SpellAbility draw=brainstorm.getFirstSpellAbility();draw.setActivatingPlayer(opponent);
        Assert.assertTrue(ComputerUtil.playStack(draw,opponent,game));
        SpellAbility look=peek.getFirstSpellAbility();look.setActivatingPlayer(actor);look.getTargets().add(opponent);
        Assert.assertTrue(ComputerUtil.playStack(look,actor,game));
        Assert.assertEquals(game.getStack().size(),2,"Real paid Peek responds above real paid Brainstorm");
        game.getStack().resolveStack();
        Assert.assertEquals(game.getStack().size(),1);
        game.getStack().resolveStack();
        Assert.assertTrue(game.getStack().isEmpty());
        Assert.assertEquals(opponent.getCardsIn(ZoneType.Hand).size(),5);
        Assert.assertEquals(actor.getCardsIn(ZoneType.Hand).size(),2);
        SpellAbility discard=therapy.getFirstSpellAbility();discard.setActivatingPlayer(actor);
        discard.getSubAbility().getTargets().add(opponent);
        return new Scene(game,actor,opponent,discard);
    }

    @Test(dataProvider="seats")
    public void paidPeekThenPrivateBrainstormChoicesDoNotGrantExactHandTracking(int seat) {
        Result first=cast(afterPaidPeekResponseToBrainstorm(seat,false));
        Result second=cast(afterPaidPeekResponseToBrainstorm(seat,true));
        Assert.assertEquals(first.actorInput(),second.actorInput(),"The actual paid response leaves equal actor-visible inputs");
        Assert.assertEquals(first.name(),second.name(),"Private put-backs must not identify which remembered cards remain");
        Assert.assertEquals(first.paid(),2,"Peek U plus Therapy B actually paid");
        Assert.assertEquals(second.paid(),2);
    }

    @Test(dataProvider="seats")
    public void aPublicCounterspellDoesNotEraseKnowledgeOfAnUnrelatedCard(int seat) {
        Scene scene=scene("Cabal Therapy",seat,false);
        for (int i=0;i<2;i++) {
            Card bolt=scene.opponent().getCardsIn(ZoneType.Hand).get(0);
            scene.game().getAction().moveToLibrary(bolt,-1,null);
            Card counter=scene.opponent().getCardsIn(ZoneType.Library).stream()
                    .filter(c -> c.getName().equals("Counterspell")).findFirst().orElseThrow();
            scene.game().getAction().moveToHand(counter,null);
        }
        Card extra=scene.actor().getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals("Cabal Therapy")).findFirst().orElseThrow();
        scene.game().getAction().moveToHand(extra,null);
        Card swamp=scene.actor().getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals("Swamp")).findFirst().orElseThrow();
        scene.game().getAction().moveToPlay(swamp,null,forge.game.ability.AbilityKey.newMap());
        for (int i=0;i<2;i++) {
            Card island=scene.opponent().getCardsIn(ZoneType.Library).stream()
                    .filter(c -> c.getName().equals("Island")).findFirst().orElseThrow();
            scene.game().getAction().moveToPlay(island,null,forge.game.ability.AbilityKey.newMap());
        }
        Card known=scene.opponent().getCardsIn(ZoneType.Hand).stream()
                .filter(c -> c.getName().equals("Lightning Bolt")).findFirst().orElseThrow();
        scene.actor().getController().reveal(new forge.game.card.CardCollection(List.of(known)),
                ZoneType.Hand,scene.opponent(),"Known card",false);
        Assert.assertTrue(ComputerUtil.playStack(scene.spell(),scene.actor(),scene.game()));
        Card counter=scene.opponent().getCardsIn(ZoneType.Hand).stream()
                .filter(c -> c.getName().equals("Counterspell")).findFirst().orElseThrow();
        SpellAbility response=counter.getFirstSpellAbility();response.setActivatingPlayer(scene.opponent());
        response.getTargets().add(scene.spell());
        Assert.assertTrue(ComputerUtil.playStack(response,scene.opponent(),scene.game()));
        Assert.assertEquals(scene.game().getStack().size(),2);
        scene.game().getStack().resolveStack();
        Assert.assertTrue(scene.game().getStack().isEmpty(),"The first Therapy was genuinely countered");
        Assert.assertEquals(scene.actor().getCardsIn(ZoneType.Graveyard).size(),1);
        SpellAbility next=extra.getFirstSpellAbility();next.setActivatingPlayer(scene.actor());
        next.getSubAbility().getTargets().add(scene.opponent());
        Result result=cast(new Scene(scene.game(),scene.actor(),scene.opponent(),next));
        Assert.assertEquals(result.name(),"Lightning Bolt","A public cast of another card does not revoke this knowledge");
        Assert.assertEquals(result.opposingHand(),1);
        Assert.assertEquals(result.paid(),2);
    }
}
