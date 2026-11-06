// SPDX-License-Identifier: GPL-3.0-or-later
// Original partial-payment protocol test; opening/selection checks adapted from
// vVVArcvz InputReadyUnit. Forge Team/Card-Forge base 61e9442, GPL3+ LICENSE retained.
// INTERNALPROTOCOL controlled native scene, NOT a natural paid episode/fullgame.
package forge.evaluation;

import com.google.common.eventbus.Subscribe;
import com.google.gson.*;
import forge.GuiDesktop;
import forge.ai.LobbyPlayerAi;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.*;
import forge.game.player.*;
import forge.game.zone.ZoneType;
import forge.gamemodes.match.HostedMatch;
import forge.gamemodes.net.*;
import forge.gamemodes.net.event.*;
import forge.gui.FThreads;
import forge.gui.GuiBase;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.player.LobbyPlayerHuman;
import forge.util.MyRandom;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

public final class PartialManaReadyUnit implements IRemote {
    static final Gson JSON = new Gson();
    final BlockingQueue<JsonObject> frames = new LinkedBlockingQueue<>();
    // Driver-only wake queue: actual frames or a completed Java future, never UI events.
    final BlockingQueue<Object> driverSignals = new LinkedBlockingQueue<>();
    final Thread driverThread = Thread.currentThread();
    final ThreadLocal<Boolean> insideStop = ThreadLocal.withInitial(() -> false);
    final CountDownLatch finished = new CountDownLatch(1);
    NativeHumanWorker worker;
    ProtocolGuiGame gui;
    volatile Player actor;
    volatile boolean clicked, committed;
    volatile int epoch, landEpoch, stopCallbacks, transientOffers, nested;
    Path output;
    volatile forge.gamemodes.match.input.InputPayMana paymentInput;
    volatile forge.game.spellability.SpellAbility paidAbility;
    volatile boolean watchPartial;
    final CompletableFuture<Void> partialRefreshCommitted = new CompletableFuture<>();
    int partialPromptCallbacks;
    final GateGuiDesktop desktop = new GateGuiDesktop();
    volatile boolean observingStaleDispatch;
    int staleGuiCallbacks;

    // INTERNALPROTOCOL executor seam: retain and later dispatch the actual native runnable.
    final class GateGuiDesktop extends GuiDesktop {
        volatile boolean holdNextManaRefresh;
        final CompletableFuture<Runnable> captured = new CompletableFuture<>();

        @Override public void invokeInEdtLater(Runnable proc) {
            if(holdNextManaRefresh && StackWalker.getInstance().walk(s -> s.anyMatch(f ->
                    f.getClassName().equals("forge.gamemodes.match.input.InputPayMana") &&
                    f.getMethodName().equals("onStateChanged")))) {
                holdNextManaRefresh=false;
                require(!FThreads.isGuiThread(),"hold real off-EDT native enqueue");
                trace("actual_native_refresh_held",Map.of("generation",paymentInput.getController().getInputQueue().getInputGeneration(),
                        "producer_thread",Thread.currentThread().getName(),"runnable_class",proc.getClass().getName()));
                require(captured.complete(proc),"capture native runnable exactly once");
                return;
            }
            super.invokeInEdtLater(proc);
        }

        CompletableFuture<Void> release(Runnable actual) {
            CompletableFuture<Void> returned=new CompletableFuture<>();
            super.invokeInEdtLater(() -> {
                observingStaleDispatch=true;
                try {
                    require(FThreads.isGuiThread(),"dispatch retained native runnable on actual EDT");
                    actual.run();
                    trace("actual_stale_native_runnable_returned",Map.of("gui_callbacks",staleGuiCallbacks));
                    returned.complete(null);
                } catch(Throwable error) { returned.completeExceptionally(error); }
                finally { observingStaleDispatch=false; }
            });
            return returned;
        }
    }

