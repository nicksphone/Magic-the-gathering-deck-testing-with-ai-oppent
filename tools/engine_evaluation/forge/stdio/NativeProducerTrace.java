// SPDX-License-Identifier: GPL-3.0-or-later
// Owned observational adapter for pinned Forge61e944 + owned input patches.
// Read-only native references/caller evidence. Never changes a native action/result.
package forge.evaluation;

import com.google.gson.*;
import forge.game.card.Card;
import forge.game.card.CardView;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.SpellAbilityView;
import forge.gamemodes.match.input.Input;
import forge.gamemodes.match.input.InputPassPriority;
import forge.gamemodes.net.ProtocolMethod;
import forge.gamemodes.net.event.GuiGameEvent;
import forge.player.PlayerControllerHuman;
import forge.util.ThreadUtil;
import java.lang.reflect.Field;
import java.util.*;
import javax.swing.SwingUtilities;

final class NativeProducerTrace {
    private static final Gson JSON=new Gson();
    private final ThreadLocal<Dispatch> active=new ThreadLocal<>();
    private final Map<Integer,Dispatch> removed=new LinkedHashMap<>();
    private final Map<Integer,JsonObject> completed=new HashMap<>();
    private String observationFailure;

    static final class Dispatch {
        final int start;final Input input;final long generation;final Player actor;
        final JsonObject entry;
        SpellAbility selected;Card source;boolean popped;
        SpellAbility poppedAbility;Card poppedSource;
        RetainedProvenance popFacts;
        ConfirmedReference<SpellAbility> claim;
        long after;JsonElement removalChain;
        Dispatch(int start,Input input,long generation,Player actor,JsonObject entry) {
            this.start=start;this.input=input;this.generation=generation;this.actor=actor;this.entry=entry;
        }
    }
    static final class Dialog {
        final JsonObject entry;
        final IdentityHashMap<SpellAbilityView,SpellAbility> offered=new IdentityHashMap<>();
        final Dispatch synchronous;
        Dispatch resumed;
        Dialog(JsonObject entry,Dispatch synchronous) {this.entry=entry;this.synchronous=synchronous;}
    }
    private static JsonObject entry() {
        JsonObject p=new JsonObject();p.addProperty("role","INELIGIBLE");
        p.add("lane",JSON.toJsonTree(Map.of("edt",SwingUtilities.isEventDispatchThread(),"native_game",ThreadUtil.isGameThread())));
        List<Map<String,Object>> frames=StackWalker.getInstance().walk(s->s.map(f->Map.<String,Object>of(
                "class",f.getClassName(),"method",f.getMethodName(),"file",Objects.requireNonNullElse(f.getFileName(),""),"line",f.getLineNumber())).toList());
        p.add("producer_chain",JSON.toJsonTree(frames));return p;
    }
    synchronized Dispatch enterDispatch(int start,Input input,long generation,Player actor) {
        if(active.get()!=null)throw new IllegalStateException("nested_dispatch_trace_context");
        Dispatch d=new Dispatch(start,input,generation,actor,entry());active.set(d);return d;
    }
    void leaveDispatch() {active.remove();}

    synchronized JsonObject publicationEdge(String form,int parent) {
        Dispatch context=active.get();
        if((context==null&&parent!=-1)||(context!=null&&context.start!=parent))
            throw new IllegalStateException("publication_context_parent_mismatch");
        JsonObject actual=entry(),e=new JsonObject();
        String kind=context==null?"ROOT":form.equals("BLOCKING_SEND_AND_WAIT")?"SYNCHRONOUS_CALL":"DEFERRED_INPUT_REQUEST";
        if(!Set.of("BLOCKING_SEND_AND_WAIT","INPUT_REQUEST_INVOKE_LATER").contains(form))throw new IllegalStateException("unknown_publication_form");
        e.addProperty("kind",kind);e.addProperty("producer_form",form);e.addProperty("parent_start",parent);
        e.addProperty("publication_parent_context",context!=null);
        e.add("publisher_lane",actual.get("lane").deepCopy());e.add("invocation_lane",actual.get("lane").deepCopy());
        e.add("producer_chain",actual.get("producer_chain").deepCopy());return e;
    }
    JsonObject inputInvocationEdge(JsonObject retained) {
        if(!retained.get("producer_form").getAsString().equals("INPUT_REQUEST_INVOKE_LATER"))throw new IllegalStateException("not_deferred_input_producer");
        JsonObject e=retained.deepCopy();e.add("invocation_lane",entry().get("lane").deepCopy());return e;
    }

    // Called outside native queue monitor. Observes a successful pop, NOT latch release.
    synchronized void removed(Input input,long before,long after) {
        try {
            Dispatch d=active.get();
            if(d==null||d.input!=input||d.generation!=before||!(input instanceof InputPassPriority p))return;
            List<SpellAbility> chosen=p.getChosenSa();
            if(chosen==null||chosen.size()!=1||d.selected==null||chosen.get(0)!=d.selected)return;
            if(d.selected.getHostCard()!=d.source||after<=before)return;
            d.popped=true;d.after=after;d.removalChain=entry().get("producer_chain").deepCopy();
            d.poppedAbility=d.selected;d.poppedSource=d.source;
            d.popFacts=new RetainedProvenance(captureRemovalFacts(d));
            d.claim=new ConfirmedReference<>(d.poppedAbility);
            removed.put(d.start,d);
        } catch(RuntimeException error) {
            observationFailure=error.getClass().getName(); // Do not interrupt native stop/latch lifecycle.
        }
    }

