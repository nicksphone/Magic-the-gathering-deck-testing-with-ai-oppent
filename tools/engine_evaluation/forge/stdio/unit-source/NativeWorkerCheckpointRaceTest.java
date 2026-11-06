// SPDX-License-Identifier: GPL-3.0-or-later
// Original controlled concurrency/IO units on Forge Team/Card-Forge APIs.
// Latches expose real callback windows; these are not natural-game fixtures.
package forge.evaluation;

import com.google.gson.*;
import forge.ai.simulation.SimulationTest;
import forge.game.Game;
import forge.game.card.*;
import forge.game.player.Player;
import forge.game.zone.ZoneType;
import forge.gamemodes.match.input.*;
import forge.gamemodes.net.ProtocolGuiGame;
import forge.player.LobbyPlayerHuman;
import forge.player.PlayerControllerHuman;
import forge.util.ITriggerEvent;
import java.io.*;
import java.lang.management.ManagementFactory;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import javax.swing.SwingUtilities;
import org.testng.Assert;
import org.testng.annotations.Test;

public final class NativeWorkerCheckpointRaceTest extends SimulationTest {
    private static Method method(String name,Class<?>... types)throws Exception {
        Method m=NativeHumanWorker.class.getDeclaredMethod(name,types);m.setAccessible(true);return m;
    }
    private static Object get(Object target,String name)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);return f.get(target);
    }
    private static void set(Object target,String name,Object value)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);f.set(target,value);
    }
    private final class Fixture {
        final Game game=initAndCreateGame();final Player actor=game.getPlayers().get(0);
        final AtomicReference<Runnable> checkpointWire=new AtomicReference<>();
        final StringWriter output=new StringWriter() {
            @Override public void write(String text,int offset,int length) {
                Runnable hook=checkpointWire.get();
                if(hook!=null&&text.substring(offset,offset+length).contains("checkpoint_saved"))hook.run();
                super.write(text,offset,length);
            }
        };
        final NativeHumanWorker worker=new NativeHumanWorker(new PrintWriter(output));
        final CountDownLatch returnedToController=new CountDownLatch(1),releaseController=new CountDownLatch(1);
        final AtomicBoolean holdController=new AtomicBoolean();
        final PlayerControllerHuman human=new PlayerControllerHuman(game,actor,new LobbyPlayerHuman("UNIT-RACE")) {
            @Override public boolean selectCard(CardView card,List<CardView> others,ITriggerEvent event) {
                boolean selected=super.selectCard(card,others,event);
                if(holdController.get()) {
                    returnedToController.countDown();
                    try { if(!releaseController.await(10,TimeUnit.SECONDS))throw new AssertionError("Controller latch not released"); }
                    catch(InterruptedException e) { throw new AssertionError(e); }
                }
                return selected;
            }
        };
        final ProtocolGuiGame gui=new ProtocolGuiGame(worker);
        final Path root=Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")),"checkpoint-race-unit-");
        final List<Card> cards=new ArrayList<>();final InputSelectEntitiesFromList<Card> input;
        Fixture()throws Exception {
            set(worker,"actor",actor);set(worker,"boundary",new ActorBoundary(actor));set(worker,"gui",gui);set(worker,"evidence",root);
            set(worker,"matchSpec",JsonParser.parseString("{\"human_seat\":0,\"decks\":[{\"file\":\"unit0.dck\"},{\"file\":\"unit1.dck\"}]}"));
            @SuppressWarnings("unchecked") Map<String,String> decks=(Map<String,String>)get(worker,"importedDecks");
            decks.put("unit0.dck","SYNTHETIC UNIT 0");decks.put("unit1.dck","SYNTHETIC UNIT 1");
            human.setGui(gui);gui.setGameController(actor.getView(),human);gui.setGameView(game.getView());
            method("observeInputReadiness").invoke(worker);
            for(int i=0;i<4;i++)cards.add(addCardToZone("Grizzly Bears",actor,ZoneType.Hand));
            var choices=new forge.util.collect.FCollection<Card>();choices.addAll(cards);
            input=new InputSelectEntitiesFromList<>(human,2,2,choices,null);input.setMessage("INTERNAL RACE UNIT choose %d more");
            human.getInputQueue().setInput(input);SwingUtilities.invokeAndWait(()->{});
            SwingUtilities.invokeAndWait(()->human.selectCard(cards.get(0).getView(),null,null));
        }
        String request()throws Exception { return (String)get(worker,"request"); }
        void capture()throws Exception { method("checkpoint",String.class).invoke(worker,request()); }
        String token(Card card) {
            JsonObject latest=null;for(String row:output.toString().split("\\R")) {
                JsonObject event=JsonParser.parseString(row).getAsJsonObject();if(event.get("event").getAsString().equals("choice"))latest=event;
            }
            for(JsonElement e:latest.getAsJsonObject("question").getAsJsonArray("choices")) {
                JsonObject d=e.getAsJsonObject().getAsJsonObject("display");
                if(d.get("card_id").getAsInt()==card.getId())return e.getAsJsonObject().get("token").getAsString();
            }
            throw new AssertionError("No actual card token");
        }
    }
    @Test public void refreshedChoiceWaitsForItsActualProducingDispatchReturn()throws Exception {
        Fixture f=new Fixture();f.holdController.set(true);
        method("accept",NativeHumanWorker.Answer.class).invoke(f.worker,new NativeHumanWorker.Answer(f.request(),List.of(f.token(f.cards.get(0)))));
        try {
            Assert.assertTrue(f.returnedToController.await(5,TimeUnit.SECONDS));
            Assert.assertEquals(get(f.worker,"starts"),1);Assert.assertEquals(get(f.worker,"decisions"),0);
            Assert.assertTrue(f.input.getSelected().isEmpty(),"Real callback toggled the card before its dispatch returned");
            InvocationTargetException rejected=Assert.expectThrows(InvocationTargetException.class,f::capture);
            Assert.assertTrue(rejected.getCause() instanceof IllegalArgumentException);
            Assert.assertFalse(Files.exists(f.root.resolve("CHECKPOINT.json")));
        } finally { f.releaseController.countDown();SwingUtilities.invokeAndWait(()->{}); }
        Assert.assertEquals(get(f.worker,"decisions"),1);f.capture();
        JsonObject saved=JsonParser.parseString(Files.readString(f.root.resolve("CHECKPOINT.json"))).getAsJsonObject();
        Assert.assertEquals(saved.get("starts").getAsInt(),1);Assert.assertEquals(saved.get("completions").getAsInt(),1);
    }
    @Test public void inputReplacementCannotPassTheCheckpointPublicationFence()throws Exception {
        Fixture f=new Fixture();AtomicReference<Thread> remover=new AtomicReference<>();AtomicReference<Throwable> failure=new AtomicReference<>();
        f.checkpointWire.set(()->{
            Thread thread=new Thread(()->{try{f.human.getInputQueue().removeInput(f.input);}catch(Throwable e){failure.set(e);}},"checkpoint-unit-replacer");
            remover.set(thread);thread.start();long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            boolean blockedByCapture=false;
            while(System.nanoTime()<deadline) {
                var info=ManagementFactory.getThreadMXBean().getThreadInfo(thread.getId());
                if(info!=null&&info.getThreadState()==Thread.State.BLOCKED&&info.getLockOwnerId()==Thread.currentThread().getId()){blockedByCapture=true;break;}
                Thread.yield();
            }
            Assert.assertTrue(blockedByCapture,"Actual remover must be blocked by the capture thread");
            Assert.assertTrue(Thread.holdsLock(f.human.getInputQueue()),"Capture must retain the input lifetime through publication");
            Assert.assertSame(f.human.getInputQueue().getInput(),f.input,"Question cannot already be replaced when saved is emitted");
        });
        try { f.capture(); }
        finally { if(remover.get()!=null)remover.get().join(5000); }
        Assert.assertNotNull(remover.get());Assert.assertFalse(remover.get().isAlive());Assert.assertNull(failure.get());
        Assert.assertTrue(Files.isRegularFile(f.root.resolve("CHECKPOINT.json")));
    }
    @Test public void recoverableWriteFailurePreservesTheQuestionAndPriorSnapshot()throws Exception {
        Fixture f=new Fixture();f.capture();String request=f.request();Path checkpoint=f.root.resolve("CHECKPOINT.json"),prior=f.root.resolve("prior-checkpoint.json");
        byte[] before=Files.readAllBytes(checkpoint);Files.move(checkpoint,prior);Files.createSymbolicLink(checkpoint,prior.getFileName());
        f.capture();Assert.assertEquals(get(f.worker,"failed"),false);Assert.assertEquals(f.request(),request);
        Assert.assertEquals(Files.readAllBytes(prior),before);Assert.assertEquals(f.input.getSelected(),List.of(f.cards.get(0)));
        Assert.assertTrue(f.output.toString().contains("checkpoint_failed"));
        Files.delete(checkpoint);Files.move(prior,checkpoint);f.capture();Assert.assertEquals(f.request(),request);
    }
}
