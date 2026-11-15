// SPDX-License-Identifier: GPL-3.0-or-later
// Historical observational facts: never reread a mutable native host on attachment.
package forge.evaluation;
import com.google.gson.JsonObject;
public final class RetainedProvenance {
    private final JsonObject captured;
    public RetainedProvenance(JsonObject facts) { captured=facts.deepCopy(); }
    public JsonObject copy() { return captured.deepCopy(); }
}
