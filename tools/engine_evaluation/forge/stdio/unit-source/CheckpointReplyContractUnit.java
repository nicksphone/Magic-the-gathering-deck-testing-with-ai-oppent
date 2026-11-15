// SPDX-License-Identifier: GPL-3.0-or-later
// LABELLED SYNTHETIC transport controls; Forge Team/Card-Forge credits retained.
// No Game/Card initialization, filesystem snapshot, or gameplay outcome.
package forge.evaluation;

public final class CheckpointReplyContractUnit {
    public static void main(String[] args)throws Exception {
        var method=NativeHumanWorker.class.getDeclaredMethod("rejectionReason",String.class,IllegalArgumentException.class);
        method.setAccessible(true);
        Object[][] cases={
            {"SYNTHETIC_CHECKPOINT", "checkpoint_busy", "checkpoint_busy"},
            {null, "checkpoint_busy", "invalid_or_stale_response"},
            {"SYNTHETIC_CHECKPOINT", "checkpoint_not_current", "invalid_or_stale_response"},
            {null, "invalid_response", "invalid_or_stale_response"}
        };
        for(Object[] row:cases) {
            Object reason=method.invoke(null,row[0],new IllegalArgumentException((String)row[1]));
            if(!row[2].equals(reason))throw new AssertionError("Wrong checkpoint/legacy rejection reason");
        }
        System.out.println("4 labelled checkpoint/legacy rejection protocol checks passed");
    }
}
