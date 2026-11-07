// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled composite launcher; original DG unit and GPL/Forge attribution retained.
package forge.evaluation;

import com.google.gson.*;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

public final class CombinedControlledUnit {
    static final Gson JSON=new Gson();

    static String sha(byte[] value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
    }

    static void coupled(Path root, Path out, String stage) throws Exception {
        JsonObject expected=JsonParser.parseString(Files.readString(root.resolve("evidence/PAYLOAD-PINS.json"))).getAsJsonObject();
        PartialManaReadyUnit.require(expected.size()==28,"exact approved coupled28 payload");
        Map<String,Object> proof=new TreeMap<>();
        for(var entry:expected.entrySet()) {
            String relative=entry.getKey(); int split=relative.indexOf('/');
            Path directory=root.resolve(relative.substring(0,split)).toAbsolutePath().normalize();
            String resource=relative.substring(split+1);
            String name=resource.substring(0,resource.length()-6).replace('/','.');
            // Resolve actual classes without initializing unused producer/helper branches.
            Class<?> type=Class.forName(name,false,CombinedControlledUnit.class.getClassLoader());
            Path origin=Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toAbsolutePath().normalize();
            String loaded;
            try(InputStream in=type.getResourceAsStream("/"+resource)) {
                PartialManaReadyUnit.require(in!=null,"actual class resource present: "+name);
                loaded=sha(in.readAllBytes());
            }
            String file=sha(Files.readAllBytes(root.resolve(relative)));
            String pin=entry.getValue().getAsString();
            PartialManaReadyUnit.require(origin.equals(directory) && loaded.equals(pin) && file.equals(pin),
                    "actual coupled origin/pin mismatch: "+name);
            proof.put(name,Map.of("origin",origin.toString(),"resource_sha256",loaded,"file_sha256",file,"expected_sha256",pin));
        }
        Files.writeString(out.resolve("COUPLED-"+stage+".json"),JSON.toJson(proof));
    }

    public static void main(String[] args) {
        long began=System.nanoTime();
        Path root=Path.of(args[0]), out=Path.of(args[1]);
        PartialManaReadyUnit unit=null; int exit=1; boolean nativePassed=false,endPassed=false;
        try {
            coupled(root,out,"PRE");
            unit=new PartialManaReadyUnit(); unit.output=out;
            unit.run(root); // Exact original final DG source, scenes and all assertions.
            synchronized(unit.worker) {
                boolean failed=PartialManaReadyUnit.field("failed").getBoolean(unit.worker);
                Map<String,Object> worker=Map.of("failed",failed,
                        "starts",PartialManaReadyUnit.field("starts").getInt(unit.worker),
                        "decisions",PartialManaReadyUnit.field("decisions").getInt(unit.worker));
                Files.writeString(out.resolve("R8-WORKER-END.json"),JSON.toJson(worker));
                PartialManaReadyUnit.require(!failed,"actual R8 worker/causal verifier must not fail");
            }
            nativePassed=true;
        } catch(Throwable error) { error.printStackTrace(System.err); }
        try { coupled(root,out,"END"); endPassed=true; }
        catch(Throwable error) { error.printStackTrace(System.err); }
        if(nativePassed && endPassed) {
            exit=0;
            try {
                Files.writeString(out.resolve("UNIT-PASS.json"),JSON.toJson(Map.of(
                        "scope","COMBINED finalR8+DG controlled partial+held-stale; NOT natural/replay/fullresume",
                        "stop_callbacks",unit.stopCallbacks,"transient_offers",unit.transientOffers,
                        "nested",unit.nested,"committed",unit.committed,"coupled_classes_verified",28)));
            } catch(Throwable error) { error.printStackTrace(System.err); exit=1; }
        }
        try {
            Files.writeString(out.resolve("JVM-EXIT.json"),JSON.toJson(Map.of("exit",exit,
                    "wall_seconds",(System.nanoTime()-began)/1e9,
                    "cpu_millis",ProcessHandle.current().info().totalCpuDuration().orElse(java.time.Duration.ZERO).toMillis(),
                    "label","controlled composite only; genuine harness concession; NOT natural/replay/fullresume")));
        } catch(Throwable error) { error.printStackTrace(System.err); exit=1; }
        System.exit(exit);
    }
}
