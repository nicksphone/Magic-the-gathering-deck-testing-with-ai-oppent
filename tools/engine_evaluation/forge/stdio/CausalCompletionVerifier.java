// SPDX-License-Identifier: GPL-3.0-or-later
// Owned R7 protocol verifier. No Forge Game/Card initialization or state mutation.
package forge.evaluation;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.Gson;
import com.google.gson.JsonParser;
import java.util.*;

public final class CausalCompletionVerifier {
    private final Map<String,List<JsonElement>> expected;
    private final boolean prefixMode;
    private final Map<String,Integer> cursors=new HashMap<>(), positions=new HashMap<>();
    private final Map<Integer,JsonObject> referenceStarts=new LinkedHashMap<>(), referenceReturns=new LinkedHashMap<>();
    private final Map<Integer,Integer> returnPositions=new HashMap<>();
    private final Map<Integer,JsonObject> starts=new LinkedHashMap<>(), returns=new LinkedHashMap<>();
    private final List<JsonElement> arrival=new ArrayList<>();
    private final List<Map<String,Integer>> displaced=new ArrayList<>();

    public CausalCompletionVerifier(Map<String,List<JsonElement>> reference) {
        this(reference,1);
    }

    private CausalCompletionVerifier(Map<String,List<JsonElement>> reference,int finalRows) {
        expected=reference;
        prefixMode=finalRows==0;
        if(reference==null) return;
        need(reference.containsKey("starts")&&reference.containsKey("completions")&&reference.containsKey("final"),"reference streams absent");
        for(JsonElement e:reference.get("starts")) {
            JsonObject s=e.getAsJsonObject();int id=num(s,"start_id");
            need(id==referenceStarts.size()&&num(s,"parent_start")<id,"invalid reference start/parent");
            need(num(s,"parent_start")==-1||referenceStarts.containsKey(num(s,"parent_start")),"unknown reference parent");
            edgeKind(s);
            referenceStarts.put(id,s);
        }
        for(JsonElement e:reference.get("completions")) {
            JsonObject c=e.getAsJsonObject();int id=num(c,"start_id");
            need(referenceStarts.containsKey(id)&&!referenceReturns.containsKey(id),"reference return domain/duplicate");
            sameTicket(referenceStarts.get(id),c);basicProof(c);
            returnPositions.put(id,referenceReturns.size());referenceReturns.put(id,c);
        }
        need(referenceReturns.keySet().equals(referenceStarts.keySet()),"reference missing completion");
        for(JsonObject s:referenceStarts.values()) {
            int parent=num(s,"parent_start");
            String edge=edgeKind(s);
            if(edge.equals("SYNCHRONOUS_CALL"))need(returnPositions.get(num(s,"start_id"))<returnPositions.get(parent),"reference synchronous child after parent");
            if(edge.equals("DEFERRED_INPUT_REQUEST"))need(returnPositions.get(parent)<returnPositions.get(num(s,"start_id")),"reference deferred child before parent return");
        }
        need(reference.get("final").size()==finalRows,"reference final absent/extra");
    }

