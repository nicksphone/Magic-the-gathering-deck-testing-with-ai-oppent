// SPDX-License-Identifier: GPL-3.0-or-later
// Internal protocol regressions using Forge Team/Card-Forge engine helpers.
package forge.evaluation;
import forge.ai.AiController;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.*;
import forge.game.card.Card;
import forge.game.player.*;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.Lock;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public final class NativeRootObserverProtocolTest extends SimulationTest {
    private Object[] pose() throws Exception { return pose(0); }
    private Object[] pose(int seat) throws Exception {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i=0;i<2;i++) {
            Deck d = new Deck("INTERNAL observer protocol"); d.getMain().add("Mountain",60);
            LobbyPlayerAi p = new LobbyPlayerAi("protocol-seat-"+i,null); p.setAiProfile("Default");
            players.add(new RegisteredPlayer(d).setPlayer(p));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        Game g = new Game(players,rules,new Match(rules,players,"INTERNAL observer protocol"));
        Player p = g.getPlayers().get(seat);
        Card bolt = addCardToZone("Lightning Bolt",p,ZoneType.Hand);
        SpellAbility sa = bolt.getFirstSpellAbility();
        AiController brain = ((PlayerControllerAi)p.getController()).getAi();
        Class<?> type = Class.forName("forge.ai.AiController$DecisionCollector");
        Constructor<?> c = type.getDeclaredConstructor(AiController.class); c.setAccessible(true);
        return new Object[] {c.newInstance(brain),sa,type};
    }
    private static Object invoke(Object collector,String name,Class<?>[] types,Object... args) throws Exception {
        Method m=collector.getClass().getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(collector,args);
    }
    private static List<?> selected(Object trace) throws Exception {
        return (List<?>)trace.getClass().getMethod("selected").invoke(trace);
    }
    @DataProvider(name="privacy") public Object[][] privacy() {
        return new Object[][] {{0,false},{1,false},{0,true},{1,true}};
    }
    @Test(dataProvider="privacy") public void internalIdentitySnapshotRedactsHiddenAndFaceDownHost(int seat,boolean faceDown) throws Exception {
        Object[] p=pose(seat);Object collector=p[0];
        Field outer=collector.getClass().getDeclaredField("this$0");outer.setAccessible(true);
        AiController brain=(AiController)outer.get(collector);
        Player other=brain.getGame().getPlayers().get(1-seat);
        Card hidden=addCardToZone("Ancestral Recall",other,ZoneType.Library);
        SpellAbility ability=hidden.getFirstSpellAbility();
        Assert.assertNotNull(ability);
        if(faceDown)hidden.turnFaceDown(true);
        // Internal snapshot protocol ONLY: this is not an eligible root action or offered game choice.
        Object value=invoke(collector,"identity",new Class<?>[]{SpellAbility.class},ability);
        for(String field:List.of("abilityId","cardId","name","api"))
            Assert.assertNull(value.getClass().getMethod(field).invoke(value),field);
    }
    @Test public void selectedSurvivesExhaustedVisitIdentityBudget() throws Exception {
        Object[] p=pose();Object c=p[0];SpellAbility sa=(SpellAbility)p[1];
        invoke(c,"offered",new Class<?>[]{List.class},Collections.nCopies(4096,sa));
        Object trace=invoke(c,"finish",new Class<?>[]{String.class,List.class},"selected",List.of(sa));
        Assert.assertEquals(selected(trace).size(),1,"Known selected choice must not be erased by visit budget");
        Assert.assertEquals(selected(trace).get(0).getClass().getMethod("abilityId").invoke(selected(trace).get(0)),sa.getId());
    }
    @Test public void finalPublicationDoesNotWaitForBusyCollectorLock() throws Exception {
        Object[] p=pose();Object c=p[0];SpellAbility sa=(SpellAbility)p[1];
        CountDownLatch held=new CountDownLatch(1),release=new CountDownLatch(1);
        Lock explicit;
        try { Field f=c.getClass().getDeclaredField("lock");f.setAccessible(true);explicit=(Lock)f.get(c); }
        catch(NoSuchFieldException original) { explicit=null; }
        final Lock lock=explicit;
        Thread holder=new Thread(()->{
            if(lock!=null) { lock.lock();try {held.countDown();release.await();}catch(InterruptedException e){Thread.currentThread().interrupt();}finally{lock.unlock();} }
            else synchronized(c) {held.countDown();try{release.await();}catch(InterruptedException e){Thread.currentThread().interrupt();}}
        },"INTERNAL observer-lock holder");
        holder.start();Assert.assertTrue(held.await(2,TimeUnit.SECONDS));
        FutureTask<Object> freeze=new FutureTask<>(()->invoke(c,"finish",new Class<?>[]{String.class,List.class},"selected",List.of(sa)));
        Thread finisher=new Thread(freeze,"INTERNAL observer publication");finisher.start();
        boolean blocked=false;
        try { Assert.assertEquals(selected(freeze.get(500,TimeUnit.MILLISECONDS)).size(),1); }
        catch(TimeoutException unbounded) { blocked=true; }
        finally {release.countDown();holder.join(2000);finisher.join(2000);}
        Assert.assertFalse(holder.isAlive()||finisher.isAlive(),"Owned test threads must be closed");
        Assert.assertFalse(blocked,"Publication waited on collector lock after native deadline");
    }
}
