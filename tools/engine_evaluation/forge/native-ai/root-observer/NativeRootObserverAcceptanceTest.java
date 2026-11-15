// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled tests of Forge Team/Card-Forge native AI instrumentation only.
// GPL version 3 or later, WITHOUT ANY WARRANTY; retain upstream Forge LICENSE.
// No naturally dealt games, policy edits, root-hook calls as replacement choosers,
// candidate re-enumeration, or fabricated legal-opportunity counts.
package forge.evaluation;

import forge.LobbyPlayer;
import forge.ai.AiPlayDecision;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.util.MyRandom;
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.RecordComponent;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.TreeMap;
import java.util.function.Consumer;
import org.testng.Assert;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public final class NativeRootObserverAcceptanceTest extends SimulationTest {
    @Override @BeforeMethod(alwaysRun=true)
    public void initializeModel() { super.initializeModel(); }

    static final class CountingController extends PlayerControllerAi {
        int calls;
        List<SpellAbility> last;
        CountingController(Game game, Player player, LobbyPlayer lobby) { super(game,player,lobby); }
        @Override public List<SpellAbility> chooseSpellAbilityToPlay() {
            calls++;
            last=super.chooseSpellAbilityToPlay();
            return last;
        }
    }
    record Pose(Game game, Player actor, Player other, CountingController controller) { }
    record Measurement(String before, String after, String selected, byte[] rngBefore, byte[] rngAfter, long draws) { }

    @DataProvider(name="seats") public Object[][] seats() { return new Object[][] {{0},{1}}; }
    @DataProvider(name="poses") public Object[][] poses() { return new Object[][] {{0,true},{1,true},{0,false},{1,false}}; }
    @DataProvider(name="privacy") public Object[][] privacy() { return new Object[][] {{0,false},{1,false},{0,true},{1,true}}; }

    static Object field(Object record,String name) throws Exception {
        try { return record.getClass().getMethod(name).invoke(record); }
        catch(InvocationTargetException error) { throw new AssertionError("record accessor failed",error.getCause()); }
    }
    @SuppressWarnings("unchecked") static List<Object> list(Object value) { return (List<Object>)value; }
    static long number(Object record,String name) throws Exception { return ((Number)field(record,name)).longValue(); }
    static void observer(CountingController c,Consumer<Object> sink) throws Exception {
        try { c.getAi().getClass().getMethod("setDecisionObserver",Consumer.class).invoke(c.getAi(),sink); }
        catch(NoSuchMethodException error) { Assert.fail("MISSING_NATIVE_ROOT_CANDIDATE_HOOK",error); }
    }
    static long failures(CountingController c) throws Exception {
        return ((Number)c.getAi().getClass().getMethod("getDecisionObserverFailures").invoke(c.getAi())).longValue();
    }
    static byte[] rng() throws Exception {
        ByteArrayOutputStream b=new ByteArrayOutputStream();
        try(ObjectOutputStream o=new ObjectOutputStream(b)){o.writeObject(MyRandom.getRandom());}
        return b.toByteArray();
    }

    Pose pose(int seat,boolean actionable,boolean ordered,boolean land,boolean hidden,boolean faceDown) {
        MyRandom.setRandom(new Random(2026110721L));
        List<RegisteredPlayer> players=new ArrayList<>();
        for(int i=0;i<2;i++) {
            Deck deck=new Deck("CONTROLLED root-observer fixture");deck.getMain().add(i==seat?"Mountain":"Plains",60);
            LobbyPlayerAi lobby=new LobbyPlayerAi("controlled-seat-"+i,null) {
                @Override public Player createIngamePlayer(Game game,int id) {
                    Player p=new Player(getName(),game,id);p.setFirstController(new CountingController(game,p,this));return p;
                }
            };
            lobby.setAiProfile("Default");players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);rules.setAllowCheatShuffle(false);
        Game game=new Game(players,rules,new Match(rules,players,"CONTROLLED native root observation"));
        game.setAge(GameStage.Play);game.AI_TIMEOUT=5;game.AI_FLAT_MONTE_CARLO=false;
        game.AI_FLAT_MONTE_CARLO_MAX=false;game.AI_FLAT_MONTE_CARLO_LITE=false;
        Player actor=game.getPlayers().get(seat),other=game.getPlayers().get(1-seat);
        actor.setLife(20,null);other.setLife(3,null);
        game.getPhaseHandler().devModeSet(land?PhaseType.MAIN1:PhaseType.END_OF_TURN,land?actor:other);
        if(actionable) {
            addCardToZone("Mountain",actor,ZoneType.Battlefield);
            addCardToZone("Lightning Bolt",actor,ZoneType.Hand);
            if(ordered)addCardToZone("Searing Blaze",actor,ZoneType.Hand);
        }
        if(land)addCardToZone("Mountain",actor,ZoneType.Hand);
        if(hidden) {
            Card secret=addCardToZone("Ancestral Recall",other,ZoneType.Library);
            if(faceDown)secret.turnFaceDown(true);
        }
        for(int i=0;i<55;i++) {
            addCardToZone("Mountain",actor,ZoneType.Library);
            addCardToZone("Plains",other,ZoneType.Library);
        }
        game.getPhaseHandler().setPriority(actor);
        MyRandom.setRandom(new Random(2026110721L));
        return new Pose(game,actor,other,(CountingController)actor.getController());
    }
    static List<SpellAbility> choose(Pose p) {
        List<SpellAbility> chosen=p.controller.chooseSpellAbilityToPlay();
        Assert.assertSame(chosen,p.controller.last,"Recorder must not replace the native list");return chosen;
    }
    static String targets(SpellAbility sa) {
        StringBuilder out=new StringBuilder();
        for(var target:sa.getTargets().getTargetEntities()) {
            if(target instanceof Player p)out.append("P:").append(p.getName());
            else if(target instanceof Card c)out.append("C:").append(c.getName());
        }
        return out.toString();
    }
    static String selected(List<SpellAbility> all) {
        if(all==null)return "NULL";
        List<String> values=new ArrayList<>();
        for(SpellAbility sa:all)values.add(sa.getHostCard().getName()+"|"+sa.getApi()+"|"+targets(sa));
        return values.toString();
    }
    static String state(Pose p) {
        // Existing ability getters only; never calls getAllPossibleAbilities or any policy/payment query.
        StringBuilder out=new StringBuilder();
        for(Player player:p.game.getPlayers()) {
            out.append(player.getName()).append(':').append(player.getLife()).append(':').append(player.getLandsPlayedThisTurn());
            for(ZoneType z:new ZoneType[]{ZoneType.Hand,ZoneType.Library,ZoneType.Battlefield,ZoneType.Graveyard,ZoneType.Exile}) {
                out.append(z);
                for(Card card:player.getCardsIn(z)) {
                    out.append('[').append(card.getName()).append('|').append(card.isTapped()).append('|').append(card.isFaceDown());
                    for(SpellAbility sa:card.getSpellAbilities())out.append('{').append(sa.getApi()).append(':').append(new TreeMap<>(sa.getMapParams())).append(':').append(targets(sa)).append('}');
                    out.append(']');
                }
            }
        }
        return out.toString();
    }
    static Object oneTrace(List<Object> traces) {
        Assert.assertEquals(traces.size(),1,"Exactly one publication per ordinary root");return traces.get(0);
    }
    static List<Object> visits(Object trace,String stage) throws Exception {
        List<Object> result=new ArrayList<>();
        for(Object v:list(field(trace,"visits")))if(stage.equals(field(v,"stage")))result.add(v);
        return result;
    }
    static void common(Pose p,Object t,List<SpellAbility> chosen) throws Exception {
        Assert.assertEquals(number(t,"gameId"),p.game.getId());
        Assert.assertEquals(number(t,"actorId"),p.actor.getId());
        Assert.assertEquals(number(t,"turn"),p.game.getPhaseHandler().getTurn());
        Assert.assertEquals(field(t,"phase"),p.game.getPhaseHandler().getPhase().name());
        Assert.assertEquals(field(t,"returnedNull"),chosen==null);
        Assert.assertEquals(field(t,"completeLegalActionSet"),Boolean.FALSE);
        Assert.assertEquals(field(t,"truncated"),Boolean.FALSE);
        Assert.assertEquals(field(t,"outcome"),chosen==null||chosen.isEmpty()?"no_action":"selected");
        List<Object> actions=list(field(t,"selected"));Assert.assertEquals(actions.size(),chosen==null?0:chosen.size());
        if(chosen!=null)for(int i=0;i<chosen.size();i++) {
            Assert.assertEquals(number(actions.get(i),"abilityId"),chosen.get(i).getId());
            Assert.assertEquals(number(actions.get(i),"cardId"),chosen.get(i).getHostCard().getId());
        }
        for(Object v:list(field(t,"visits")))Assert.assertNull(field(v,"affordability"),"Policy opinion never certifies affordability");
    }

    @Test(groups="actual-root",dataProvider="poses")
    public void ordinaryRootCapturesSelectionOrActualEmptyInput(int seat,boolean actionable) throws Exception {
        Pose p=pose(seat,actionable,false,false,false,false);List<Object> traces=new ArrayList<>();
        observer(p.controller,traces::add);List<SpellAbility> chosen=choose(p);Object t=oneTrace(traces);
        Assert.assertEquals(p.controller.calls,1);common(p,t,chosen);
        if(actionable) {
            Assert.assertNotNull(chosen);Assert.assertEquals(chosen.get(0).getHostCard().getName(),"Lightning Bolt");
            Assert.assertEquals(chosen.get(0).getTargets().getFirstTargetedPlayer(),p.other);
            Assert.assertFalse(visits(t,"CONSIDERED").isEmpty(),"Actual eval-worker visits must survive root correlation");
            Assert.assertFalse(visits(t,"OPINION").isEmpty());
        } else {
            Assert.assertTrue(chosen==null||chosen.isEmpty());
            List<Object> offered=visits(t,"OFFERED");Assert.assertFalse(offered.isEmpty(),"Actual empty list stage must be observed");
            Assert.assertNotNull(field(offered.get(0),"actions"));Assert.assertTrue(list(field(offered.get(0),"actions")).isEmpty());
            Assert.assertTrue(visits(t,"CONSIDERED").isEmpty());
        }
    }

    @Test(groups="actual-root",dataProvider="seats")
    public void offeredOrderPrecedesNativeSortAndEvalOpinionCorrelates(int seat) throws Exception {
        Pose p=pose(seat,true,true,false,false,false);List<Object> traces=new ArrayList<>();
        observer(p.controller,traces::add);choose(p);Object t=oneTrace(traces);
        Object offered=visits(t,"OFFERED").get(0);List<String> order=new ArrayList<>();
        for(Object action:list(field(offered,"actions"))) {
            String name=(String)field(action,"name");if("Lightning Bolt".equals(name)||"Searing Blaze".equals(name))order.add(name);
        }
        Assert.assertEquals(order,List.of("Lightning Bolt","Searing Blaze"),"Offer snapshot must retain known hand insertion order before sort");
        List<Object> considered=visits(t,"CONSIDERED");Assert.assertFalse(considered.isEmpty());
        Assert.assertEquals(field(list(field(considered.get(0),"actions")).get(0),"name"),"Searing Blaze","Native higher-cost-first evaluation must not overwrite OFFERED order");
        Set<Long> batches=new HashSet<>();for(Object v:visits(t,"OFFERED"))batches.add(number(v,"batch"));
        for(Object v:considered)Assert.assertTrue(batches.contains(number(v,"batch")));
        List<Object> opinions=visits(t,"OPINION");Assert.assertFalse(opinions.isEmpty());
        for(Object v:opinions) {
            Assert.assertTrue(batches.contains(number(v,"batch")));Assert.assertNotNull(field(v,"opinion"));
            AiPlayDecision.valueOf((String)field(v,"opinion"));Assert.assertNull(field(v,"affordability"));
        }
    }

    Measurement measured(int seat,boolean actionable,boolean enabled) throws Exception {
        Pose p=pose(seat,actionable,false,false,false,false);List<Object> traces=new ArrayList<>();
        observer(p.controller,enabled?traces::add:null);
        String before=state(p);byte[] rngBefore=rng();long draws=MyRandom.callCount();
        List<SpellAbility> chosen=choose(p);byte[] rngAfter=rng();long delta=MyRandom.callCount()-draws;
        String after=state(p);Assert.assertEquals(p.controller.calls,1);
        Assert.assertEquals(traces.size(),enabled?1:0);
        return new Measurement(before,after,selected(chosen),rngBefore,rngAfter,delta);
    }
    @Test(groups="actual-root",dataProvider="poses")
    public void offOnEquivalentControlledStatesPreserveActionsTargetsInventoryAndExactRng(int seat,boolean actionable) throws Exception {
        Measurement off=measured(seat,actionable,false),on=measured(seat,actionable,true);
        Assert.assertEquals(on.before,off.before);Assert.assertEquals(on.after,off.after);
        Assert.assertEquals(on.selected,off.selected);Assert.assertEquals(on.draws,off.draws);
        Assert.assertTrue(Arrays.equals(on.rngBefore,off.rngBefore));Assert.assertTrue(Arrays.equals(on.rngAfter,off.rngAfter));
    }

    @Test(groups="actual-root",dataProvider="seats")
    public void throwingSinkIsIsolatedAndCountedWithoutReplacingNativeAction(int seat) throws Exception {
        Measurement off=measured(seat,true,false);Pose p=pose(seat,true,false,false,false,false);
        long before=failures(p.controller);observer(p.controller,t->{throw new IllegalStateException("SYNTHETIC_SINK_FAILURE");});
        List<SpellAbility> chosen=choose(p);
        Assert.assertEquals(failures(p.controller),before+1);Assert.assertEquals(p.controller.calls,1);
        Assert.assertEquals(selected(chosen),off.selected);Assert.assertTrue(Arrays.equals(rng(),off.rngAfter));
        Assert.assertEquals(state(p),off.after);
    }

    @SuppressWarnings({"rawtypes","unchecked"}) static void immutable(List<?> all) {
        try { ((List)all).add(null);Assert.fail("Observer retained mutable list"); }
        catch(UnsupportedOperationException expected) { }
    }
    static void scalarTree(Object value) throws Exception {
        if(value==null||value instanceof String||value instanceof Number||value instanceof Boolean)return;
        if(value instanceof List<?> all){immutable(all);for(Object x:all)scalarTree(x);return;}
        Assert.assertTrue(value.getClass().isRecord(),"Observer retained non-record engine object: "+value.getClass().getName());
        for(RecordComponent c:value.getClass().getRecordComponents())scalarTree(c.getAccessor().invoke(value));
    }
    @Test(groups="actual-root")
    public void actualPublishedValueIsDeeplyImmutableAndContainsOnlyScalars() throws Exception {
        Pose p=pose(0,true,true,false,false,false);List<Object> traces=new ArrayList<>();observer(p.controller,traces::add);choose(p);
        Object first=oneTrace(traces);scalarTree(first);String frozen=first.toString();
        choose(p);Assert.assertEquals(traces.size(),2);Assert.assertEquals(first.toString(),frozen,"Old publication must be detached/frozen");
        Assert.assertTrue(number(traces.get(1),"root")>number(first,"root"));
        scalarTree(traces.get(1));
    }

    @Test(groups="actual-root")
    public void distinctRootsAndActorsDoNotMixVisits() throws Exception {
        Pose p=pose(0,true,false,false,false,false);CountingController other=(CountingController)p.other.getController();
        List<Object> a=new ArrayList<>(),b=new ArrayList<>();observer(p.controller,a::add);observer(other,b::add);
        choose(p);String first=a.get(0).toString();choose(p);other.chooseSpellAbilityToPlay();
        Assert.assertEquals(a.size(),2);Assert.assertEquals(b.size(),1);Assert.assertEquals(a.get(0).toString(),first);
        Assert.assertTrue(number(a.get(1),"root")>number(a.get(0),"root"));
        for(Object trace:a)Assert.assertEquals(number(trace,"actorId"),p.actor.getId());
        Assert.assertEquals(number(b.get(0),"actorId"),p.other.getId());
        Assert.assertTrue(list(field(b.get(0),"selected")).isEmpty());
    }

    @Test(groups="actual-root",dataProvider="privacy")
    public void rootExcludesIneligibleHiddenHost(int seat,boolean faceDown) throws Exception {
        Pose p=pose(seat,true,false,false,true,faceDown);List<Object> traces=new ArrayList<>();observer(p.controller,traces::add);choose(p);
        int redacted=0;
        for(Object v:list(field(oneTrace(traces),"visits"))) {
            Object value=field(v,"actions");if(value==null)continue;
            for(Object action:list(value)) {
                Assert.assertNotEquals(field(action,"name"),"Ancestral Recall","Opponent hidden host name leaked");
                if(field(action,"cardId")==null) {
                    redacted++;Assert.assertNull(field(action,"abilityId"));Assert.assertNull(field(action,"name"));Assert.assertNull(field(action,"api"));
                }
            }
        }
        Assert.assertEquals(redacted,0,"This fixture is pre-filtered by native ability eligibility before OFFERED; root exclusion is observed, not identity-redaction coverage");
    }

    @Test(groups="actual-root",dataProvider="seats")
    public void selectedLandShortcutHasNoFabricatedOfferedVisit(int seat) throws Exception {
        Pose p=pose(seat,false,false,true,false,false);List<Object> traces=new ArrayList<>();observer(p.controller,traces::add);
        List<SpellAbility> chosen=choose(p);Object t=oneTrace(traces);common(p,t,chosen);
        Assert.assertNotNull(chosen);Assert.assertTrue(chosen.get(0).isLandAbility());
        Assert.assertTrue(visits(t,"OFFERED").isEmpty(),"Uncalled list path is no stage, not fabricated empty list");
        Assert.assertTrue(visits(t,"CONSIDERED").isEmpty());Assert.assertEquals(field(t,"completeLegalActionSet"),Boolean.FALSE);
    }
}
