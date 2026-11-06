// SPDX-License-Identifier: GPL-3.0-or-later
// LABELLED SYNTHETIC causal-prefix controls; Forge Team/Card-Forge credits retained.
// No native Game/Card initialization or manufactured game-final certificate.
package forge.evaluation;

import com.google.gson.*;
import java.lang.reflect.*;
import java.util.*;

public final class CheckpointPrefixUnit {
    private static Method verify,create,finish;
    private static int checks;
    private static Map<String,List<JsonElement>> prefix() {
        var p=CausalProtocolUnit.copy(CausalProtocolUnit.fixture());
        p.remove("observations");p.put("paid-pending",new ArrayList<>());p.get("final").clear();return p;
    }
    @SuppressWarnings("unchecked")
    private static Map<String,Object> verify(Map<String,List<JsonElement>> ref,Map<String,List<JsonElement>> actual) {
        try { return (Map<String,Object>)verify.invoke(null,ref,actual); }
        catch(ReflectiveOperationException e) { throw new IllegalStateException(e); }
    }
    private static void reject(Runnable action) {
        try { action.run();throw new AssertionError("SYNTHETIC invalid prefix accepted"); }
        catch(RuntimeException expected) { checks++; }
    }
    private static void need(boolean ok,String reason) { if(!ok)throw new AssertionError(reason);checks++; }
    private static Map<String,List<JsonElement>> swapped(Map<String,List<JsonElement>> input) {
        var p=CausalProtocolUnit.copy(input);Collections.swap(p.get("completions"),1,2);return p;
    }
    public static void main(String[] args)throws Exception {
        verify=CausalCompletionVerifier.class.getDeclaredMethod("verifyPrefix",Map.class,Map.class);
        create=CausalCompletionVerifier.class.getDeclaredMethod("prefix",Map.class);
        finish=CausalCompletionVerifier.class.getDeclaredMethod("finishPrefix");
        var ref=prefix();var same=verify(ref,CausalProtocolUnit.copy(ref));
        need(same.get("contract").equals("CAUSAL_CHECKPOINT_PREFIX"),"Explicit prefix contract required");
        need(Boolean.FALSE.equals(same.get("game_complete"))&&Integer.valueOf(0).equals(same.get("final_rows")),"Prefix is not a game result");
        need(Boolean.TRUE.equals(same.get("strict_global_completion_order")),"Equal order must remain reported");
        var reordered=verify(ref,swapped(ref));
        need(Boolean.FALSE.equals(reordered.get("strict_global_completion_order")),"Real order difference must remain reported");
        need(((List<?>)reordered.get("displaced_pairs")).size()==1,"Reviewed inversion requires an explicit pair proof");
        verify(swapped(ref),ref);checks++;
        for(String field:List.of("result","kind","ticket","start_id","producer")) {
            var bad=swapped(ref);JsonObject row=bad.get("completions").get(1).getAsJsonObject();
            if(field.equals("start_id"))row.addProperty(field,999);else if(field.equals("producer"))row.remove(field);else row.addProperty(field,"SYNTHETIC_MUTATION");
            reject(()->verify(ref,bad));
        }
        for(String field:List.of("unknown_role","payment_callsite","wrong_source","wrong_lane","missing_identity_flag")) {
            var bad=CausalProtocolUnit.copy(ref);JsonObject p=bad.get("completions").get(1).getAsJsonObject().getAsJsonObject("producer");
            switch(field) {
                case "unknown_role" -> p.addProperty("role","INELIGIBLE");
                case "payment_callsite" -> p.add("producer_chain",CausalProtocolUnit.J.toJsonTree(CausalProtocolUnit.chain("forge.gamemodes.match.input.InputPayMana#onCardSelected")));
                case "wrong_source" -> p.addProperty("source",999);
                case "wrong_lane" -> p.add("lane",CausalProtocolUnit.J.toJsonTree(Map.of("edt",true,"native_game",false)));
                case "missing_identity_flag" -> p.addProperty("same_sa_reference",false);
            }
            reject(()->verify(bad,swapped(bad)));
        }
        for(String stream:List.of("starts","native","paid-pending")) {
            var bad=CausalProtocolUnit.copy(ref);bad.get(stream).add(CausalProtocolUnit.obj(Map.of("fixture","SYNTHETIC_EXTRA")));
            reject(()->verify(ref,bad));
        }
        var missing=CausalProtocolUnit.copy(ref);missing.get("completions").remove(0);reject(()->verify(ref,missing));
        var duplicate=CausalProtocolUnit.copy(ref);duplicate.get("completions").add(duplicate.get("completions").get(0));reject(()->verify(ref,duplicate));
        var unknown=CausalProtocolUnit.copy(ref);unknown.put("unknown",List.of());reject(()->verify(ref,unknown));
        var finalRow=CausalProtocolUnit.copy(ref);finalRow.get("final").add(CausalProtocolUnit.obj(Map.of("fixture","SYNTHETIC_INVALID_FINAL")));
        reject(()->verify(finalRow,finalRow));reject(()->verify(ref,finalRow));
        reject(()->new CausalCompletionVerifier(ref));
        var empty=new LinkedHashMap<String,List<JsonElement>>();
        for(String key:List.of("starts","completions","native","paid-pending","final"))empty.put(key,new ArrayList<>());
        var instance=(CausalCompletionVerifier)create.invoke(null,empty);finish.invoke(instance);checks++;
        reject(instance::finish);
        var invalidFinal=CausalProtocolUnit.obj(Map.of("fixture","SYNTHETIC_INVALID_FINAL"));
        empty.get("final").add(invalidFinal);
        reject(()->{instance.accept("final",invalidFinal);instance.finish();});
        var fullRef=CausalProtocolUnit.fixture();var full=new CausalCompletionVerifier(fullRef);
        for(String key:List.of("starts","completions","native","observations"))for(JsonElement row:fullRef.get(key))full.accept(key,row);
        fullRef.get("final").clear();
        reject(()->{try{finish.invoke(full);}catch(ReflectiveOperationException e){throw new IllegalStateException(e);}});
        var deferred=CausalProtocolUnit.copy(CausalProtocolUnit.two("unused",true));deferred.remove("observations");deferred.put("paid-pending",new ArrayList<>());deferred.get("final").clear();
        verify(deferred,deferred);checks++;
        var badDeferred=CausalProtocolUnit.copy(deferred);Collections.reverse(badDeferred.get("completions"));reject(()->verify(deferred,badDeferred));
        System.out.println("CheckpointPrefixUnit passed="+checks+" (labelled protocol checks; no game outcome)");
    }
}