    static void require(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    static Field field(String name) throws Exception {
        Field f = NativeHumanWorker.class.getDeclaredField(name); f.setAccessible(true); return f;
    }

    synchronized void trace(String kind, Object value) {
        try { Files.writeString(output.resolve("unit-trace.jsonl"), JSON.toJson(Map.of("event",kind,"value",value))+"\n",
                StandardOpenOption.CREATE,StandardOpenOption.APPEND); }
        catch (IOException e) { throw new UncheckedIOException(e); }
    }

    @Subscribe public void nativeEvent(forge.game.event.GameEvent event) {
        String kind=event.getClass().getSimpleName();
        if (kind.equals("GameEventPlayerPriority")) { epoch++; trace("real_priority", epoch); }
        if (kind.equals("GameEventLandPlayed") && clicked) {
            committed=true; landEpoch=epoch; trace("real_land_event",counts());
        }
        if (kind.equals("GameEventGameFinished")) finished.countDown();
    }

    Map<String,Object> counts() {
        return actor==null ? Map.of() : Map.of("hand",actor.getCardsIn(ZoneType.Hand).size(),
                "battlefield",actor.getCardsIn(ZoneType.Battlefield).size(),"epoch",epoch);
    }

    @Override public void send(NetEvent event) {
        GuiGameEvent call=(GuiGameEvent)event;
        boolean stop=call.getMethod()==ProtocolMethod.setSelection && clicked && actor!=null &&
                actor.getCardsIn(ZoneType.Hand).size()==7 && actor.getCardsIn(ZoneType.Battlefield).isEmpty() &&
                StackWalker.getInstance().walk(s -> s.anyMatch(f -> f.getClassName().endsWith("InputSyncronizedBase") && f.getMethodName().equals("stop")));
        if (stop) { stopCallbacks++; trace("stop_before_native_commit",counts()); insideStop.set(true); }
        try {
            worker.send(event);
            if(observingStaleDispatch && StackWalker.getInstance().walk(s -> s.anyMatch(f ->
                    f.getClassName().equals("forge.gamemodes.match.input.InputPayMana") &&
                    f.getMethodName().equals("updateMessage")))) {
                staleGuiCallbacks++;
                trace("stale_native_refresh_gui_callback",call.getMethod().name());
            }
            if (watchPartial && call.getMethod()==ProtocolMethod.showPromptMessage &&
                    paidAbility.getManaCostBeingPaid()!=null &&
                    paidAbility.getManaCostBeingPaid().getConvertedManaCost()==1 &&
                    StackWalker.getInstance().walk(s -> s.anyMatch(f ->
                        f.getClassName().equals("forge.gamemodes.match.input.InputPayMana") &&
                        f.getMethodName().equals("updateMessage")))) {
                require(FThreads.isGuiThread(),"real partial refresh must execute on EDT");
                partialPromptCallbacks++;
                trace("actual_partial_prompt_callback",Map.of("remaining",1,"busy",paymentInput.isActivatingManaAbility()));
                // Test observation only: behind the entire real updateMessage and its receipt.
                // This barrier never publishes readiness or invokes a production refresh.
                FThreads.invokeInEdtLater(() -> partialRefreshCommitted.complete(null));
            }
            if (call.getMethod()==ProtocolMethod.openView) {
                try { actor=(Player)field("actor").get(worker); } catch (Exception e) { throw new RuntimeException(e); }
                actor.getGame().subscribeToEvents(this);
            }
        } finally { if (stop) insideStop.set(false); }
    }

    @Override public Object sendAndWait(IdentifiableNetEvent event) {
        if (((GuiGameEvent)event).getMethod()==ProtocolMethod.getAbilityToPlay && clicked) {
            nested++; trace("real_nested_ability",counts());
        }
        return worker.sendAndWait(event);
    }

    void wire(String line) {
        JsonObject frame=JsonParser.parseString(line).getAsJsonObject();
        try { Files.writeString(output.resolve("wire.jsonl"),line+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND); }
        catch (IOException e) { throw new UncheckedIOException(e); }
        if (frame.get("event").getAsString().equals("choice")) {
            if (insideStop.get()) { transientOffers++; trace("actionable_stop_offer",counts()); }
            frames.add(frame);
            driverSignals.add(frame);
        }
        if (frame.get("event").getAsString().equals("completion")) frames.add(frame);
    }

    static void loaded(Path output) throws Exception {
        Map<String,Object> pins=new TreeMap<>();
        for (Class<?> c:List.of(NativeHumanWorker.class, PartialManaReadyUnit.class, ActorBoundary.class,
                NativeNameMatchProbe.class, NativeObserverUnit.class, PublicNameController.class,
                forge.game.GameAction.class, forge.util.MyRandom.class, GateGuiDesktop.class,
                forge.gamemodes.match.input.InputPayMana.class,
                forge.gamemodes.match.input.InputBase.class, forge.gamemodes.match.input.InputQueue.class,
                forge.gamemodes.match.input.InputProxy.class)) {
            String resource="/"+c.getName().replace('.','/')+".class";
            try (InputStream in=c.getResourceAsStream(resource)) {
                pins.put(c.getName(),Map.of("location",c.getProtectionDomain().getCodeSource().getLocation().toString(),
                        "sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(in.readAllBytes()))));
            }
        }
        Files.writeString(output.resolve("LOADED-CLASSES.json"),JSON.toJson(pins));
    }

    void answer(NativeHumanWorker.Answer answer) throws Exception {
        Method accept=NativeHumanWorker.class.getDeclaredMethod("accept",NativeHumanWorker.Answer.class);
        accept.setAccessible(true);
        try { accept.invoke(worker,answer); }
        catch (InvocationTargetException e) {
            if (e.getCause() instanceof IllegalArgumentException stale) throw stale;
            throw e;
        }
    }

    void physical120() throws Exception {
        Method observe=NativeHumanWorker.class.getDeclaredMethod("nativeState",Game.class); observe.setAccessible(true);
        JsonObject state=JSON.toJsonTree(observe.invoke(worker,actor.getGame())).getAsJsonObject();
        Set<Integer> ids=new HashSet<>(); int n=0;
        for (JsonElement player:state.getAsJsonArray("players")) {
            for (var zone:player.getAsJsonObject().getAsJsonObject("zones").entrySet()) {
                for (JsonElement card:zone.getValue().getAsJsonArray()) {
                    JsonArray row=card.getAsJsonArray();
                    if (!row.get(7).getAsBoolean()) { require(ids.add(row.get(0).getAsInt()),"duplicate physical id"); n++; }
                }
            }
        }
        require(n==120,"physical registry must stay 120");
        trace("physical120",n);
    }

    JsonObject currentChoice(String kind) throws Exception {
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(12);
        while(System.nanoTime()<end) {
            JsonObject f=frames.poll(1,TimeUnit.SECONDS);
            if(f==null || !f.get("event").getAsString().equals("choice")) continue;
            JsonObject q=f.getAsJsonObject("question");
            synchronized(worker) {
                if(q.get("kind").getAsString().equals(kind) && q.get("request_id").getAsString().equals(field("request").get(worker))) return f;
            }
        }
        throw new AssertionError("actual current native choice not presented: "+kind);
    }

    NativeHumanWorker.Answer cardAnswer(JsonObject frame, int id) {
        JsonObject q=frame.getAsJsonObject("question");
        for(JsonElement item:q.getAsJsonArray("choices")) {
            JsonObject c=item.getAsJsonObject(); JsonElement d=c.get("display");
            if(d.isJsonObject() && d.getAsJsonObject().has("card_id") && d.getAsJsonObject().get("card_id").getAsInt()==id)
                return new NativeHumanWorker.Answer(q.get("request_id").getAsString(),List.of(c.get("token").getAsString()));
        }
        throw new AssertionError("actual card not offered");
    }

    JsonObject selectAndRefresh(JsonObject frame, int id,
            forge.gamemodes.match.input.InputSelectEntitiesFromList<forge.game.card.Card> input,
            int selectedCount, long generation, int sameEpoch) throws Exception {
        var controller=(forge.player.PlayerControllerHuman)gui.getGameController(actor.getView());
        var queue=controller.getInputQueue();
        NativeHumanWorker.Answer a=cardAnswer(frame,id);
        int before;
        synchronized(worker) { before=field("decisions").getInt(worker); }
        answer(a);
        JsonObject candidate=null;
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(12);
        boolean returned=false;
        while(System.nanoTime()<end) {
            JsonObject f=frames.poll(1,TimeUnit.SECONDS); if(f==null) continue;
            if(f.get("event").getAsString().equals("choice")) candidate=f;
            if(f.get("event").getAsString().equals("completion") && f.get("count").getAsInt()>before) { returned=true; break; }
        }
        require(returned,"real native selection handler returned");
        require(input.getSelected().size()==selectedCount,"native selection actually mutated");
        require(queue.getInput()==input && queue.getInputGeneration()==generation && epoch==sameEpoch,
                "interaction preserved actual same input/generation/priority epoch");
        trace("same_input_handler_returned",Map.of("selected",selectedCount,"generation",generation,"epoch",epoch));
        String request;
        synchronized(worker) { request=(String)field("request").get(worker); }
        require(request!=null && !request.equals(a.request()) && candidate!=null &&
                candidate.getAsJsonObject("question").get("request_id").getAsString().equals(request),
                "FRESH_SAME_INPUT_OFFER_AFTER_SELECTION_"+selectedCount);
        JsonObject q=candidate.getAsJsonObject("question");
        require(q.get("kind").getAsString().equals("input:InputSelectEntitiesFromList"),"same native input offered");
        require(candidate.getAsJsonObject("info").keySet().equals(Set.of("ok_label","cancel_label","prompt")),"all interaction prompt fields retained");
        Set<String> oldTokens=new HashSet<>();
        for(JsonElement c:frame.getAsJsonObject("question").getAsJsonArray("choices")) oldTokens.add(c.getAsJsonObject().get("token").getAsString());
        for(JsonElement c:q.getAsJsonArray("choices")) require(!oldTokens.contains(c.getAsJsonObject().get("token").getAsString()),"fresh per-click one-use tokens");
        boolean rejected=false;
        try { answer(a); } catch(IllegalArgumentException stale) { rejected=true; }
        require(rejected,"previous selection token rejected");
        trace("fresh_same_input_and_stale_rejected",Map.of("selected",selectedCount,"generation",generation,"epoch",epoch));
        return candidate;
    }

    void sameInputInteraction() throws Exception {
        // Trusted harness interaction with real hand objects; not a natural spell/effect.
        var controller=(forge.player.PlayerControllerHuman)gui.getGameController(actor.getView());
        forge.util.collect.FCollection<forge.game.card.Card> cards=new forge.util.collect.FCollection<>();
        for(var card:actor.getCardsIn(ZoneType.Hand)) { if(cards.size()==3) break; cards.add(card); }
        require(cards.size()==3,"three actual canonical hand cards available");
        var input=new forge.gamemodes.match.input.InputSelectEntitiesFromList<forge.game.card.Card>(controller,2,3,cards);
        input.setMessage("Trusted harness: choose %d more actual hand cards");
        CompletableFuture<Void> ended=new CompletableFuture<>();
        frames.clear();
        Thread nativeWait=new Thread(() -> {
            try { input.showAndWait(); ended.complete(null); }
            catch(Throwable e) { ended.completeExceptionally(e); }
        },"trusted-native-selection-unit");
        nativeWait.setDaemon(true); nativeWait.start();
        JsonObject first=currentChoice("input:InputSelectEntitiesFromList");
        long generation=controller.getInputQueue().getInputGeneration(); int sameEpoch=epoch;
        trace("real_same_input_initial",Map.of("generation",generation,"epoch",epoch,"selected",input.getSelected().size()));
        JsonObject second=selectAndRefresh(first,cards.get(0).getId(),input,1,generation,sameEpoch);
        JsonObject third=selectAndRefresh(second,cards.get(1).getId(),input,2,generation,sameEpoch);
        JsonObject ok=null;
        for(JsonElement c:third.getAsJsonObject("question").getAsJsonArray("choices"))
            if(c.getAsJsonObject().get("display").isJsonPrimitive() && c.getAsJsonObject().get("display").getAsString().equals("button_ok")) ok=c.getAsJsonObject();
        require(ok!=null,"native minimum2 enables actual OK");
        answer(new NativeHumanWorker.Answer(third.getAsJsonObject("question").get("request_id").getAsString(),List.of(ok.get("token").getAsString())));
        ended.get(10,TimeUnit.SECONDS);
        require(input.getSelected().size()==2 && input.getSelected().contains(cards.get(0)) && input.getSelected().contains(cards.get(1)),"actual native two-choice result");
        require(controller.getInputQueue().getInput()!=input && controller.getInputQueue().getInputGeneration()>generation,"native OK removes and invalidates input");
        trace("real_same_input_completed",Map.of("selected",2,"generation",generation,"epoch",sameEpoch));
        physical120();
    }

    void fullReceipt(String stage) throws Exception {
        Method observe=NativeHumanWorker.class.getDeclaredMethod("nativeState",Game.class);
        observe.setAccessible(true);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(ObjectOutputStream out=new ObjectOutputStream(bytes)) { out.writeObject(MyRandom.getRandom()); }
        Map<String,Object> receipt=new LinkedHashMap<>();
        receipt.put("label","INTERNALPROTOCOL; NOT natural paid episode");
        receipt.put("native_state",observe.invoke(worker,actor.getGame()));
        receipt.put("rng_calls",MyRandom.callCount());
        receipt.put("rng_serialized_base64",Base64.getEncoder().encodeToString(bytes.toByteArray()));
        receipt.put("rng_serialized_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.toByteArray())));
        if(paidAbility!=null) {
            List<Object> mana=new ArrayList<>();
            for(var m:paidAbility.getPayingMana()) mana.add(List.of(m.getColor(),m.getSourceCard().getId(),m.getPlayer().getId(),m.isRestricted(),m.isSnow()));
            receipt.put("payment",Map.of("host",paidAbility.getHostCard().getId(),"ability",paidAbility.getId(),
                    "printed_cost",paidAbility.getHostCard().getManaCost().toString(),"paying_mana",mana,
                    "remaining",paidAbility.getManaCostBeingPaid()==null ? "input_stopped" : paidAbility.getManaCostBeingPaid().toString(),
                    "pool_empty",actor.getManaPool().isEmpty()));
        }
        Files.writeString(output.resolve(stage+".full-state.json"),JSON.toJson(receipt));
        physical120();
    }

    forge.game.card.Card actualCard(String name) {
        for(ZoneType zone:List.of(ZoneType.Hand,ZoneType.Library))
            for(var card:actor.getCardsIn(zone)) if(card.getName().equals(name)) return card;
        throw new AssertionError("missing actual canonical card: "+name);
    }

    <T> T awaitNativeWithDialogs(CompletableFuture<T> completion, int sourceId, String stage) throws Exception {
        require(Thread.currentThread()==driverThread,"one native protocol driver, no parallel RPC");
        completion.whenComplete((value,error) -> driverSignals.add(completion));
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(12);
        while(!completion.isDone()) {
            long left=deadline-System.nanoTime();
            if(left<=0) throw new TimeoutException("native completion not reached: "+stage);
            Object signal=driverSignals.poll(left,TimeUnit.NANOSECONDS);
            if(signal==null) throw new TimeoutException("native completion not reached: "+stage);
            if(!(signal instanceof JsonObject frame)) continue;
            JsonObject q=frame.getAsJsonObject("question");
            String kind=q.get("kind").getAsString();
            // Never drive payment/priority input buttons (especially Auto) in this wait.
            if(kind.startsWith("input:")) continue;
            synchronized(worker) {
                if(!q.get("request_id").getAsString().equals(field("request").get(worker))) continue;
                require(Set.of("getAbilityToPlay","getChoices","showOptionDialog","showInputDialog",
                        "confirm","showConfirmDialog","chooseSingleEntityForEffect").contains(kind),
                        "unsupported actual nested scalar prompt: "+kind);
                require(q.get("min").getAsInt()==1 && q.get("max").getAsInt()==1 &&
                        q.getAsJsonArray("choices").size()==1,"nested scalar must be required and unambiguous: "+kind);
                JsonObject choice=q.getAsJsonArray("choices").get(0).getAsJsonObject();
                if(kind.equals("getAbilityToPlay")) {
                    JsonObject display=choice.getAsJsonObject("display");
                    require(display.getAsJsonObject("source").get("card_id").getAsInt()==sourceId,
                            "actual offered mana ability belongs to clicked source");
                }
                trace("actual_nested_scalar_answer",Map.of("stage",stage,"kind",kind,"source",sourceId,
                        "request",q.get("request_id").getAsString(),"display",choice.get("display")));
                NativeHumanWorker.Answer answer=new NativeHumanWorker.Answer(q.get("request_id").getAsString(),
                        List.of(choice.get("token").getAsString()));
                answer(answer);  // Original synchronized worker and ActorBoundary consume the real token.
                boolean rejected=false;
                try { answer(answer); } catch(IllegalArgumentException stale) { rejected=true; }
                require(rejected,"nested scalar token is one-use");
            }
        }
        return completion.get();
    }

    JsonObject currentUiRoot() throws Exception {
        synchronized(worker) {
            ActorBoundary boundary=(ActorBoundary)field("boundary").get(worker);
            JsonObject state=new JsonObject();
            for(String name:List.of("prompt","okLabel","cancelLabel","ok","cancel","request","inputRevision",
                    "readyGeneration","readyEpoch","blocking","pendingOffer"))
                state.add(name,JSON.toJsonTree(field(name).get(worker)));
            state.addProperty("reply_identity",System.identityHashCode(field("reply").get(worker)));
            state.addProperty("ready_input_identity",System.identityHashCode(field("readyInput").get(worker)));
            var selection=(forge.gamemodes.match.Selection)field("selection").get(worker);
            Map<String,Object> marks=new LinkedHashMap<>();
            marks.put("cards",selection.cards().stream().map(boundary::describe).toList());
            marks.put("min",selection.min()); marks.put("max",selection.max());
            marks.put("targets",selection.targets().stream().map(boundary::describe).toList());
            marks.put("chosen",selection.chosen().stream().map(boundary::describe).toList());
            marks.put("actionable",selection.actionable().stream().map(boundary::describe).toList());
            state.add("selection",JSON.toJsonTree(marks));
            // Read the full real pending-token record; never insert or replace a token.
            synchronized(boundary) {
                Field pendingField=ActorBoundary.class.getDeclaredField("pending"); pendingField.setAccessible(true);
                Object pending=pendingField.get(boundary);
                JsonObject tokens=new JsonObject();
                if(pending!=null) for(var component:pending.getClass().getRecordComponents()) {
                    Method accessor=component.getAccessor(); accessor.setAccessible(true);
                    Object value=accessor.invoke(pending);
                    if(component.getName().equals("values")) {
                        Map<String,Object> descriptors=new TreeMap<>();
                        for(var entry:((Map<?,?>)value).entrySet()) descriptors.put((String)entry.getKey(),boundary.describe(entry.getValue()));
                        tokens.add("values",JSON.toJsonTree(descriptors));
                    } else tokens.add(component.getName(),JSON.toJsonTree(value));
                }
                state.add("boundary_pending",pending==null ? JsonNull.INSTANCE : tokens);
            }
            state.add("public_root",JSON.toJsonTree(boundary.snapshot(gui.getGameView())));
            return state;
        }
    }

    JsonObject staleRefreshIsolation(JsonObject oldPaymentOffer, long oldGeneration, int sameEpoch,
                                     CompletableFuture<Boolean> paymentWaiting) throws Exception {
        var controller=(forge.player.PlayerControllerHuman)gui.getGameController(actor.getView());
        var queue=controller.getInputQueue();
        require(queue.isCurrentPresentation(paymentInput,oldGeneration) && !paymentWaiting.isDone(),"old producer is genuinely current and unfinished before capture");
        final NativeHumanWorker.Answer savedManaAnswer=cardAnswer(oldPaymentOffer,27);
        synchronized(worker) {
            require(savedManaAnswer.request().equals(field("request").get(worker)),"save actual live partial-source27 answer before replacement");
        }
        Files.writeString(output.resolve("saved-partial-source27-answer.json"),JSON.toJson(savedManaAnswer));
        trace("actual_source27_answer_saved_before_replacement",savedManaAnswer);
        desktop.holdNextManaRefresh=true;
        CompletableFuture<Void> producerReturned=new CompletableFuture<>();
        actor.getGame().getAction().invoke(() -> {
            try { paymentInput.showMessage(); producerReturned.complete(null); }
            catch(Throwable error) { producerReturned.completeExceptionally(error); }
        });
        Runnable actual=desktop.captured.get(10,TimeUnit.SECONDS);
        producerReturned.get(10,TimeUnit.SECONDS);
        require(queue.isCurrentPresentation(paymentInput,oldGeneration),"actual native runnable captured with valid old generation");
        var cards=new forge.util.collect.FCollection<forge.game.card.Card>();
        for(var card:actor.getCardsIn(ZoneType.Hand)) { if(cards.size()==3) break; cards.add(card); }
        require(cards.size()==3,"replacement uses three real canonical hand references");
        var replacement=new forge.gamemodes.match.input.InputSelectEntitiesFromList<forge.game.card.Card>(controller,1,2,cards);
        replacement.setMessage("INTERNALPROTOCOL replacement: choose %d actual hand cards");
        CompletableFuture<Void> replacementEnded=new CompletableFuture<>();
        Thread wait=new Thread(() -> {
            try { replacement.showAndWait(); replacementEnded.complete(null); }
            catch(Throwable error) { replacementEnded.completeExceptionally(error); }
        },"internalprotocol-native-replacement");
        wait.setDaemon(true); wait.start();
        JsonObject offered=currentChoice("input:InputSelectEntitiesFromList");
        FThreads.invokeInEdtAndWait(() -> {});
        long replacementGeneration=queue.getInputGeneration();
        Field finished=forge.gamemodes.match.input.InputBase.class.getDeclaredField("finished"); finished.setAccessible(true);
        require(queue.getInput()==replacement && replacementGeneration>oldGeneration &&
                !queue.isCurrentPresentation(paymentInput,oldGeneration) && !finished.getBoolean(paymentInput),
                "replacement current, actual old input unfinished but generation rejected");
        boolean staleRejected=false;
        try { answer(savedManaAnswer); }
        catch(IllegalArgumentException stale) { staleRejected=true; }
        require(staleRejected,"old mana presentation token rejected after replacement");
        trace("same_saved_source27_answer_rejected_after_replacement",savedManaAnswer);
        JsonObject before=currentUiRoot();
        require(before.get("prompt").getAsString().startsWith("INTERNALPROTOCOL replacement:"),"real replacement prompt fully presented");
        require(before.getAsJsonObject("boundary_pending").get("id").equals(offered.getAsJsonObject("question").get("request_id")),"replacement owns actual actor tokens");
        Files.writeString(output.resolve("replacement-offer.json"),JSON.toJson(offered));
        Files.writeString(output.resolve("stale-before.ui.json"),JSON.toJson(before));
        fullReceipt("stale-before");
        trace("replacement_committed_before_old_refresh",Map.of("old_generation",oldGeneration,"new_generation",replacementGeneration,"epoch",sameEpoch));
        desktop.release(actual).get(10,TimeUnit.SECONDS);
        FThreads.invokeInEdtAndWait(() -> {});
        JsonObject after=currentUiRoot();
        Files.writeString(output.resolve("stale-after.ui.json"),JSON.toJson(after));
        fullReceipt("stale-after");
        JsonElement beforeNative=JsonParser.parseString(Files.readString(output.resolve("stale-before.full-state.json")));
        JsonElement afterNative=JsonParser.parseString(Files.readString(output.resolve("stale-after.full-state.json")));
        Map<String,Boolean> checks=new LinkedHashMap<>();
        checks.put("current_input_generation_unchanged",queue.getInput()==replacement && queue.getInputGeneration()==replacementGeneration && epoch==sameEpoch);
        checks.put("old_generation_rejected",!queue.isCurrentPresentation(paymentInput,oldGeneration));
        checks.put("old_input_still_unfinished",!finished.getBoolean(paymentInput));
        checks.put("prompt_unchanged",before.get("prompt").equals(after.get("prompt")));
        checks.put("selection_unchanged",before.get("selection").equals(after.get("selection")));
        checks.put("buttons_unchanged",List.of("okLabel","cancelLabel","ok","cancel").stream().allMatch(n -> before.get(n).equals(after.get(n))));
        checks.put("pending_tokens_unchanged",before.get("boundary_pending").equals(after.get("boundary_pending")));
        checks.put("full_ui_and_public_root_unchanged",before.equals(after));
        checks.put("full_native_payment_rng_root_unchanged",beforeNative.equals(afterNative));
        checks.put("no_stale_gui_callbacks",staleGuiCallbacks==0);
        Files.writeString(output.resolve("stale-invariants.json"),JSON.toJson(checks));
        trace("old_refresh_dispatched_invariants",checks);
        require(checks.values().stream().allMatch(Boolean::booleanValue),"STALE_NATIVE_REFRESH_MUTATED_CURRENT_PRESENTATION");
        JsonObject selected=selectAndRefresh(offered,cards.get(0).getId(),replacement,1,replacementGeneration,sameEpoch);
        JsonObject ok=null;
        for(var c:selected.getAsJsonObject("question").getAsJsonArray("choices"))
            if(c.getAsJsonObject().get("display").isJsonPrimitive() && c.getAsJsonObject().get("display").getAsString().equals("button_ok")) ok=c.getAsJsonObject();
        require(ok!=null,"actual replacement selection enables native OK");
        answer(new NativeHumanWorker.Answer(selected.getAsJsonObject("question").get("request_id").getAsString(),List.of(ok.get("token").getAsString())));
        replacementEnded.get(10,TimeUnit.SECONDS);
        JsonObject resumed=currentChoice("input:InputPayManaOfCostPayment");
        FThreads.invokeInEdtAndWait(() -> {});
        require(queue.getInput()==paymentInput && queue.getInputGeneration()>replacementGeneration &&
                !queue.isCurrentPresentation(paymentInput,oldGeneration) && !paymentWaiting.isDone(),"native payment resumed at fresh generation, old generation remains rejected");
        trace("retained_replacement_token_consumed_and_payment_resumed",Map.of("old_generation",oldGeneration,
                "replacement_generation",replacementGeneration,"resumed_generation",queue.getInputGeneration()));
        return resumed;
    }

    void partialManualMana() throws Exception {
        var controller=(forge.player.PlayerControllerHuman)gui.getGameController(actor.getView());
        var queue=controller.getInputQueue();
        require(queue.getInput() instanceof forge.gamemodes.match.input.InputPassPriority,"real priority parked for scene");
        require(actor.getCardsIn(ZoneType.Battlefield).size()==1 && actor.getManaPool().isEmpty(),"scene starts after real land");
        var first=actor.getCardsIn(ZoneType.Battlefield).getFirst();
        require(first.getName().equals("Plains") && !first.isTapped(),"first source is genuine played Plains");
        CompletableFuture<forge.game.card.Card> scene=new CompletableFuture<>();
        actor.getGame().getAction().invoke(() -> {
            try {
                var second=actor.getGame().getAction().moveToPlay(actualCard("Plains"),null,new HashMap<>());
                var spell=actualCard("Thalia, Guardian of Thraben");
                if(spell.getZone().getZoneType()!=ZoneType.Hand) spell=actor.getGame().getAction().moveToHand(spell,null);
                for(var sa:spell.getSpellAbilities()) if(sa.isSpell()) { paidAbility=sa; break; }
                require(paidAbility!=null && spell.getManaCost().getCMC()==2,"canonical actual two-mana spell");
                paidAbility.setActivatingPlayer(actor);
                scene.complete(second);
            } catch(Throwable error) { scene.completeExceptionally(error); }
        });
        var second=scene.get(10,TimeUnit.SECONDS);
        fullReceipt("scene-before-payment");
        trace("INTERNALPROTOCOL_scene",Map.of("spell",paidAbility.getHostCard().getName(),"printed_cost",paidAbility.getHostCard().getManaCost().toString(),
                "source1",first.getId(),"source2",second.getId(),"no_fake_stack",actor.getGame().getStack().isEmpty()));
        CompletableFuture<Boolean> paid=new CompletableFuture<>();
        frames.clear();
        actor.getGame().getAction().invoke(() -> {
            try {
                var part=paidAbility.getPayCosts().getCostMana();
                paid.complete(controller.payManaCost(part.getMana(),part,paidAbility,
                        "INTERNALPROTOCOL actual controller payment, NOT natural paid episode",null,false));
            } catch(Throwable error) { paid.completeExceptionally(error); }
        });
        JsonObject initial=currentChoice("input:InputPayManaOfCostPayment");
        FThreads.invokeInEdtAndWait(() -> {});
        paymentInput=(forge.gamemodes.match.input.InputPayMana)queue.getInput();
        long generation=queue.getInputGeneration(); int sameEpoch=epoch;
        require(paidAbility.getManaCostBeingPaid().getConvertedManaCost()==2 && !paymentInput.isActivatingManaAbility(),"native initial unpaid cost two, unlocked");
        long initialOffers=Files.readAllLines(output.resolve("wire.jsonl")).stream().filter(s -> s.contains("\"kind\":\"input:InputPayManaOfCostPayment\"")).count();
        require(initialOffers==1,"exactly one initial payment offer, no duplicate presentation receipt");
        fullReceipt("initial-payment");
        NativeHumanWorker.Answer old=cardAnswer(initial,first.getId());
        watchPartial=true;
        answer(old);
        awaitNativeWithDialogs(partialRefreshCommitted,first.getId(),"first-source-committed-refresh");
        FThreads.invokeInEdtAndWait(() -> {});
        watchPartial=false;
        require(partialPromptCallbacks==1,"one actual committed partial refresh");
        require(queue.getInput()==paymentInput && queue.getInputGeneration()==generation && epoch==sameEpoch,"same unfinished payment input/generation/epoch");
        require(!paymentInput.isActivatingManaAbility() && !paid.isDone(),"native partial input unlocked, payment still waiting");
        require(first.isTapped() && !second.isTapped(),"first actual source taps, second stays untapped");
        require(paidAbility.getManaCostBeingPaid().getConvertedManaCost()==1 && !paidAbility.getManaCostBeingPaid().isPaid(),"actual cost two to one, not paid");
        require(actor.getManaPool().isEmpty() && paidAbility.getPayingMana().size()==1 &&
                paidAbility.getPayingMana().get(0).getSourceCard().getId()==first.getId(),"native source1 mana consumed into actual spell payment");
        fullReceipt("partial-payment-committed");
        trace("partial_refresh_committed_barrier",Map.of("remaining",1,"generation",generation,"epoch",epoch,"source1_tapped",first.isTapped(),"source2_tapped",second.isTapped()));
        String request;
        synchronized(worker) { request=(String)field("request").get(worker); }
        JsonObject fresh=null;
        for(JsonObject f:frames) if(f.get("event").getAsString().equals("choice") &&
                f.getAsJsonObject("question").get("request_id").getAsString().equals(request)) fresh=f;
        require(request!=null && !request.equals(old.request()) && fresh!=null,
                "MISSING_FRESH_PARTIAL_PAYMENT_OFFER_AFTER_COMMITTED_REFRESH");
        require(fresh.getAsJsonObject("question").get("kind").getAsString().equals("input:InputPayManaOfCostPayment"),"same native payment type");
        require(fresh.getAsJsonObject("info").keySet().equals(Set.of("ok_label","cancel_label","prompt")),"all payment prompt fields retained");
        require(!fresh.getAsJsonObject("info").get("prompt").equals(initial.getAsJsonObject("info").get("prompt")),"actual partial unpaid-cost prompt changed");
        Set<String> oldTokens=new HashSet<>();
        for(JsonElement c:initial.getAsJsonObject("question").getAsJsonArray("choices")) oldTokens.add(c.getAsJsonObject().get("token").getAsString());
        for(JsonElement c:fresh.getAsJsonObject("question").getAsJsonArray("choices")) require(!oldTokens.contains(c.getAsJsonObject().get("token").getAsString()),"fresh partial tokens");
        boolean rejected=false;
        try { answer(old); } catch(IllegalArgumentException stale) { rejected=true; }
        require(rejected,"stale first-source token rejects");
        trace("fresh_partial_offer_stale_rejected",Map.of("generation",generation,"epoch",epoch));
        fresh=staleRefreshIsolation(fresh,generation,sameEpoch,paid);
        answer(cardAnswer(fresh,second.getId()));
        require(awaitNativeWithDialogs(paid,second.getId(),"second-source-payment-latch"),"real human controller payment returned true");
        FThreads.invokeInEdtAndWait(() -> {});
        require(first.isTapped() && second.isTapped() && actor.getManaPool().isEmpty(),"two actual sources paid, no floating mana");
        require(paidAbility.getPayingMana().size()==2 && paidAbility.getPayingMana().stream().map(m -> m.getSourceCard().getId()).collect(java.util.stream.Collectors.toSet()).equals(Set.of(first.getId(),second.getId())),"native payment records both actual sources");
        require(queue.getInput()!=paymentInput && queue.getInputGeneration()>generation,"paid input removed and generation invalidated");
        fullReceipt("completed-payment");
        trace("INTERNALPROTOCOL_payment_latch_true",Map.of("paying_mana",2,"source1",first.getId(),"source2",second.getId()));
    }

    void run(Path root) throws Exception {
        loaded(output);
        System.setProperty("java.awt.headless","true");
        GuiBase.setInterface(desktop); FModel.initialize(null,null);
        FModel.getPreferences().setPref(FPref.UI_ENABLE_SOUNDS,false);
        FModel.getPreferences().setPref(FPref.UI_ENABLE_MUSIC,false);
        FModel.getPreferences().setPref(FPref.PLAYER_NAME,"Human");
        FModel.getPreferences().setPref(FPref.UI_SHOW_ACTIONABLE_HIGHLIGHTS,true);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS,false);
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);
        JsonObject spec=JsonParser.parseString(Files.readString(root.resolve("SPEC.json"))).getAsJsonObject();
        MyRandom.setRandom(new Random(spec.get("seed").getAsLong()));
        worker=new NativeHumanWorker(new PrintWriter(Writer.nullWriter()) {
            @Override public void println(String line) { wire(line); }
        });
        field("evidence").set(worker,output); field("rngBase").setLong(worker,MyRandom.callCount());
        gui=new ProtocolGuiGame(this); field("gui").set(worker,gui);
        List<RegisteredPlayer> players=new ArrayList<>(); Map<Integer,Map<String,Integer>> disclosed=new TreeMap<>();
        for (int i=0;i<2;i++) {
            JsonObject row=spec.getAsJsonArray("decks").get(i).getAsJsonObject();
            Deck deck=DeckSerializer.fromFile(root.resolve("decks").resolve(row.get("file").getAsString()).toFile());
            Map<String,Integer> cards=new TreeMap<>(); row.getAsJsonObject("main").entrySet().forEach(e -> cards.put(e.getKey(),e.getValue().getAsInt()));
            Map<String,Integer> actual=new TreeMap<>(); for (var c:deck.getMain()) actual.merge(c.getKey().getName(),c.getValue(),Integer::sum);
            require(actual.equals(cards) && deck.getMain().countAll()==60,"exact R4 public deck");
            disclosed.put(i,cards); players.add(new RegisteredPlayer(deck));
        }
        int seat=spec.get("human_seat").getAsInt();
        for (int i=0;i<2;i++) {
            String name=spec.getAsJsonArray("decks").get(i).getAsJsonObject().get("name").getAsString();
            LobbyPlayerAi ai=new LobbyPlayerAi(name,null) {
                @Override public Player createIngamePlayer(Game game,int id) {
                    Player p=new Player(getName(),game,id); p.setFirstController(new PublicNameController(game,p,this,disclosed)); return p;
                }
            };
            ai.setAiProfile("Default"); players.get(i).setPlayer(i==seat ? new LobbyPlayerHuman(name) : ai);
        }
        HostedMatch match=new HostedMatch();
        match.setStartGameHook(() -> NativeNameMatchProbe.configureSearch(match.getGame(),false));
        GameRules rules=new GameRules(GameType.Constructed); rules.setGamesPerMatch(1); rules.setAllowCheatShuffle(false); rules.setPlayForAnte(false);
        NativeHumanWorker.Answer old=null; boolean fresh=false, staleRejected=false;
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(32);
        try {
            match.startMatch(rules,null,players,players.get(seat),gui);
            while (System.nanoTime()<deadline) {
                JsonObject f=frames.poll(2,TimeUnit.SECONDS); if(f==null) continue;
                if(!f.get("event").getAsString().equals("choice")) continue;
                JsonObject q=f.getAsJsonObject("question");
                synchronized(worker) { if(!q.get("request_id").getAsString().equals(field("request").get(worker))) continue; }
                JsonObject offer=f.getAsJsonObject("replay_offer");
                require(offer.keySet().equals(Set.of("kind","min","max","choices","info","turn","phase","actor")),"offer schema unchanged");
                String kind=q.get("kind").getAsString();
                if (clicked && committed && kind.equals("input:InputPassPriority") && epoch>landEpoch &&
                        actor.getCardsIn(ZoneType.Hand).size()==6 && actor.getCardsIn(ZoneType.Battlefield).size()==1) {
                    JsonObject zones=null;
                    for(JsonElement p:f.getAsJsonObject("state").getAsJsonArray("players"))
                        if(p.getAsJsonObject().get("player_id").getAsInt()==actor.getId()) zones=p.getAsJsonObject().getAsJsonObject("zones");
                    require(zones!=null && zones.getAsJsonObject("Hand").get("count").getAsInt()==6 &&
                            zones.getAsJsonObject("Battlefield").get("count").getAsInt()==1,"fresh actual full snapshot");
                    require(f.getAsJsonObject("info").keySet().equals(Set.of("ok_label","cancel_label","prompt")),"all prompt fields retained");
                    try { answer(old); } catch(IllegalArgumentException rejected) { staleRejected=true; }
                    require(staleRejected,"old land token must reject"); physical120(); fresh=true; trace("fresh_after_land",counts()); break;
                }
                List<String> tokens=new ArrayList<>(); JsonObject chosen=null;
                if (!clicked && kind.equals("input:InputPassPriority") && offer.get("phase").getAsString().equals("MAIN1")) {
                    for(JsonElement c:q.getAsJsonArray("choices")) {
                        JsonObject choice=c.getAsJsonObject(); JsonElement d=choice.get("display");
                        if(d.isJsonObject() && d.getAsJsonObject().has("card_id") &&
                                d.getAsJsonObject().getAsJsonObject("face").get("type").getAsString().contains("Land")) { chosen=choice; break; }
                    }
                    if(chosen!=null) {
                        require(actor.getCardsIn(ZoneType.Hand).size()==7 && actor.getCardsIn(ZoneType.Battlefield).isEmpty(),"real opening seven");
                        physical120(); clicked=true; trace("actual_land_click",counts());
                    }
                }
                if(chosen==null && kind.startsWith("input:")) for(JsonElement c:q.getAsJsonArray("choices"))
                    if(c.getAsJsonObject().get("display").isJsonPrimitive() && c.getAsJsonObject().get("display").getAsString().equals("button_ok")) { chosen=c.getAsJsonObject(); break; }
                int min=q.get("min").getAsInt();
                if(chosen!=null) tokens.add(chosen.get("token").getAsString());
                else for(JsonElement c:q.getAsJsonArray("choices")) { if(tokens.size()>=min) break; tokens.add(c.getAsJsonObject().get("token").getAsString()); }
                NativeHumanWorker.Answer a=new NativeHumanWorker.Answer(q.get("request_id").getAsString(),tokens);
                if(chosen!=null && clicked && old==null) old=a;
                try { answer(a); } catch(IllegalArgumentException stale) { trace("already_revoked_client_frame",kind); }
            }
            require(stopCallbacks>0,"genuine old stop callback before native zone commit observed");
            require(nested>0,"genuine nested native land ability serviced");
            require(fresh,"fresh native priority/input after hand7->6 BF0->1");
            require(transientOffers==0,"NO_ACTIONABLE_TRANSIENT_BEFORE_NATIVE_COMMIT: "+transientOffers);
            require(!(boolean)field("failed").get(worker),"actual worker must not fail");
            sameInputInteraction();
            partialManualMana();
        } finally {
            if(actor!=null) {
                trace("HARNESS_CONCESSION_NOT_FULLGAME",counts());
                FThreads.invokeInEdtLater(() -> gui.getGameController(actor.getView()).concede());
                finished.await(8,TimeUnit.SECONDS);
                require(actor.getGame().isGameOver(),"harness concession must really end game");
                physical120();
                fullReceipt("final-after-concession");
            }
        }
    }

    public static void main(String[] args) {
        long began=System.nanoTime();
        PartialManaReadyUnit unit=new PartialManaReadyUnit(); int exit=1;
        try {
            unit.output=Path.of(args[1]); unit.run(Path.of(args[0])); exit=0;
            Files.writeString(unit.output.resolve("UNIT-PASS.json"),JSON.toJson(Map.of("scope","real-opening-land-nested-unit; harness concession NOT fullgame",
                    "stop_callbacks",unit.stopCallbacks,"transient_offers",unit.transientOffers,"nested",unit.nested,"committed",unit.committed)));
        } catch(Throwable e) { e.printStackTrace(System.err); }
        try { Files.writeString(unit.output.resolve("JVM-EXIT.json"),JSON.toJson(Map.of("exit",exit,
                "wall_seconds",(System.nanoTime()-began)/1e9,
                "cpu_millis",ProcessHandle.current().info().totalCpuDuration().orElse(java.time.Duration.ZERO).toMillis(),
                "label","bounded unit; harness concession; NOT fullgame"))); }
        catch(IOException e) { e.printStackTrace(System.err); exit=1; }
        System.exit(exit);
    }
}