    static void need(boolean ok,String reason) { if(!ok)throw new IllegalStateException(reason); }
    static int num(JsonObject o,String key) { need(o.has(key)&&o.get(key).isJsonPrimitive(),"missing integer "+key);return o.get(key).getAsInt(); }
    static String text(JsonObject o,String key) { need(o.has(key)&&o.get(key).isJsonPrimitive(),"missing text "+key);return o.get(key).getAsString(); }
    static JsonObject object(JsonObject o,String key) { need(o.has(key)&&o.get(key).isJsonObject(),"missing object "+key);return o.getAsJsonObject(key); }
    static boolean yes(JsonObject o,String key) { return o.has(key)&&o.get(key).isJsonPrimitive()&&o.get(key).getAsBoolean(); }
    static boolean bool(JsonObject o,String key) {
        need(o.has(key)&&o.get(key).isJsonPrimitive()&&o.get(key).getAsJsonPrimitive().isBoolean(),"typed boolean absent "+key);
        return o.get(key).getAsBoolean();
    }
    static String edgeKind(JsonObject start) {
        JsonObject e=object(start,"parent_edge");String kind=text(e,"kind"),form=text(e,"producer_form");int parent=num(start,"parent_start");
        need(num(e,"parent_start")==parent,"typed edge parent differs");
        boolean context=bool(e,"publication_parent_context");
        need(Set.of("ROOT","SYNCHRONOUS_CALL","DEFERRED_INPUT_REQUEST").contains(kind),"unknown typed edge");
        need(kind.equals("ROOT")?parent==-1&&!context:parent>=0&&context,"edge root/context mismatch");
        JsonObject publication=object(e,"publisher_lane"),invocation=object(e,"invocation_lane");
        boolean pe=bool(publication,"edt"),pg=bool(publication,"native_game"),ie=bool(invocation,"edt"),ig=bool(invocation,"native_game");
        need(e.has("producer_chain")&&e.get("producer_chain").isJsonArray()&&e.getAsJsonArray("producer_chain").size()>0,"publication chain absent");
        if(form.equals("INPUT_REQUEST_INVOKE_LATER")) {
            need(text(start,"kind").equals("dispatch")&&!kind.equals("SYNCHRONOUS_CALL"),"input producer edge mismatch");
            need(pe&&!pg&&ie&&!ig,"deferred input requires actual EDT publisher/invocation");
        } else if(form.equals("BLOCKING_SEND_AND_WAIT")) {
            need(text(start,"kind").equals("dialog")&&!kind.equals("DEFERRED_INPUT_REQUEST"),"blocking producer edge mismatch");
            need(publication.equals(invocation),"dialog lane must be producer, not answer intake");
            if(kind.equals("SYNCHRONOUS_CALL"))need(pe&&!pg,"synchronous dispatch dialog requires actual EDT producer");
        } else need(false,"unknown producer form");
        return kind;
    }
    static void sameTicket(JsonObject s,JsonObject c) {
        need(s.get("kind").equals(c.get("kind"))&&s.get("ticket").equals(c.get("ticket")),"completion kind/ticket mismatch");
    }
    static void basicProof(JsonObject c) {
        JsonObject p=object(c,"producer");String role=text(p,"role");
        need(Set.of("INELIGIBLE","SYNCHRONOUS_DIALOG","ROOT_PRIORITY_REMOVED","RESUMED_ADDITIONAL_COST").contains(role),"unknown producer role");
        object(p,"lane");need(p.has("producer_chain")&&p.get("producer_chain").isJsonArray(),"producer chain absent");
    }
    public void accept(String stream,JsonElement row) {
        int index=cursors.getOrDefault(stream,0);
        if(expected!=null&&!stream.equals("completions")) {
            need(expected.containsKey(stream)&&index<expected.get(stream).size()&&row.equals(expected.get(stream).get(index)),"strict_replay_mismatch_"+stream+"_"+index);
        }
        if(stream.equals("starts")) {
            JsonObject s=row.getAsJsonObject();int id=num(s,"start_id"),parent=num(s,"parent_start");
            need(id==starts.size()&&!starts.containsKey(id)&&parent<id,"start domain/order/parent");
            String edge=edgeKind(s);
            need(parent==-1||starts.containsKey(parent),"unknown publication parent");
            if(edge.equals("SYNCHRONOUS_CALL"))need(!returns.containsKey(parent),"synchronous child outside active parent");
            if(edge.equals("DEFERRED_INPUT_REQUEST"))need(returns.containsKey(parent),"deferred child before EDT parent return");
            starts.put(id,s.deepCopy());
        } else if(stream.equals("completions")) {
            JsonObject c=row.getAsJsonObject();int id=num(c,"start_id");
            need(starts.containsKey(id)&&!returns.containsKey(id),"return before start/extra/duplicate");
            sameTicket(starts.get(id),c);basicProof(c);
            if(edgeKind(starts.get(id)).equals("SYNCHRONOUS_CALL"))
                need(text(object(c,"producer"),"role").equals("SYNCHRONOUS_DIALOG")&&num(object(c,"producer"),"origin_start")==num(starts.get(id),"parent_start"),"synchronous edge lacks actual blocking producer");
            for(JsonObject child:starts.values()) if(num(child,"parent_start")==id&&edgeKind(child).equals("SYNCHRONOUS_CALL"))
                need(returns.containsKey(num(child,"start_id")),"synchronous child must return before parent");
            if(expected!=null) {
                need(referenceReturns.containsKey(id)&&c.equals(referenceReturns.get(id)),"whole completion row mismatch by start_id");
                for(JsonObject child:referenceStarts.values()) if(num(child,"parent_start")==id&&edgeKind(child).equals("SYNCHRONOUS_CALL"))
                    need(returns.containsKey(num(child,"start_id")),"reference child absent before parent return");
                // An unarrived reference predecessor is an actual displacement now.
                // Its eventual whole-row equality/domain is still mandatory at finish.
                for(var entry:referenceReturns.entrySet()) {
                    int skipped=entry.getKey();
                    if(returnPositions.get(skipped)<returnPositions.get(id)&&!returns.containsKey(skipped)) {
                        need(permitted(c,entry.getValue()),"unreviewed_completion_inversion_"+id+"_"+skipped);
                        displaced.add(Map.of("arrived_before",id,"reference_predecessor",skipped));
                    }
                }
            }
            returns.put(id,c.deepCopy());arrival.add(c.deepCopy());
        }
        cursors.put(stream,index+1);
    }

