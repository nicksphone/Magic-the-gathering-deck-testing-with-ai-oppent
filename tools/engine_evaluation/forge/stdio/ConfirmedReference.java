// SPDX-License-Identifier: GPL-3.0-or-later
// Observing a unique candidate is not confirmation of its actual returned reference.
package forge.evaluation;
import java.util.*;
public final class ConfirmedReference<T> {
 private final T expected;private boolean claimed;
 public ConfirmedReference(T expected){this.expected=Objects.requireNonNull(expected);}
 public synchronized boolean available(){return !claimed;}
 public synchronized boolean confirm(T actual){if(claimed||actual!=expected)return false;claimed=true;return true;}
 public static<T> Optional<ConfirmedReference<T>> uniqueAvailable(Collection<ConfirmedReference<T>> entries){
  ConfirmedReference<T> found=null;
  for(var entry:entries)if(entry.available()){if(found!=null)return Optional.empty();found=entry;}
  return Optional.ofNullable(found);
 }
}
