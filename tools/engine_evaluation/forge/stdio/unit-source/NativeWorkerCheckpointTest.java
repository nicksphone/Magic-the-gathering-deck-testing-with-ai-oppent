// SPDX-License-Identifier: GPL-3.0-or-later
// Original units for the Forge Team/Card-Forge adapter; trusted native poses,
// not natural games or durable-resume qualification.
package forge.evaluation;

import com.google.gson.*;
import forge.ai.simulation.SimulationTest;
import forge.game.Game;
import forge.game.card.Card;
import forge.game.player.Player;
import forge.game.zone.ZoneType;
import forge.gamemodes.match.input.*;
import forge.gamemodes.net.ProtocolGuiGame;
import forge.player.LobbyPlayerHuman;
import forge.player.PlayerControllerHuman;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import javax.swing.SwingUtilities;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public final class NativeWorkerCheckpointTest extends SimulationTest {
    private static final Gson JSON=new Gson();
    private static final String ID="00000000-0000-0000-0000-000000000001";
    private static Method method(String name,Class<?>... types)throws Exception {
        Method m=NativeHumanWorker.class.getDeclaredMethod(name,types);m.setAccessible(true);return m;
    }
    private static void set(Object worker,String name,Object value)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);f.set(worker,value);
    }
    private static Object get(Object worker,String name)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);return f.get(worker);
    }
    private static Throwable failure(Method m,Object target,Object... args)throws Exception {
        try { m.invoke(target,args);throw new AssertionError("Expected rejection"); }
        catch(InvocationTargetException e) { return e.getCause(); }
    }
    @DataProvider(name="invalidControl") public Object[][] invalidControl() {
        return new Object[][] {
            {"{\"checkpoint_request_id\":null}"},
            {"{\"checkpoint_request_id\":true}"},
            {"{\"checkpoint_request_id\":123}"},
            {"{\"checkpoint_request_id\":\"\"}"},
            {"{\"checkpoint_request_id\":\""+ID+"\",\"checkpoint_request_id\":\""+ID+"\"}"},
            {"{\"checkpoint_request_id\":\""+ID+"\",\"actor_id\":0}"},
            {"{\"checkpoint_request_id\":\""+ID+"\",\"tokens\":[]}"},
            {"{\"checkpoint_request_id\":\""+ID+"\"} []"},
            {"{\"checkpoint_request_id\":\""+"a".repeat(16385)+"\"}"}
        };
    }
    @Test(dataProvider="invalidControl") public void malformedControlCannotBecomeAnAnswer(String line)throws Exception {
        Method m=method("decodeCheckpoint",String.class);
        Assert.assertTrue(failure(m,null,line) instanceof IllegalArgumentException);
    }
    @Test public void strictControlAndLegacyAnswerAreSeparate()throws Exception {
        Method m=method("decodeCheckpoint",String.class);
        Assert.assertEquals(m.invoke(null,"{\"checkpoint_request_id\":\""+ID+"\"}"),ID);
        String answer="{\"request_id\":\""+ID+"\",\"tokens\":[]}";
        Assert.assertNull(m.invoke(null,answer));Assert.assertEquals(NativeHumanWorker.decode(answer).request(),ID);
        Assert.expectThrows(IllegalArgumentException.class,()->NativeHumanWorker.decode("{\"checkpoint_request_id\":\""+ID+"\"}"));
    }

    private final class Fixture {
        final Game game=initAndCreateGame();final Player actor=game.getPlayers().get(0);
        final StringWriter output=new StringWriter();final NativeHumanWorker worker=new NativeHumanWorker(new PrintWriter(output));
        final PlayerControllerHuman human=new PlayerControllerHuman(game,actor,new LobbyPlayerHuman("UNIT-CHECKPOINT"));
        final ProtocolGuiGame gui=new ProtocolGuiGame(worker);
        final Path root=Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")),"checkpoint-unit-");
        final List<Card> cards=new ArrayList<>();final InputSelectEntitiesFromList<Card> input;
        Fixture()throws Exception {
            set(worker,"actor",actor);set(worker,"boundary",new ActorBoundary(actor));set(worker,"gui",gui);set(worker,"evidence",root);
            // LABELLED SYNTHETIC launch metadata for this trusted native object pose.
            set(worker,"matchSpec",JsonParser.parseString("{\"human_seat\":0,\"decks\":[{\"file\":\"unit0.dck\"},{\"file\":\"unit1.dck\"}]}"));
            @SuppressWarnings("unchecked") Map<String,String> decks=(Map<String,String>)get(worker,"importedDecks");
            decks.put("unit0.dck","SYNTHETIC UNIT deck 0\n");decks.put("unit1.dck","SYNTHETIC UNIT deck 1\n");
            human.setGui(gui);gui.setGameController(actor.getView(),human);gui.setGameView(game.getView());
            method("observeInputReadiness").invoke(worker);
            for(int i=0;i<4;i++)cards.add(addCardToZone("Grizzly Bears",actor,ZoneType.Hand));
            var choices=new forge.util.collect.FCollection<Card>();choices.addAll(cards);
            input=new InputSelectEntitiesFromList<>(human,2,2,choices,null);
            input.setMessage("INTERNAL CHECKPOINT UNIT choose %d more");
            human.getInputQueue().setInput(input);SwingUtilities.invokeAndWait(()->{});
            SwingUtilities.invokeAndWait(()->human.selectCard(cards.get(0).getView(),null,null));
        }
        String request()throws Exception { return (String)get(worker,"request"); }
        void capture()throws Exception { method("checkpoint",String.class).invoke(worker,request()); }
        JsonObject saved()throws Exception { return JsonParser.parseString(Files.readString(root.resolve("CHECKPOINT.json"))).getAsJsonObject(); }
    }
    @Test public void captureRetainsOneOfTwoNativeSelectionsAndDoesNotConsumeChoice()throws Exception {
        method("checkpoint",String.class);Fixture f=new Fixture();String request=f.request();
        Object before=method("nativeState",Game.class).invoke(f.worker,f.game);
        f.capture();JsonObject saved=f.saved();
        Assert.assertEquals(saved.keySet(),Set.of("schema","spec","decks","starts","completions","pending_offer","actor_view","native_state","journals"));
        Assert.assertEquals(saved.get("schema").getAsInt(),1);Assert.assertEquals(saved.get("native_state"),JSON.toJsonTree(before));
        Assert.assertEquals(saved.getAsJsonObject("pending_offer").getAsJsonObject("info").getAsJsonObject("selection").getAsJsonArray("chosen").size(),1);
        Assert.assertEquals(saved.getAsJsonObject("actor_view").get("actor_id").getAsInt(),f.actor.getId());
        Assert.assertEquals(saved.getAsJsonObject("journals").keySet(),Set.of("starts","completions","native","paid-pending","final"));
        Assert.assertEquals(f.request(),request);Assert.assertEquals(f.input.getSelected(),List.of(f.cards.get(0)));
        Assert.assertEquals(method("nativeState",Game.class).invoke(f.worker,f.game),before);
        Assert.assertEquals(Files.getPosixFilePermissions(f.root.resolve("CHECKPOINT.json")),PosixFilePermissions.fromString("rw-------"));
        try(var files=Files.list(f.root)) { Assert.assertEquals(files.filter(p->p.getFileName().toString().startsWith(".checkpoint-")).count(),0L); }
        // The original one-use question remains usable; snapshot data never chooses the second card.
        JsonObject frame=null;for(String row:f.output.toString().split("\\R")) {
            JsonObject e=JsonParser.parseString(row).getAsJsonObject();if(e.get("event").getAsString().equals("choice"))frame=e;
        }
        String token=null;for(JsonElement row:frame.getAsJsonObject("question").getAsJsonArray("choices")) {
            JsonObject e=row.getAsJsonObject();if(e.get("display").isJsonObject()&&e.getAsJsonObject("display").has("card_id")&&e.getAsJsonObject("display").get("card_id").getAsInt()==f.cards.get(1).getId())token=e.get("token").getAsString();
        }
        Assert.assertNotNull(token);method("accept",NativeHumanWorker.Answer.class).invoke(f.worker,new NativeHumanWorker.Answer(request,List.of(token)));
        SwingUtilities.invokeAndWait(()->{});Assert.assertEquals(f.input.getSelected(),List.of(f.cards.get(0),f.cards.get(1)));
        Assert.assertEquals(f.saved(),saved,"Later play must not rewrite the retained snapshot");
    }
    @Test public void staleRequestCannotWriteOrConsumeCurrentQuestion()throws Exception {
        Method m=method("checkpoint",String.class);Fixture f=new Fixture();String request=f.request();
        Assert.assertTrue(failure(m,f.worker,ID) instanceof IllegalArgumentException);
        Assert.assertFalse(Files.exists(f.root.resolve("CHECKPOINT.json")));Assert.assertEquals(f.request(),request);
    }
    @DataProvider(name="closed") public Object[][] closed() { return new Object[][]{{"terminal"},{"failed"},{"aborted"}}; }
    @Test(dataProvider="closed") public void closedWorkerCannotSave(String flag)throws Exception {
        Method m=method("checkpoint",String.class);Fixture f=new Fixture();set(f.worker,flag,true);
        Assert.assertTrue(failure(m,f.worker,f.request()) instanceof IllegalArgumentException);
        Assert.assertFalse(Files.exists(f.root.resolve("CHECKPOINT.json")));
    }
    @Test public void replacedInputCannotBeSavedAsCurrent()throws Exception {
        Method m=method("checkpoint",String.class);Fixture f=new Fixture();String request=f.request();
        SwingUtilities.invokeAndWait(()->f.human.getInputQueue().removeInput(f.input));
        Assert.assertTrue(failure(m,f.worker,request) instanceof IllegalArgumentException);
        Assert.assertFalse(Files.exists(f.root.resolve("CHECKPOINT.json")));
    }
    @Test public void mismatchedJournalCountCannotProduceSnapshot()throws Exception {
        Method m=method("checkpoint",String.class);Fixture f=new Fixture();Files.writeString(f.root.resolve("starts.jsonl"),"{}\n");
        Assert.assertTrue(failure(m,f.worker,f.request()) instanceof IllegalStateException);
        Assert.assertFalse(Files.exists(f.root.resolve("CHECKPOINT.json")));
    }
}