    static final String[] GAME={"forge.player.PlayerControllerHuman#getAbilityToPlay","forge.game.player.PlayerController#getAbilityToPlay","forge.game.player.PlaySpellAbility#chooseOptionalAdditionalCosts","forge.game.player.PlaySpellAbility#playSpellAbility","forge.player.PlayerControllerHuman#playChosenSpellAbility","forge.game.phase.PhaseHandler#mainLoopStep"};
    static final String[] POP={"forge.gamemodes.match.input.InputQueue#removeInput","forge.gamemodes.match.input.InputSyncronizedBase#stop","forge.gamemodes.match.input.InputPassPriority#onCardSelected","forge.gamemodes.match.input.InputBase#selectCard","forge.gamemodes.match.input.InputProxy#selectCard","forge.player.PlayerControllerHuman#selectCard"};
    static boolean chain(JsonObject p,String key,String[] required) {
        if(!p.has(key)||!p.get(key).isJsonArray())return false;
        List<String> names=new ArrayList<>();
        for(JsonElement e:p.getAsJsonArray(key)) {
            if(!e.isJsonObject())return false;
            JsonObject frame=e.getAsJsonObject();if(!frame.has("class")||!frame.has("method"))return false;
            names.add(frame.get("class").getAsString()+"#"+frame.get("method").getAsString());
        }
        if(key.equals("producer_chain")&&names.stream().anyMatch(s->s.startsWith("forge.gamemodes.match.input.InputPayMana#")||s.startsWith("forge.game.ability.effects.")))return false;
        for(int i=0;i+required.length<=names.size();i++)if(names.subList(i,i+required.length).equals(Arrays.asList(required)))return true;
        return false;
    }
    private boolean permitted(JsonObject a,JsonObject b) {
        JsonObject ap=object(a,"producer"),bp=object(b,"producer");
        JsonObject d,g,dp,gp;
        if(text(ap,"role").equals("ROOT_PRIORITY_REMOVED")&&text(bp,"role").equals("RESUMED_ADDITIONAL_COST")){d=a;g=b;dp=ap;gp=bp;}
        else if(text(bp,"role").equals("ROOT_PRIORITY_REMOVED")&&text(ap,"role").equals("RESUMED_ADDITIONAL_COST")){d=b;g=a;dp=bp;gp=ap;}
        else return false;
        int did=num(d,"start_id"),gid=num(g,"start_id");
        JsonObject ds=referenceStarts.get(did),gs=referenceStarts.get(gid);
        if(ds==null||gs==null||num(ds,"parent_start")!=-1||num(gs,"parent_start")!=-1)return false;
        if(!text(ds,"kind").equals("dispatch")||!text(gs,"kind").equals("dialog"))return false;
        JsonObject dt=object(ds,"ticket"),gt=object(gs,"ticket"),dof=object(dt,"offer"),gof=object(gt,"offer");
        if(!text(dof,"kind").equals("input:InputPassPriority")||!text(gof,"kind").equals("getAbilityToPlay"))return false;
        if(!yes(object(dp,"lane"),"edt")||yes(object(dp,"lane"),"native_game")||yes(object(gp,"lane"),"edt")||!yes(object(gp,"lane"),"native_game"))return false;
        if(!chain(dp,"removal_chain",POP)||!chain(gp,"removal_chain",POP)||!chain(gp,"producer_chain",GAME))return false;
        for(JsonObject p:List.of(dp,gp)) {
            for(String flag:List.of("successful_pop","same_input_reference","same_sa_reference","same_source_reference"))if(!yes(p,flag))return false;
            if(yes(p,"latch_release_observed")||!text(p,"input_class").equals("InputPassPriority"))return false;
            if(num(p,"origin_start")!=did||num(p,"removal_after_generation")<=num(p,"input_generation"))return false;
        }
        for(String key:List.of("actor","source","ability","origin_start","input_generation","removal_after_generation"))if(num(dp,key)!=num(gp,key))return false;
        int actor=num(dp,"actor"),source=num(dp,"source"),ability=num(dp,"ability");
        if(num(dof,"actor")!=actor||num(gof,"actor")!=actor)return false;
        if(dt.getAsJsonArray("selected").size()!=1||gt.getAsJsonArray("selected").size()!=1)return false;
        JsonObject dc=dt.getAsJsonArray("selected").get(0).getAsJsonObject(),gc=gt.getAsJsonArray("selected").get(0).getAsJsonObject();
        if(num(dc,"card_id")!=source||num(gc,"ability_id")!=ability||num(object(gc,"source"),"card_id")!=source)return false;
        int matchedChildren=0;
        for(JsonObject child:referenceStarts.values())if(num(child,"parent_start")==did) {
            JsonObject ct=object(child,"ticket");
            if(text(object(ct,"offer"),"kind").equals("getAbilityToPlay")&&ct.getAsJsonArray("selected").size()==1) {
                JsonObject selected=ct.getAsJsonArray("selected").get(0).getAsJsonObject();
                if(num(selected,"ability_id")==ability&&num(object(selected,"source"),"card_id")==source)matchedChildren++;
            }
        }
        return matchedChildren==1;
    }
    public void finish() {
        need(!prefixMode,"a checkpoint prefix is not a full game");
        need(returns.keySet().equals(starts.keySet()),"missing completion domain");
        need(cursors.getOrDefault("final",0)==1,"missing/extra final");
        if(expected!=null) {
            need(starts.keySet().equals(referenceStarts.keySet()),"missing/extra start domain");
            need(returns.keySet().equals(referenceReturns.keySet()),"missing/extra reference receipt domain");
            for(String stream:expected.keySet())need(cursors.getOrDefault(stream,0)==expected.get(stream).size(),"unconsumed_journal_"+stream);
        }
    }
    public Map<String,Object> diagnostic() {
        return Map.of("contract","CAUSAL_COMPLETION_REPLAY","reference_comparison",expected!=null,
                "strict_global_completion_order",expected==null||arrival.equals(expected.get("completions")),
                "displaced_pairs",List.copyOf(displaced),"completed_ids_in_arrival_order",new ArrayList<>(returns.keySet()));
    }

