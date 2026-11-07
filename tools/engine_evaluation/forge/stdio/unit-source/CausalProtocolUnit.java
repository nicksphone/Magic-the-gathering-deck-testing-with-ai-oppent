// SPDX-License-Identifier: GPL-3.0-or-later
// Labelled SYNTHETIC protocol-only fixtures. No Forge Game/Card objects or init.
package forge.evaluation;
import com.google.gson.*;
import java.util.*;
public final class CausalProtocolUnit {
    static final Gson J=new Gson(); static int tests;
    static void need(boolean v,String s) { if(!v) throw new AssertionError(s); }
    static JsonObject obj(Object v) { return J.toJsonTree(v).getAsJsonObject(); }
    static List<Map<String,Object>> chain(String... pairs) {
        List<Map<String,Object>> r=new ArrayList<>();
        for(String pair:pairs) {int i=pair.lastIndexOf('#');r.add(Map.of("class",pair.substring(0,i),"method",pair.substring(i+1),"file","SYNTHETIC.java","line",1));}return r;
    }
    static final List<Map<String,Object>> GAME=chain("forge.player.PlayerControllerHuman#getAbilityToPlay","forge.game.player.PlayerController#getAbilityToPlay","forge.game.player.PlaySpellAbility#chooseOptionalAdditionalCosts","forge.game.player.PlaySpellAbility#playSpellAbility","forge.player.PlayerControllerHuman#playChosenSpellAbility","forge.game.phase.PhaseHandler#mainLoopStep");
    static final List<Map<String,Object>> POP=chain("forge.gamemodes.match.input.InputQueue#removeInput","forge.gamemodes.match.input.InputSyncronizedBase#stop","forge.gamemodes.match.input.InputPassPriority#onCardSelected","forge.gamemodes.match.input.InputBase#selectCard","forge.gamemodes.match.input.InputProxy#selectCard","forge.player.PlayerControllerHuman#selectCard");
    static JsonObject proof(String role) {
        JsonObject p=obj(Map.of("role",role,"lane",Map.of("edt",!role.equals("RESUMED_ADDITIONAL_COST"),"native_game",role.equals("RESUMED_ADDITIONAL_COST")),"producer_chain",role.equals("RESUMED_ADDITIONAL_COST")?GAME:chain("forge.evaluation.NativeHumanWorker#publishInput")));
        if(!role.equals("INELIGIBLE")) {
            p.addProperty("origin_start",0);p.addProperty("actor",7);p.addProperty("source",11);p.addProperty("ability",23);
            p.addProperty("input_generation",4);p.addProperty("removal_after_generation",5);p.addProperty("input_class","InputPassPriority");
            for(String key:List.of("successful_pop","same_input_reference","same_sa_reference","same_source_reference"))p.addProperty(key,true);
            p.addProperty("latch_release_observed",false);p.add("removal_chain",J.toJsonTree(POP));
        }return p;
    }
    static JsonObject edge(String kind,String form,int parent,boolean game) {
        return obj(Map.of("kind",kind,"producer_form",form,"parent_start",parent,
            "publication_parent_context",parent>=0,"publisher_lane",Map.of("edt",!game,"native_game",game),
            "producer_chain",chain("forge.evaluation.NativeHumanWorker#publish"),
            "invocation_lane",Map.of("edt",!game,"native_game",game)));
    }
    static Map<String,List<JsonElement>> fixture() {
        Map<String,List<JsonElement>> f=new LinkedHashMap<>();
        JsonObject card=obj(Map.of("card_id",11,"fixture","SYNTHETIC"));
        JsonObject sa=obj(Map.of("ability_id",23,"source",card,"fixture","SYNTHETIC"));
        List<JsonElement> starts=new ArrayList<>(),completions=new ArrayList<>();
        for(int id=0;id<3;id++) {
            String kind=id==0?"dispatch":"dialog";
            JsonObject offer=obj(Map.of("kind",id==0?"input:InputPassPriority":"getAbilityToPlay","actor",7,"choices",List.of(id==0?card:sa),"min",1,"max",1,"turn",1,"phase","MAIN1","info",Map.of("fixture","SYNTHETIC")));
            JsonObject ticket=obj(Map.of("offer",offer,"selected",List.of(id==0?card:sa)));
            starts.add(obj(Map.of("start_id",id,"parent_start",id==1?0:-1,"kind",kind,"ticket",ticket,"parent_edge",edge(id==1?"SYNCHRONOUS_CALL":"ROOT",id==0?"INPUT_REQUEST_INVOKE_LATER":"BLOCKING_SEND_AND_WAIT",id==1?0:-1,id==2))));
            completions.add(obj(Map.of("start_id",id,"kind",kind,"ticket",ticket,"result",id==0?"true":"returned","producer",proof(id==0?"ROOT_PRIORITY_REMOVED":id==2?"RESUMED_ADDITIONAL_COST":"SYNCHRONOUS_DIALOG"))));
        }
        f.put("starts",starts);f.put("completions",new ArrayList<>(List.of(completions.get(1),completions.get(2),completions.get(0))));
        f.put("native",new ArrayList<>(List.of(obj(Map.of("fixture","SYNTHETIC","rng_delta",5)))));
        f.put("observations",new ArrayList<>(List.of(obj(Map.of("fixture","SYNTHETIC","view",Map.of("all_fields",List.of(1,2,3)))))));
        f.put("final",new ArrayList<>(List.of(obj(Map.of("fixture","SYNTHETIC","complete",true)))));return f;
    }
    static Map<String,List<JsonElement>> copy(Map<String,List<JsonElement>> f) {
        Map<String,List<JsonElement>> r=new LinkedHashMap<>();f.forEach((k,v)->{List<JsonElement> a=new ArrayList<>();v.forEach(x->a.add(x.deepCopy()));r.put(k,a);});return r;
    }
    static void feed(CausalCompletionVerifier v,Map<String,List<JsonElement>> f,boolean reverse) {
        List<JsonElement> st=f.get("starts"), c=f.get("completions");
        if(st.size()==3 && c.size()==3) {
            v.accept("starts",st.get(0));v.accept("starts",st.get(1));
            v.accept("completions",c.get(0));v.accept("starts",st.get(2));
            for(int i:reverse?new int[]{2,1}:new int[]{1,2})v.accept("completions",c.get(i));
        } else {
            for(JsonElement x:st)v.accept("starts",x);
            for(JsonElement x:c)v.accept("completions",x);
        }
        for(String s:List.of("native","observations","final"))for(JsonElement x:f.get(s))v.accept(s,x);
        v.finish();
    }
    static void reject(String label,Runnable run) {
        boolean rejected=false;try{run.run();}catch(IllegalArgumentException|IllegalStateException e){rejected=true;}
        need(rejected,"SYNTHETIC_NEGATIVE_ACCEPTED: "+label);tests++;
    }
    static Map<String,List<JsonElement>> two(String method,boolean deferred) {
        Map<String,List<JsonElement>> f=fixture();
        List<JsonElement> st=new ArrayList<>(),co=new ArrayList<>();
        for(int id=0;id<2;id++) {
            String kind=id==0||deferred?"dispatch":"dialog";
            String offerKind=id==0||deferred?"input:InputAttack":method;
            JsonObject ticket=obj(Map.of("offer",Map.of("kind",offerKind,"actor",7,"choices",List.of("SYNTHETIC_choice"),"min",1,"max",1,"turn",1,"phase","COMBAT","info",Map.of("fixture","SYNTHETIC")),"selected",List.of("SYNTHETIC_choice")));
            JsonObject e=edge(id==0?"ROOT":deferred?"DEFERRED_INPUT_REQUEST":"SYNCHRONOUS_CALL",id==0||deferred?"INPUT_REQUEST_INVOKE_LATER":"BLOCKING_SEND_AND_WAIT",id==0?-1:0,false);
            st.add(obj(Map.of("start_id",id,"parent_start",id==0?-1:0,"kind",kind,"ticket",ticket,"parent_edge",e)));
            JsonObject proof=proof("INELIGIBLE");
            if(id==1&&!deferred){proof.addProperty("role","SYNCHRONOUS_DIALOG");proof.addProperty("origin_start",0);}
            co.add(obj(Map.of("start_id",id,"kind",kind,"ticket",ticket,"result","SYNTHETIC_return","producer",proof)));
        }
        f.put("starts",st);f.put("completions",deferred?co:new ArrayList<>(List.of(co.get(1),co.get(0))));return f;
    }
    static void tail(CausalCompletionVerifier v,Map<String,List<JsonElement>> f) {
        for(String key:List.of("native","observations","final"))for(JsonElement x:f.get(key))v.accept(key,x);v.finish();
    }
    static void deferred(CausalCompletionVerifier v,Map<String,List<JsonElement>> f) {
        v.accept("starts",f.get("starts").get(0));v.accept("completions",f.get("completions").get(0));
        v.accept("starts",f.get("starts").get(1));v.accept("completions",f.get("completions").get(1));tail(v,f);
    }
    static void typedControls() {
        Map<String,List<JsonElement>> d=two("unused",true);
        try{deferred(new CausalCompletionVerifier(d),copy(d));}
        catch(RuntimeException ex){throw new AssertionError("SYNTHETIC_DEFERRED_PUBLICATION_MUST_START_AFTER_RETURN",ex);}tests++;
        for(String method:List.of("confirm","showConfirmDialog","getChoices","order")) {
            Map<String,List<JsonElement>> g=two(method,false);CausalCompletionVerifier v=new CausalCompletionVerifier(g);
            for(JsonElement st:g.get("starts"))v.accept("starts",st);for(JsonElement co:g.get("completions"))v.accept("completions",co);tail(v,g);tests++;
            CausalCompletionVerifier bad=new CausalCompletionVerifier(g);bad.accept("starts",g.get("starts").get(0));
            reject("generic sync parent returns before child "+method,()->bad.accept("completions",g.get("completions").get(1)));
        }
        for(String key:List.of("unknown_kind","wrong_form","wrong_parent","missing_edge","context_absent","invocation_lane","root_context")) {
            Map<String,List<JsonElement>> bad=copy(d);JsonObject child=bad.get("starts").get(1).getAsJsonObject();JsonObject edge=child.getAsJsonObject("parent_edge");
            if(key.equals("unknown_kind"))edge.addProperty("kind","UNKNOWN");
            if(key.equals("wrong_form"))edge.addProperty("producer_form","BLOCKING_SEND_AND_WAIT");
            if(key.equals("wrong_parent"))edge.addProperty("parent_start",999);
            if(key.equals("missing_edge"))child.remove("parent_edge");
            if(key.equals("context_absent"))edge.addProperty("publication_parent_context",false);
            if(key.equals("invocation_lane"))edge.add("invocation_lane",J.toJsonTree(Map.of("edt",false,"native_game",true)));
            if(key.equals("root_context"))bad.get("starts").get(0).getAsJsonObject().getAsJsonObject("parent_edge").addProperty("publication_parent_context",true);
            reject("invalid typed reference "+key,()->deferred(new CausalCompletionVerifier(bad),copy(bad)));
        }
        CausalCompletionVerifier early=new CausalCompletionVerifier(d);early.accept("starts",d.get("starts").get(0));
        reject("deferred child before EDT parent return",()->early.accept("starts",d.get("starts").get(1)));
        Map<String,List<JsonElement>> mutation=copy(d);mutation.get("starts").get(1).getAsJsonObject().getAsJsonObject("parent_edge").addProperty("kind","ROOT");
        reject("actual edge mutation",()->deferred(new CausalCompletionVerifier(d),mutation));
        JsonObject live=obj(Map.of("fixture","SYNTHETIC","source",11,"successful_pop",true));
        RetainedProvenance frozen=new RetainedProvenance(live);live.addProperty("source",999);
        need(frozen.copy().get("source").getAsInt()==11,"historical removal must not reread live mutable host");
        JsonObject alias=frozen.copy();alias.addProperty("source",888);
        need(frozen.copy().get("source").getAsInt()==11,"retained proof must not alias attached output");tests+=2;
    }
    static void referenceControls() {
        List<String> failures=new ArrayList<>();Object a=new Object(),b=new Object(),other=new Object(),sa=new Object();
        IdentityHashMap<Object,Object> cache=new IdentityHashMap<>();cache.put(a,sa);cache.put(other,new Object());
        Map<Object,Object> partial=IdentityOfferSnapshot.capture(List.of(a,b),cache,Object.class,Object.class,(k,v)->true);
        if(!partial.isEmpty()||partial.get(a)!=null)failures.add("partial snapshot retained earlier entry");tests++;
        cache.clear();cache.put(a,sa);cache.put(b,other);
        need(IdentityOfferSnapshot.capture(List.of(a,b),cache,Object.class,Object.class,(k,v)->true).get(a)==sa,"full actual identity mapping");tests++;
        if(!IdentityOfferSnapshot.capture(List.of(a,b),cache,Object.class,Object.class,(k,v)->k!=b).isEmpty())failures.add("later predicate failure retained partial map");tests++;
        need(IdentityOfferSnapshot.capture(List.of(a,a),cache,Object.class,Object.class,(k,v)->true).isEmpty(),"duplicate actual offered view rejected");tests++;
        ConfirmedReference<Object> first=new ConfirmedReference<>(sa),second=new ConfirmedReference<>(sa);
        need(ConfirmedReference.uniqueAvailable(List.of(first)).orElseThrow()==first,"one candidate observed");
        need(!first.confirm(other),"alternate selection not confirmation");
        if(!first.available()||ConfirmedReference.uniqueAvailable(List.of(first,second)).isPresent())failures.add("unconfirmed publication manufactured uniqueness");tests++;
        ConfirmedReference<Object> exact=new ConfirmedReference<>(sa);
        need(ConfirmedReference.uniqueAvailable(List.of(exact)).orElseThrow()==exact,"exact candidate observed");
        need(exact.confirm(sa)&&!exact.available(),"exact actual reference confirms consumption");tests++;
        if(exact.confirm(sa))failures.add("duplicate claim confirmation accepted");tests++;
        need(ConfirmedReference.uniqueAvailable(List.of(exact)).isEmpty(),"confirmed origin excluded");tests++;
        need(failures.isEmpty(),"SYNTHETIC_COMPLETE_SNAPSHOT_AND_CONFIRMED_CLAIM_REQUIRED: "+failures);
    }
    public static void main(String[] args) {
        try {
            Map<String,List<JsonElement>> f=fixture();feed(new CausalCompletionVerifier(f),copy(f),false);tests++;
            CausalCompletionVerifier allowed=new CausalCompletionVerifier(f);
            try{feed(allowed,copy(f),true);}catch(RuntimeException e){throw new AssertionError("SYNTHETIC_REVIEWED_PAIR_MUST_BE_ACCEPTED",e);}tests++;
            need(Boolean.FALSE.equals(allowed.diagnostic().get("strict_global_completion_order")),"raw global difference must be reported");
            for(String field:List.of("result","kind","ticket","start_id","producer")) {
                Map<String,List<JsonElement>> bad=copy(f);JsonObject r=bad.get("completions").get(2).getAsJsonObject();
                if(field.equals("start_id"))r.addProperty(field,999);else if(field.equals("producer"))r.remove(field);else r.addProperty(field,"SYNTHETIC_MUTATION");
                reject(field,()->feed(new CausalCompletionVerifier(f),bad,true));
            }
            for(String field:List.of("source","actor","origin_start","input_generation","removal_after_generation","same_sa_reference","same_source_reference","successful_pop","lane","producer_chain")) {
                Map<String,List<JsonElement>> bad=copy(f);JsonObject p=bad.get("completions").get(1).getAsJsonObject().getAsJsonObject("producer");
                if(field.equals("lane"))p.add(field,J.toJsonTree(Map.of("edt",true,"native_game",false)));
                else if(field.equals("producer_chain"))p.add(field,J.toJsonTree(chain("forge.gamemodes.match.input.InputPayMana#onCardSelected")));
                else if(field.startsWith("same")||field.equals("successful_pop"))p.addProperty(field,false);else p.addProperty(field,999);
                reject("proof mutation "+field,()->feed(new CausalCompletionVerifier(f),bad,true));
            }
            for(String stream:List.of("starts","native","observations","final")) {
                Map<String,List<JsonElement>> bad=copy(f);bad.get(stream).set(0,obj(Map.of("fixture","SYNTHETIC_MUTATION")));
                reject(stream+" mutation",()->feed(new CausalCompletionVerifier(f),bad,true));
            }
            Map<String,List<JsonElement>> wrongParent=copy(f);wrongParent.get("starts").get(1).getAsJsonObject().addProperty("parent_start",-1);
            reject("wrong parent",()->feed(new CausalCompletionVerifier(f),wrongParent,true));
            Map<String,List<JsonElement>> duplicate=copy(f);duplicate.get("completions").add(duplicate.get("completions").get(0));
            reject("duplicate",()->feed(new CausalCompletionVerifier(f),duplicate,false));
            Map<String,List<JsonElement>> missing=copy(f);missing.get("completions").remove(1);
            reject("missing completion",()->feed(new CausalCompletionVerifier(f),missing,false));
            Map<String,List<JsonElement>> noFinal=copy(f);noFinal.get("final").clear();
            reject("missing final",()->feed(new CausalCompletionVerifier(f),noFinal,true));
            Map<String,List<JsonElement>> future=fixture();
            for(int n=3;n<52;n++) {
                JsonObject st=future.get("starts").get(0).getAsJsonObject().deepCopy();st.addProperty("start_id",n);st.addProperty("parent_start",-1);future.get("starts").add(st);
                JsonObject co=future.get("completions").get(2).getAsJsonObject().deepCopy();co.addProperty("start_id",n);co.add("producer",proof("INELIGIBLE"));future.get("completions").add(co);
            }
            reject("missing49 and final",()->feed(new CausalCompletionVerifier(future),copy(f),true));
            for(String wrong:List.of("unknown_role","payment_callsite","wrong_source","wrong_lane")) {
                Map<String,List<JsonElement>> ref=fixture();JsonObject pr=ref.get("completions").get(1).getAsJsonObject().getAsJsonObject("producer");
                if(wrong.equals("unknown_role"))pr.addProperty("role","INELIGIBLE");
                if(wrong.equals("payment_callsite"))pr.add("producer_chain",J.toJsonTree(chain("forge.gamemodes.match.input.InputPayMana#onCardSelected")));
                if(wrong.equals("wrong_source"))pr.addProperty("source",999);
                if(wrong.equals("wrong_lane"))pr.add("lane",J.toJsonTree(Map.of("edt",true,"native_game",false)));
                reject("unreviewed inversion "+wrong,()->feed(new CausalCompletionVerifier(ref),copy(ref),true));
            }
            CausalCompletionVerifier beforeStart=new CausalCompletionVerifier(f);
            reject("return before start",()->beforeStart.accept("completions",f.get("completions").get(0)));
            CausalCompletionVerifier child=new CausalCompletionVerifier(f);for(JsonElement x:f.get("starts"))child.accept("starts",x);
            reject("synchronous child before parent",()->child.accept("completions",f.get("completions").get(2)));
            typedControls();
            referenceControls();
            System.out.println("PASS SYNTHETIC protocol tests="+tests+"; no Game/Card initialization");
        }catch(Throwable e){e.printStackTrace();System.exit(1);}
    }
}