    synchronized Dialog enterDialog(GuiGameEvent call,Player actor,PlayerControllerHuman controller) {
        Dialog d=new Dialog(entry(),active.get());
        if(call.getMethod()!=ProtocolMethod.getAbilityToPlay)return d;
        Object[] a=call.getObjects();
        if(!(a[0] instanceof CardView source)||!(a[1] instanceof List<?> views))return d;
        try {
            // Native mapping was established by this producer immediately before GUI call.
            // No getView() mutation, ID-based native reconstruction or cache writes.
            Field field=PlayerControllerHuman.class.getDeclaredField("spellViewCache");field.setAccessible(true);
            Object value=field.get(controller);if(!(value instanceof Map<?,?> map))return d;
            Map<SpellAbilityView,SpellAbility> complete=IdentityOfferSnapshot.capture(views,map,
                    SpellAbilityView.class,SpellAbility.class,(view,sa)->
                    sa.getId()==view.getId()&&sa.getHostCard().getId()==source.getId());
            if(complete.isEmpty()||complete.size()!=views.size())return d;
            d.offered.putAll(complete);
            if(d.synchronous!=null)return d;
            JsonObject lane=d.entry.getAsJsonObject("lane");
            if(lane.get("edt").getAsBoolean()||!lane.get("native_game").getAsBoolean()||
                    !CausalCompletionVerifier.chain(d.entry,"producer_chain",CausalCompletionVerifier.GAME))return d;
            List<Dispatch> matches=new ArrayList<>();
            for(Dispatch origin:removed.values()) {
                if(origin.actor!=actor||origin.popFacts==null||origin.claim==null||!origin.claim.available())continue;
                for(var item:d.offered.entrySet())if(item.getValue()==origin.poppedAbility&&
                        item.getValue().getHostCard()==origin.poppedSource&&item.getValue().getActivatingPlayer()==actor&&
                        source==item.getKey().getHostCard()) {matches.add(origin);break;}
            }
            var unique=ConfirmedReference.uniqueAvailable(matches.stream().map(origin->origin.claim).toList());
            if(unique.isPresent())for(Dispatch origin:matches)if(origin.claim==unique.get())d.resumed=origin;
        } catch(ReflectiveOperationException|RuntimeException error) {
            d.offered.clear(); // Unknown provenance never authorizes a displacement.
        }
        return d;
    }
    synchronized void dialogReturned(Dialog d,int start,List<Object> answer) {
        JsonObject p=d.entry.deepCopy();
        SpellAbility chosen=answer.size()==1&&answer.get(0) instanceof SpellAbilityView v?d.offered.get(v):null;
        if(d.synchronous!=null) {
            Dispatch origin=d.synchronous;
            if(chosen!=null) {
                if(origin.selected==null) {origin.selected=chosen;origin.source=chosen.getHostCard();}
                else if(origin.selected!=chosen) {origin.selected=null;origin.source=null;}
            }
            p.addProperty("role","SYNCHRONOUS_DIALOG");p.addProperty("origin_start",origin.start);
        } else if(d.resumed!=null&&d.resumed.claim.confirm(chosen)) {
            p.addProperty("role","RESUMED_ADDITIONAL_COST");link(p,d.resumed);
        }
        completed.put(start,p);
    }
    synchronized void dispatchReturned(Dispatch d) {
        JsonObject p=d.entry.deepCopy();
        if(d.popFacts!=null&&
                CausalCompletionVerifier.chain(removalProof(d),"removal_chain",CausalCompletionVerifier.POP)) {
            p.addProperty("role","ROOT_PRIORITY_REMOVED");link(p,d);
        }
        completed.put(d.start,p);
    }
    private static JsonObject removalProof(Dispatch d) {
        return d.popFacts.copy();
    }
    private static void link(JsonObject p,Dispatch d) {
        for(var fact:d.popFacts.copy().entrySet())p.add(fact.getKey(),fact.getValue());
    }
    private static JsonObject captureRemovalFacts(Dispatch d) {
        JsonObject p=new JsonObject();
        p.addProperty("origin_start",d.start);p.addProperty("actor",d.actor.getId());p.addProperty("source",d.poppedSource.getId());p.addProperty("ability",d.poppedAbility.getId());
        p.addProperty("input_generation",d.generation);p.addProperty("removal_after_generation",d.after);p.addProperty("input_class",d.input.getClass().getSimpleName());
        for(String key:List.of("successful_pop","same_input_reference","same_sa_reference","same_source_reference"))p.addProperty(key,true);
        p.addProperty("latch_release_observed",false);p.add("removal_chain",d.removalChain.deepCopy());
        return p;
    }
    synchronized JsonObject completion(int start) {
        if(observationFailure!=null)throw new IllegalStateException("producer_observer_failed_"+observationFailure);
        JsonObject result=completed.remove(start);
        if(result==null)throw new IllegalStateException("missing_actual_producer_context_"+start);
        return result;
    }
}