    private static final Set<String> PREFIX_STREAMS=Set.of("starts","completions","native","paid-pending","final");

    public static CausalCompletionVerifier prefix(Map<String,List<JsonElement>> reference) {
        need(reference!=null&&reference.keySet().equals(PREFIX_STREAMS),"checkpoint prefix streams differ");
        return new CausalCompletionVerifier(reference,0);
    }

    public void finishPrefix() {
        need(prefixMode&&expected!=null&&expected.get("final").isEmpty(),"not an unfinished reference prefix");
        need(returns.keySet().equals(starts.keySet()),"missing prefix completion domain");
        need(starts.keySet().equals(referenceStarts.keySet())&&returns.keySet().equals(referenceReturns.keySet()),"prefix invocation domain differs");
        for(String stream:expected.keySet())need(cursors.getOrDefault(stream,0)==expected.get(stream).size(),"unconsumed_prefix_"+stream);
    }

    public static Map<String,Object> verifyPrefix(Map<String,List<JsonElement>> reference,Map<String,List<JsonElement>> actual) {
        CausalCompletionVerifier verifier=prefix(reference);
        need(actual!=null&&actual.keySet().equals(PREFIX_STREAMS),"actual prefix streams differ");
        need(actual.get("final").isEmpty(),"checkpoint prefix has a final row");
        int nextReturn=0;
        List<JsonElement> completed=actual.get("completions");
        // Reconstruct only declared parent dependencies. Completion arrivals retain
        // their actual order; accept() still proves each inversion and whole row.
        for(JsonElement row:actual.get("starts")) {
            JsonObject start=row.getAsJsonObject();
            if(edgeKind(start).equals("DEFERRED_INPUT_REQUEST")) {
                int parent=num(start,"parent_start");
                while(!verifier.returns.containsKey(parent)) {
                    need(nextReturn<completed.size(),"deferred prefix parent has not returned");
                    verifier.accept("completions",completed.get(nextReturn++));
                }
            }
            verifier.accept("starts",row);
        }
        while(nextReturn<completed.size())verifier.accept("completions",completed.get(nextReturn++));
        for(String stream:List.of("native","paid-pending","final"))
            for(JsonElement row:actual.get(stream))verifier.accept(stream,row);
        verifier.finishPrefix();
        Map<String,Object> result=new LinkedHashMap<>(verifier.diagnostic());
        result.put("contract","CAUSAL_CHECKPOINT_PREFIX");
        result.put("final_rows",0);
        result.put("game_complete",false);
        return result;
    }

