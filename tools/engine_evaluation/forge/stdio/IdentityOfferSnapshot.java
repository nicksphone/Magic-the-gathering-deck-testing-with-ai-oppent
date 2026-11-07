// SPDX-License-Identifier: GPL-3.0-or-later
// Publish identity mappings only after the complete actual offered snapshot validates.
package forge.evaluation;
import java.util.*;
import java.util.function.BiPredicate;
public final class IdentityOfferSnapshot {
 public static<K,V> Map<K,V> capture(List<?> views,Map<?,?> cache,Class<K> kc,Class<V> vc,BiPredicate<K,V> valid) {
  if(cache==null||cache.size()!=views.size())return Map.of();
  IdentityHashMap<K,V> pending=new IdentityHashMap<>();
  for(Object offered:views) {
   if(!kc.isInstance(offered))return Map.of();K key=kc.cast(offered);V found=null;
   for(var item:cache.entrySet())if(item.getKey()==key&&vc.isInstance(item.getValue())) {
    if(found!=null)return Map.of();found=vc.cast(item.getValue());
   }
   if(found==null||!valid.test(key,found))return Map.of();pending.put(key,found);
  }
  if(pending.size()!=views.size())return Map.of();
  return Collections.unmodifiableMap(pending);
 }
}
