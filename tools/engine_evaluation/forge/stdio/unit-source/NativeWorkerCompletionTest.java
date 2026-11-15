// SPDX-License-Identifier: GPL-3.0-or-later
// Original lifecycle units using the Forge Team/Card-Forge engine and test helpers.
// Controlled canonical poses, not naturally drawn games or injected winners.
package forge.evaluation;

import com.google.gson.*;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.*;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.*;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.util.MyRandom;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.util.*;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public final class NativeWorkerCompletionTest extends SimulationTest {
    @DataProvider(name="seats") public Object[][] seats() { return new Object[][]{{0},{1}}; }

    private Game pose(int seat) {
        MyRandom.setRandom(new Random(2026110601L));
        List<RegisteredPlayer> players=new ArrayList<>();
        for(int i=0;i<2;i++) {
            Deck deck=new Deck("completion-seat"+i);
            if(i==seat) { deck.getMain().add("Lightning Bolt",4);deck.getMain().add("Mountain",56); }
            else deck.getMain().add("Plains",60);
            LobbyPlayerAi lobby=new LobbyPlayerAi("completion-seat"+i,null);
            lobby.setAiProfile("Default");players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);rules.setAllowCheatShuffle(false);
        Game game=new Game(players,rules,new Match(rules,players,"CONTROLLED completion unit"));
        game.setAge(GameStage.Play);Player actor=game.getPlayers().get(seat),other=game.getPlayers().get(1-seat);
        actor.setLife(20,null);other.setLife(3,null);
        game.getPhaseHandler().devModeSet(PhaseType.END_OF_TURN,other);
        addCardToZone("Mountain",actor,ZoneType.Battlefield);addCardToZone("Lightning Bolt",actor,ZoneType.Hand);
        for(int i=0;i<55;i++)addCardToZone("Mountain",actor,ZoneType.Library);
        for(int i=0;i<3;i++)addCardToZone("Lightning Bolt",actor,ZoneType.Library);
        for(int i=0;i<60;i++)addCardToZone("Plains",other,ZoneType.Library);
        game.getPhaseHandler().setPriority(actor);Assert.assertFalse(game.isGameOver());return game;
    }

    private static void set(NativeHumanWorker worker,String name,Object value)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);f.set(worker,value);
    }
    private static boolean flag(NativeHumanWorker worker,String name)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);return f.getBoolean(worker);
    }
    private NativeHumanWorker worker(StringWriter output)throws Exception {
        NativeHumanWorker worker=new NativeHumanWorker(new PrintWriter(output));
        set(worker,"evidence",Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")),"completion-unit-"));
        return worker;
    }
    private static List<JsonObject> events(StringWriter output) {
        List<JsonObject> result=new ArrayList<>();
        for(String row:output.toString().split("\\R"))if(!row.isBlank())result.add(JsonParser.parseString(row).getAsJsonObject());
        return result;
    }

    @Test(dataProvider="seats") public void actualNativeWinDoesNotRequireScriptCoverage(int seat)throws Exception {
        Game game=pose(seat);Player actor=game.getPlayers().get(seat),other=game.getPlayers().get(1-seat);
        List<SpellAbility> selected=((PlayerControllerAi)actor.getController()).chooseSpellAbilityToPlay();
        Assert.assertNotNull(selected);Assert.assertEquals(selected.size(),1);SpellAbility sa=selected.get(0);
        Assert.assertEquals(sa.getHostCard().getName(),"Lightning Bolt");Assert.assertTrue(sa.canPlay());
        Assert.assertTrue(sa.isTargetNumberValid());Assert.assertEquals(sa.getTargets().getFirstTargetedPlayer(),other);
        Assert.assertTrue(ComputerUtil.playStack(sa,actor,game));Assert.assertEquals(other.getLife(),3);
        Assert.assertEquals(game.getStack().size(),1);Assert.assertEquals(actor.getCardsIn(ZoneType.Battlefield).stream().filter(Card::isTapped).count(),1L);
        game.getStack().resolveStack();game.getAction().checkStateEffects(true);
        Assert.assertTrue(game.isGameOver());Assert.assertEquals(other.getLife(),0);Assert.assertNotNull(game.getOutcome());
        StringWriter output=new StringWriter();NativeHumanWorker worker=worker(output);
        Assert.assertFalse(flag(worker,"reversedSeen"));Assert.assertFalse(flag(worker,"paidSeen"));
        set(worker,"actor",actor);set(worker,"boundary",new ActorBoundary(actor));
        worker.completed(game);
        List<JsonObject> all=events(output);
        List<JsonObject> views=all.stream().filter(e->e.get("event").getAsString().equals("view")).toList();
        Assert.assertEquals(views.size(),1,"Final actor view must be published after genuine native lethal");
        Assert.assertEquals(all.get(all.size()-2).get("event").getAsString(),"view");
        for(JsonElement p:views.get(0).getAsJsonObject("state").getAsJsonArray("players")) {
            JsonObject player=p.getAsJsonObject();
            int expected=player.get("player_id").getAsInt()==other.getId()?0:20;
            Assert.assertEquals(player.get("life").getAsInt(),expected,"Final actor life must match native committed life");
        }
        List<JsonObject> complete=events(output).stream().filter(e->e.get("event").getAsString().equals("game_complete")).toList();
        Assert.assertEquals(complete.size(),1,"A genuine native win must be reported even without scripted ordering/payment coverage: "+output);
        Assert.assertEquals(complete.get(0).get("draw").getAsBoolean(),game.getOutcome().isDraw());
        Assert.assertEquals(complete.get(0).get("outcomes"),new Gson().toJsonTree(game.getOutcome().getOutcomeStrings()));
        Assert.assertFalse(flag(worker,"failed"));Assert.assertTrue(flag(worker,"terminal"));
    }

    @Test(dataProvider="seats") public void coverageFlagsCannotInventAnUnfinishedOutcome(int seat)throws Exception {
        Game game=pose(seat);StringWriter output=new StringWriter();NativeHumanWorker worker=worker(output);
        // INTERNAL negative diagnostic flags, not observed human gameplay coverage.
        set(worker,"reversedSeen",true);set(worker,"paidSeen",true);worker.completed(game);
        Assert.assertFalse(game.isGameOver());Assert.assertTrue(flag(worker,"failed"));Assert.assertFalse(flag(worker,"terminal"));
        Assert.assertTrue(events(output).isEmpty());
    }
}
