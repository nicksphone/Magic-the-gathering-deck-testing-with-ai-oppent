// SPDX-License-Identifier: GPL-3.0-or-later
// Actual Forge native object/API regression fixtures; Forge Team/Card-Forge credits retained.
// TRUSTED UNIT POSES, not paid/natural games, events, winners or strength evidence.
package forge.evaluation;

import com.google.gson.*;
import forge.ai.simulation.SimulationTest;
import forge.game.*;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.player.Player;
import forge.game.spellability.*;
import forge.game.zone.ZoneType;
import forge.gamemodes.match.Selection;
import forge.gamemodes.match.input.*;
import forge.gamemodes.net.ProtocolGuiGame;
import forge.player.LobbyPlayerHuman;
import forge.player.PlayerControllerHuman;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import javax.swing.SwingUtilities;
import org.testng.Assert;
import org.testng.annotations.Test;

public class NativeStackBoundaryTest extends SimulationTest {
    private static final Gson JSON=new Gson();
    private static void set(Object o,String name,Object value)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);f.set(o,value);
    }
    private static Object field(Object o,String name)throws Exception {
        Field f=NativeHumanWorker.class.getDeclaredField(name);f.setAccessible(true);return f.get(o);
    }
    private static Object call(Object o,String name,Class<?>[] types,Object... values)throws Exception {
        Method m=NativeHumanWorker.class.getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(o,values);
    }
    private static void drainEdt()throws Exception { SwingUtilities.invokeAndWait(()->{}); }
    private static List<SpellAbilityStackInstance> entries(Game game) {
        List<SpellAbilityStackInstance> out=new ArrayList<>();for(var e:game.getStack())out.add(e);return out;
    }
    private List<SpellAbilityStackInstance> pair(Game game,Player owner,ZoneType zone) {
        Card source=addCardToZone("Prodigal Pyromancer",owner,zone);
        SpellAbility a=source.getSpellAbilities().stream().filter(s->!s.isSpell()).findFirst().orElseThrow();
        a.setActivatingPlayer(owner);a.getTargets().add(game.getPlayers().get(1-game.getPlayers().indexOf(owner)));
        SpellAbility b=a.copy(source,true);b.setActivatingPlayer(owner);
        game.getStack().add(a);game.getStack().add(b);
        List<SpellAbilityStackInstance> out=entries(game);Assert.assertEquals(out.size(),2);
        Assert.assertEquals(out.get(0).getSourceCard().getId(),out.get(1).getSourceCard().getId());
        Assert.assertNotEquals(out.get(0).getId(),out.get(1).getId());return out;
    }
    @SuppressWarnings("unchecked")
    private static List<String> tokens(Map<String,Object> question) {
        List<String> out=new ArrayList<>();for(Object row:(List<?>)question.get("choices"))out.add((String)((Map<?,?>)row).get("token"));return out;
    }
    @Test public void realCurrentStackViewsStayDistinctForSamePhysicalSource() {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(0);var es=pair(game,actor,ZoneType.Battlefield);ActorBoundary b=new ActorBoundary(actor);
        Map<?,?> a=(Map<?,?>)b.describe(es.get(0).getView()),c=(Map<?,?>)b.describe(es.get(1).getView());
        Assert.assertEquals(a.keySet(),Set.of("stack_id","source"));Assert.assertNotEquals(a.get("stack_id"),c.get("stack_id"));
        Assert.assertEquals(((Map<?,?>)a.get("source")).get("card_id"),((Map<?,?>)c.get("source")).get("card_id"));
    }
    @Test public void foreignRemovedAndSameIdAliasViewsFailClosed() {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(0);var es=pair(game,actor,ZoneType.Battlefield);ActorBoundary b=new ActorBoundary(actor);StackItemView view=es.get(0).getView();
        Assert.expectThrows(IllegalArgumentException.class,()->b.describe(new StackItemView(view.getId(),game.getTracker())));
        Game foreign=initAndCreateGame();var other=pair(foreign,foreign.getPlayers().get(0),ZoneType.Battlefield);
        Assert.expectThrows(IllegalArgumentException.class,()->b.describe(other.get(0).getView()));
        game.getStack().remove(es.get(0));Assert.expectThrows(IllegalArgumentException.class,()->b.describe(view));
    }
    @Test public void nativeViewTokensRejectRemovedWrongActorAndReplay() {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(0);var es=pair(game,actor,ZoneType.Battlefield);ActorBoundary b=new ActorBoundary(actor);
        Map<String,Object> q=b.offer("stack",List.of(es.get(0).getView(),es.get(1).getView()),1,1);String id=(String)q.get("request_id");var ts=tokens(q);
        Assert.expectThrows(IllegalArgumentException.class,()->b.answer(game.getPlayers().get(1),id,List.of(ts.get(0))));
        game.getStack().remove(es.get(0));Assert.expectThrows(IllegalArgumentException.class,()->b.answer(actor,id,List.of(ts.get(0))));
        Assert.assertSame(b.answer(actor,id,List.of(ts.get(1))).get(0),es.get(1).getView());
        Assert.expectThrows(IllegalArgumentException.class,()->b.answer(actor,id,List.of(ts.get(1))));
    }
    @Test public void hiddenCurrentSourceRemainsRedactedWithoutRawText() {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(0);var es=pair(game,game.getPlayers().get(1),ZoneType.Hand);ActorBoundary b=new ActorBoundary(actor);
        Map<?,?> value=(Map<?,?>)b.describe(es.get(0).getView());Assert.assertEquals(value.get("source"),Map.of("hidden",true));
        Assert.assertFalse(JSON.toJson(value).contains("Prodigal Pyromancer"));Assert.assertEquals(value.keySet(),Set.of("stack_id","source"));
    }
    private final class Fixture {
        final Game game=initAndCreateGame();final Player actor=game.getPlayers().get(0);
        final StringWriter output=new StringWriter();final NativeHumanWorker worker=new NativeHumanWorker(new PrintWriter(output));
        final PlayerControllerHuman human=new PlayerControllerHuman(game,actor,new LobbyPlayerHuman("UNIT-NATIVE"));
        final ProtocolGuiGame gui=new ProtocolGuiGame(worker);
        Fixture()throws Exception {
            Path root=Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")),"native-stack-unit-");
            set(worker,"actor",actor);set(worker,"boundary",new ActorBoundary(actor));set(worker,"gui",gui);set(worker,"evidence",root);
            human.setGui(gui);gui.setGameController(actor.getView(),human);gui.setGameView(game.getView());
            call(worker,"observeInputReadiness",new Class<?>[]{});
        }
        void show(InputSynchronized input)throws Exception { human.getInputQueue().setInput(input);drainEdt(); }
        JsonObject latestChoice() {
            JsonObject out=null;for(String line:output.toString().split("\\R")){JsonObject v=JsonParser.parseString(line).getAsJsonObject();if(v.get("event").getAsString().equals("choice"))out=v;}Assert.assertNotNull(out,"actual Worker choice required");return out;
        }
    }
    @Test public void existingControllerSelectsTheExactNativeStackInstances()throws Exception {
        Fixture f=new Fixture();var es=pair(f.game,f.actor,ZoneType.Battlefield);InputSelectStackItems input=new InputSelectStackItems(f.human,2,2,es,null);f.show(input);
        SwingUtilities.invokeAndWait(()->f.human.selectStackItem(es.get(0).getView()));Assert.assertEquals(input.getSelected(),List.of(es.get(0)));
        SwingUtilities.invokeAndWait(()->f.human.selectStackItem(es.get(1).getView()));Assert.assertEquals(input.getSelected(),es);Assert.assertNull(f.human.getInputQueue().getInput());
    }
    @Test public void stackMetadataUsesNativeSelectedNotRetainedTargetHighlights()throws Exception {
        Fixture f=new Fixture();var es=pair(f.game,f.actor,ZoneType.Battlefield);Card card=addCardToZone("Counterspell",f.actor,ZoneType.Hand);SpellAbility sa=card.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();sa.setActivatingPlayer(f.actor);sa.getTargets().add(es.get(1).getSpellAbility());
        InputSelectStackItems input=new InputSelectStackItems(f.human,2,2,es,sa);f.show(input);
        JsonObject meta=f.latestChoice().getAsJsonObject("info").getAsJsonObject("stack_selection");Assert.assertEquals(meta.getAsJsonArray("chosen").size(),0);Assert.assertFalse(meta.has("min"));Assert.assertFalse(meta.has("max"));
        SwingUtilities.invokeAndWait(()->f.human.selectStackItem(es.get(0).getView()));
        JsonArray chosen=f.latestChoice().getAsJsonObject("info").getAsJsonObject("stack_selection").getAsJsonArray("chosen");Assert.assertEquals(chosen.size(),1);Assert.assertEquals(chosen.get(0).getAsJsonObject().get("stack_id").getAsInt(),es.get(0).getId());
    }
    @Test public void entityCostHighlightsOutsideOverlapAndDuplicateAreNotSelections()throws Exception {
        // INTERNAL native cost-input fixture, not a genuine paid game.
        Fixture f=new Fixture();List<Card> valid=new ArrayList<>();for(int i=0;i<4;i++)valid.add(addCard("Grizzly Bears",f.actor));
        Card outside=addCard("Hill Giant",f.game.getPlayers().get(1));Card source=addCard("Prodigal Pyromancer",f.actor);SpellAbility sa=source.getSpellAbilities().stream().filter(s->!s.isSpell()).findFirst().orElseThrow();sa.setActivatingPlayer(f.actor);sa.getTargets().add(outside);
        var choices=new forge.util.collect.FCollection<Card>();choices.addAll(valid);InputSelectEntitiesFromList<Card> input=new InputSelectEntitiesFromList<>(f.human,2,2,choices,sa);input.setMessage("INTERNAL NATIVE FIXTURE select %d more");f.human.getKeptMarks().add(outside.getView());f.show(input);
        Assert.assertFalse(((Selection)field(f.worker,"selection")).chosen().isEmpty(),"actual unoffered highlight must exist");
        Assert.assertEquals(f.latestChoice().getAsJsonObject("info").getAsJsonObject("selection").getAsJsonArray("chosen").size(),0);
        sa.resetTargets();sa.getTargets().add(valid.get(0));
        f.human.getKeptMarks().clear();f.human.getKeptMarks().add(valid.get(0).getView());
        SwingUtilities.invokeAndWait(()->input.selectCard(valid.get(0),null,null));
        List<?> highlighted=((Selection)field(f.worker,"selection")).chosen();Assert.assertTrue(highlighted.size()>=2,"actual overlap must duplicate UI highlight");
        JsonArray chosen=f.latestChoice().getAsJsonObject("info").getAsJsonObject("selection").getAsJsonArray("chosen");Assert.assertEquals(chosen.size(),1);Assert.assertEquals(chosen.get(0).getAsJsonObject().get("card_id").getAsInt(),valid.get(0).getId());Assert.assertEquals(input.getSelected().size(),1);
    }
    @Test public void unsupportedPresentationFailsWorkerAndInvalidatesWithoutWaiting()throws Exception {
        Fixture f=new Fixture();Card source=addCard("Grizzly Bears",f.actor);
        InputSyncronizedBase bad=new InputSyncronizedBase(f.human){
            @Override public String getActivateAction(Card card){return null;}
            @Override protected Selection getSelection(){return new Selection(List.of(),0,0,List.of(source.getView().getCurrentState()),List.of(),List.of());}
            @Override protected void showMessage(){showMessage("INTERNAL NEGATIVE unsupported native value");}
        };
        f.show(bad);Assert.assertEquals(field(f.worker,"failed"),Boolean.TRUE);Assert.assertNull(field(f.worker,"request"));
    }
    private record CounterPose(Game game,SpellAbility target,SpellAbility counter) { }
    private CounterPose counterPose() {
        Game game=initAndCreateGame();Player actor=game.getPlayers().get(0),opp=game.getPlayers().get(1);
        Card bolt=addCardToZone("Lightning Bolt",opp,ZoneType.Hand);SpellAbility target=bolt.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();target.setActivatingPlayer(opp);target.getTargets().add(actor);game.getStack().add(target);
        target=entries(game).get(0).getSpellAbility();Card counter=addCardToZone("Counterspell",actor,ZoneType.Hand);SpellAbility sa=counter.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();sa.setActivatingPlayer(actor);sa.getTargets().add(target);game.getStack().add(sa);return new CounterPose(game,target,entries(game).get(0).getSpellAbility());
    }
    @Test public void actualCounterspellTargetSnapshotRetainsSaIdentityAndStrictReference()throws Exception {
        CounterPose p=counterPose();NativeHumanWorker w=new NativeHumanWorker(new PrintWriter(new StringWriter()));JsonElement state=JSON.toJsonTree(call(w,"nativeState",new Class<?>[]{Game.class},p.game()));
        JsonObject encoded=null;for(JsonElement row:state.getAsJsonObject().getAsJsonArray("stack"))for(JsonElement t:row.getAsJsonObject().getAsJsonArray("targets"))if(t.isJsonObject()&&t.getAsJsonObject().has("type"))encoded=t.getAsJsonObject();
        Assert.assertNotNull(encoded);Assert.assertEquals(encoded.get("type").getAsString(),"spell_ability");Assert.assertEquals(encoded.get("ability_id").getAsInt(),p.target().getId());Assert.assertEquals(encoded.getAsJsonObject("host").get("card_id").getAsInt(),p.target().getHostCard().getId());Assert.assertEquals(encoded.getAsJsonObject("host").get("game_timestamp").getAsLong(),p.target().getHostCard().getGameTimestamp());Assert.assertFalse(encoded.has("stack_id"));
        // LABELLED SYNTHETIC verifier EOF marker, NOT an engine event/game outcome.
        JsonElement end=JSON.toJsonTree(Map.of("fixture","SYNTHETIC_VERIFIER_EOF_NOT_GAME_RESULT"));Map<String,List<JsonElement>> reference=Map.of("starts",List.of(),"completions",List.of(),"native",List.of(state),"final",List.of(end));
        CausalCompletionVerifier strict=new CausalCompletionVerifier(reference);strict.accept("native",state);strict.accept("final",end);strict.finish();JsonElement changed=state.deepCopy();changed.getAsJsonObject().addProperty("SYNTHETIC_EXTRA_FIELD",true);CausalCompletionVerifier negative=new CausalCompletionVerifier(reference);Assert.expectThrows(IllegalStateException.class,()->negative.accept("native",changed));
    }
    @Test public void unknownSnapshotTargetMarksFailedInsteadOfSilentOmission()throws Exception {
        CounterPose p=counterPose();
        // INTERNAL NEGATIVE future/unknown native target; no fake event or game result.
        p.counter().setTargets(new TargetChoices(){@Override public Iterator<GameObject> iterator(){return List.<GameObject>of(new GameObject(){}).iterator();}});
        NativeHumanWorker w=new NativeHumanWorker(new PrintWriter(new StringWriter()));InvocationTargetException error=Assert.expectThrows(InvocationTargetException.class,()->call(w,"nativeState",new Class<?>[]{Game.class},p.game()));Assert.assertTrue(error.getCause()instanceof IllegalStateException);Assert.assertEquals(field(w,"failed"),Boolean.TRUE);
    }
}