    private static Map<String,List<JsonElement>> prefixStreams(JsonObject value) {
        need(value.keySet().equals(PREFIX_STREAMS),"checkpoint prefix stream keys differ");
        Map<String,List<JsonElement>> streams=new LinkedHashMap<>();
        for(String key:PREFIX_STREAMS) {
            need(value.get(key).isJsonArray(),"checkpoint prefix stream must be an array");
            List<JsonElement> rows=new ArrayList<>();value.getAsJsonArray(key).forEach(rows::add);streams.put(key,rows);
        }
        return streams;
    }

    // Local trusted-host verifier, not a game launcher or browser command API.
    public static void main(String[] args)throws Exception {
        need(args.length==1&&args[0].equals("--checkpoint-prefix"),"expected checkpoint-prefix mode");
        int limit=128*1024*1024;
        byte[] raw=System.in.readNBytes(limit+1);
        need(raw.length<=limit,"checkpoint prefix input too large");
        JsonObject input=JsonParser.parseString(new String(raw,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        need(input.keySet().equals(Set.of("reference","actual")),"checkpoint prefix request keys differ");
        Map<String,Object> proof=new LinkedHashMap<>(verifyPrefix(prefixStreams(input.getAsJsonObject("reference")),prefixStreams(input.getAsJsonObject("actual"))));
        proof.put("input_sha256",java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(raw)));
        System.out.println(new Gson().toJson(proof));
    }
}
