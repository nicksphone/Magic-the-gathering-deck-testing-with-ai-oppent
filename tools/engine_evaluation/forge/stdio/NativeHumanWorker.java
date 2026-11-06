// SPDX-License-Identifier: GPL-3.0-or-later
// Original host adapter for the Forge Team/Card-Forge engine and human controller.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
// Owned 2026-11-05 presentation-fence adapter; requires base61e944 + owned native patch.
// Owned R7 additive producer provenance + CAUSAL_COMPLETION_REPLAY verification.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonElement;
import com.google.common.eventbus.Subscribe;
import forge.game.card.Card;
import forge.game.zone.ZoneType;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import forge.GuiDesktop;
import forge.ai.LobbyPlayerAi;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.card.CardView;
import forge.game.player.Player;
import forge.game.player.PlayerView;
import forge.game.player.RegisteredPlayer;
import forge.gamemodes.match.HostedMatch;
import forge.gamemodes.match.Selection;
import forge.gamemodes.net.IRemote;
import forge.gamemodes.net.ProtocolGuiGame;
import forge.gamemodes.net.event.GuiGameEvent;
import forge.gamemodes.net.event.IdentifiableNetEvent;
import forge.gamemodes.net.event.NetEvent;
import forge.gui.FThreads;
import forge.gui.GuiBase;
import forge.interfaces.IGameController;
import forge.item.PaperCard;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.player.LobbyPlayerHuman;
import forge.player.PlayerControllerHuman;
import forge.trackable.TrackableCollection;
import forge.util.MyRandom;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.Reader;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

public final class NativeHumanWorker implements IRemote {
    private static final long JOURNAL_BYTE_LIMIT = 536870912L;
    private long journalBytes;
    private Path evidence;
    private JsonObject matchSpec;
    private final Map<String,String> importedDecks = new TreeMap<>();
    private boolean replay;
    private long rngBase;
    private final Map<String,List<JsonElement>> expected = new TreeMap<>();
    private final Map<String,Integer> cursors = new TreeMap<>();
    private JsonElement pendingOffer, submitted;
    private JsonObject pendingEdge, submittedEdge;
    private int decisions, starts;
    private final ThreadLocal<Integer> activeStart = ThreadLocal.withInitial(() -> -1);
    private int pendingParent = -1, submittedParent = -1;
    private boolean reversedSeen, paidSeen;
    private final NativeProducerTrace producerTrace = new NativeProducerTrace();
    private CausalCompletionVerifier causalVerifier;
    private Game pendingTerminal;

    private synchronized void journal(String stream, Object value) {
        if (failed) throw new IllegalStateException("diagnostic_already_stopped");
        JsonElement row = JSON.toJsonTree(value);
        if (stream.equals("completions")) {
            int id=row.getAsJsonObject().get("start_id").getAsInt();
            row.getAsJsonObject().add("producer",producerTrace.completion(id));
        }
        try {
            var utf8 = StandardCharsets.UTF_8.newEncoder().encode(java.nio.CharBuffer.wrap(row+"\n"));
            byte[] encoded = new byte[utf8.remaining()];
            utf8.get(encoded);
            if (encoded.length > JOURNAL_BYTE_LIMIT - journalBytes) {
                failed = true;
                throw new IllegalStateException("journal_budget");
            }
            Files.write(evidence.resolve(stream+".jsonl"), encoded,
                    java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
            journalBytes += encoded.length;
            int index = cursors.getOrDefault(stream,0);
            try {
                if (causalVerifier == null) causalVerifier = new CausalCompletionVerifier(replay ? expected : null);
                causalVerifier.accept(stream,row);
            } catch (IllegalStateException mismatch) {
                Files.writeString(evidence.resolve("MISMATCH.json"),JSON.toJson(Map.of("stream",stream,"index",index,
                        "actual",row,"reason",mismatch.getMessage(),"contract","CAUSAL_COMPLETION_REPLAY")));
                failed = true;
                throw mismatch;
            }
            cursors.put(stream,index+1);
        } catch (IOException error) { failed = true; throw new IllegalStateException(error); }
    }

    private List<Object> physical(Game game, Player p, ZoneType zone) {
        List<Object> list = new ArrayList<>();
        for (Card c : p.getCardsIn(zone)) list.add(List.of(c.getId(),c.getName(),c.getOwner().getId(),
                c.getController().getId(),c.isTapped(),c.hasSickness(),c.isFaceDown(),c.isToken(),
                c.getGameTimestamp(),c.getManaCost().toString(),c.getSetCode()));
        return list;
    }

    private Object nativeState(Game game) {
        try {
        List<Object> players = new ArrayList<>(), stack = new ArrayList<>();
        for (Player p : game.getRegisteredPlayers()) {
            Map<String,Object> zones = new TreeMap<>();
            for (ZoneType z : List.of(ZoneType.Hand,ZoneType.Library,ZoneType.Battlefield,ZoneType.Graveyard,
                    ZoneType.Exile,ZoneType.Command,ZoneType.Sideboard)) zones.put(z.name(),physical(game,p,z));
            List<Object> mana = new ArrayList<>();
            for (var m : p.getManaPool()) mana.add(List.of(m.getColor(),m.getSourceCard().getId(),m.getPlayer().getId(),m.isRestricted(),m.isSnow()));
            players.add(Map.of("id",p.getId(),"life",p.getLife(),"zones",zones,"mana",mana));
        }
        for (var entry : game.getStack()) {
            var sa = entry.getSpellAbility();
            List<Object> targets = new ArrayList<>(), paid = new ArrayList<>();
            for (var t : sa.getTargets()) {
                if (t instanceof Player p) targets.add(List.of("player",p.getId()));
                else if (t instanceof Card c) targets.add(List.of("card",c.getId(),c.getGameTimestamp()));
                else if (t instanceof forge.game.spellability.SpellAbility target) {
                    Map<String,Object> actual = new java.util.LinkedHashMap<>();
                    actual.put("type","spell_ability"); actual.put("ability_id",target.getId());
                    Card host = target.getHostCard();
                    actual.put("host",host == null ? null : Map.of("card_id",host.getId(),"game_timestamp",host.getGameTimestamp()));
                    Player activating = target.getActivatingPlayer();
                    actual.put("activating_player",activating == null ? null : activating.getId());
                    targets.add(actual);
                } else throw new IllegalStateException("unsupported_native_target");
            }
            for (var m : sa.getPayingMana()) paid.add(List.of(m.getColor(),m.getSourceCard().getId(),m.getPlayer().getId()));
            stack.add(Map.of("id",entry.getId(),"ability_id",sa.getId(),"source",sa.getHostCard().getId(),
                    "controller",sa.getActivatingPlayer().getId(),"targets",targets,"paid",paid,
                    "mana_cost",sa.getPayCosts().getCostMana()==null ? "none" : sa.getPayCosts().getCostMana().getMana().toString()));
        }
        return Map.of("players",players,"stack",stack,"turn",game.getPhaseHandler().getTurn(),
                "phase",String.valueOf(game.getPhaseHandler().getPhase()),"rng_delta",MyRandom.callCount()-rngBase);
        } catch (RuntimeException | Error error) { fail(error); throw error; }
    }

    @Subscribe public void nativeEvent(forge.game.event.GameEvent event) {
        String kind = event.getClass().getSimpleName();
        if (kind.equals("GameEventPlayerPriority") || kind.equals("GameEventGameFinished")) synchronized (this) {
            if (kind.equals("GameEventPlayerPriority")) priorityEpoch++;
            readyInput = null;
            invalidate();
        }
        if (!Set.of("GameEventGameStarted","GameEventShuffle","GameEventSpellAbilityCast",
                "GameEventSpellResolved","GameEventPlayerPriority","GameEventGameFinished").contains(kind)) return;
        Game game = actor.getGame();
        boolean wasPaidSeen = paidSeen;
        if (kind.equals("GameEventPlayerPriority")) for (var item : game.getStack()) {
            var sa=item.getSpellAbility();
            if (sa.isSpell() && sa.getActivatingPlayer()==actor && sa.getTotalManaSpent()>0) paidSeen=true;
        }
        journal("native",Map.of("event",kind,"state",nativeState(game)));
        if (!wasPaidSeen && paidSeen) journal("paid-pending",nativeState(game));
    }

    // Causal starts drive replay. They are not successful dispatches, casts, or payments.
    private synchronized int begin(String kind, JsonElement ticket, int parent,JsonObject edge) {
        if (starts>=1000) { failed=true; throw new IllegalStateException("input_budget"); }
        int id=starts++;
        journal("starts",Map.of("start_id",id,"parent_start",parent,"kind",kind,"ticket",ticket,"parent_edge",edge));
        emit(Map.of("event","started","count",starts,"start_id",id,"role","invocation_not_acceptance"));
        return id;
    }

    private synchronized void decision(int start, String kind, JsonElement ticket, String result) {
        if (++decisions>1000) { failed=true; throw new IllegalStateException("input_budget"); }
        journal("completions",Map.of("start_id",start,"kind",kind,"ticket",ticket,"result",result));
        emit(Map.of("event","completion","count",decisions,"start_id",start,"role","native_return_not_cast_receipt"));
        if (pendingTerminal != null && decisions == starts) finishTerminal(pendingTerminal);
    }
    private static final Gson JSON = new Gson();
    private static final int MAX_LINE = 16_384;
    record Answer(String request, List<String> tokens) { }
    private record Input(String line, boolean eof) { }

    static Answer decode(String line) {
        try (JsonReader reader = new JsonReader(new StringReader(line))) {
            if (line.length() > MAX_LINE) throw new IllegalArgumentException();
            reader.setLenient(false);
            String request = null;
            List<String> tokens = null;
            Set<String> keys = new HashSet<>();
            reader.beginObject();
            while (reader.hasNext()) {
                String key = reader.nextName();
                if (!keys.add(key)) throw new IllegalArgumentException();
                if (key.equals("request_id")) request = opaque(reader);
                else if (key.equals("tokens")) {
                    tokens = new ArrayList<>();
                    reader.beginArray();
                    while (reader.hasNext()) {
                        if (tokens.size() == 256) throw new IllegalArgumentException();
                        tokens.add(opaque(reader));
                    }
                    reader.endArray();
                } else throw new IllegalArgumentException();
            }
            reader.endObject();
            if (reader.peek() != JsonToken.END_DOCUMENT || request == null || tokens == null ||
                    new HashSet<>(tokens).size() != tokens.size()) throw new IllegalArgumentException();
            return new Answer(request, List.copyOf(tokens));
        } catch (Exception malformed) {
            throw new IllegalArgumentException("invalid_response");
        }
    }

    private static String opaque(JsonReader reader) throws IOException {
        if (reader.peek() != JsonToken.STRING) throw new IllegalArgumentException();
        String value = reader.nextString();
        if (!value.matches("[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")) throw new IllegalArgumentException();
        return value;
    }

    static String decodeCheckpoint(String line) {
        try (JsonReader reader = new JsonReader(new StringReader(line))) {
            if (line.length() > MAX_LINE) throw new IllegalArgumentException();
            reader.setLenient(false);
            reader.beginObject();
            if (!reader.hasNext() || !reader.nextName().equals("checkpoint_request_id")) return null;
            String request = opaque(reader);
            if (reader.hasNext()) throw new IllegalArgumentException();
            reader.endObject();
            if (reader.peek() != JsonToken.END_DOCUMENT) throw new IllegalArgumentException();
            return request;
        } catch (Exception malformed) {
            throw new IllegalArgumentException("invalid_checkpoint_request");
        }
    }

    private synchronized void checkpoint(String requestId) {
        if (aborted || terminal || failed || actor == null || reply == null || request == null ||
                !request.equals(requestId) || actor.getGame().isGameOver()) {
            throw new IllegalArgumentException("checkpoint_not_current");
        }
        var human = (PlayerControllerHuman)gui.getGameController(actor.getView());
        var queue = human.getInputQueue();
        // Queue transitions invoke host callbacks only after releasing this monitor.
        // Retain that input lifetime through capture/publication, in worker->queue order.
        synchronized (queue) {
            if (!blocking) {
                if (starts != decisions) throw new IllegalArgumentException("checkpoint_busy");
                if (readyInput == null || readyEpoch != priorityEpoch ||
                        !queue.isCurrentPresentation(readyInput,readyGeneration)) {
                    throw new IllegalArgumentException("checkpoint_input_replaced");
                }
            }
            if (matchSpec == null || importedDecks.isEmpty()) throw new IllegalStateException("checkpoint_inputs_absent");
            boolean committed = false;
            try {
                Map<String,Object> journals = new TreeMap<>();
                for (String stream : List.of("starts","completions","native","paid-pending","final")) {
                    Path file = evidence.resolve(stream+".jsonl");
                    List<JsonElement> rows = new ArrayList<>();
                    if (Files.exists(file)) for (String line : Files.readAllLines(file)) rows.add(JsonParser.parseString(line));
                    if (rows.size() != cursors.getOrDefault(stream,0)) throw new IllegalStateException("checkpoint_journal_count_"+stream);
                    journals.put(stream,rows);
                }
                if (cursors.getOrDefault("final",0) != 0) throw new IllegalStateException("checkpoint_already_final");
                String body = JSON.toJson(Map.of("schema",1,"spec",matchSpec.deepCopy(),"decks",Map.copyOf(importedDecks),
                        "starts",starts,"completions",decisions,"pending_offer",pendingOffer.deepCopy(),
                        "actor_view",boundary.snapshot(gui.getGameView()),"native_state",nativeState(actor.getGame()),"journals",journals));
                Path target = evidence.resolve("CHECKPOINT.json");
                if (Files.isSymbolicLink(target)) throw new IOException("checkpoint_target_symlink");
                Path temporary = Files.createTempFile(evidence,".checkpoint-",".tmp",
                        java.nio.file.attribute.PosixFilePermissions.asFileAttribute(
                                java.nio.file.attribute.PosixFilePermissions.fromString("rw-------")));
                try {
                    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
                    try (var output = java.nio.channels.FileChannel.open(temporary,java.nio.file.StandardOpenOption.WRITE)) {
                        var buffer = java.nio.ByteBuffer.wrap(bytes);
                        while (buffer.hasRemaining()) output.write(buffer);
                        output.force(true);
                    }
                    Files.move(temporary,target,java.nio.file.StandardCopyOption.ATOMIC_MOVE,
                            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    committed = true;
                    try (var directory = java.nio.channels.FileChannel.open(evidence,java.nio.file.StandardOpenOption.READ)) { directory.force(true); }
                    String digest = java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
                    emit(Map.of("event","checkpoint_saved","request_id",requestId,"sha256",digest));
                } finally { Files.deleteIfExists(temporary); }
            } catch (IOException | java.security.NoSuchAlgorithmException error) {
                error.printStackTrace(System.err);
                emit(Map.of("event","checkpoint_failed","request_id",requestId,"committed",committed,
                        "reason",committed ? "durability_unconfirmed_after_commit" : "write_failed_before_commit"));
            }
        }
    }

    static String rejectionReason(String checkpoint,IllegalArgumentException error) {
        return checkpoint != null && "checkpoint_busy".equals(error.getMessage())
                ? "checkpoint_busy" : "invalid_or_stale_response";
    }

    static int[] choiceBounds(int min,int max,int count) {
        // Forge's reveal dialog uses (-1,-1): acknowledge without selecting a card.
        if (min == -1 && max == -1) return new int[] {0,0};
        return new int[] {min, max < 0 || max > count ? count : max};
    }

    static Map<String,Object> dialogInfo(GuiGameEvent call) {
        Object[] a = call.getObjects();
        return switch (call.getMethod()) {
            case confirm -> Map.of("prompt",(String) a[1],"labels",labels(a[3]));
            case showConfirmDialog -> Map.of("prompt",(String) a[0],"title",(String) a[1],"labels",List.of(a[2],a[3]));
            case showOptionDialog -> Map.of("prompt",(String) a[0],"title",(String) a[1],"labels",labels(a[3]));
            case showInputDialog -> Map.of("prompt",(String) a[0],"title",(String) a[1]);
            case getChoices, chooseSingleEntityForEffect, order -> Map.of("prompt",(String) a[0]);
            default -> Map.of();
        };
    }

    static List<?> orderChoices(GuiGameEvent call) {
        Object[] a = call.getObjects();
        if ((Integer) a[2] != 0 || (Integer) a[3] != 0 || (Boolean) a[7]) {
            throw new IllegalArgumentException("unsupported_partial_or_sideboard_order");
        }
        List<Object> choices = new ArrayList<>((List<?>) a[4]);
        choices.addAll((List<?>) a[5]);
        return List.copyOf(choices);
    }

    private static List<String> labels(Object value) {
        List<String> result = new ArrayList<>();
        if (value == null) return result;
        for (Object label : (List<?>) value) {
            if (!(label instanceof String text)) throw new IllegalArgumentException("unsupported_label_type");
            result.add(text);
        }
        return List.copyOf(result);
    }

    void dispatch(Runnable action) {
        try { action.run(); }
        catch (RuntimeException | Error error) {
            fail(error);
        }
    }

    private void fail(Throwable error) {
        error.printStackTrace(System.err);
        invalidate();
        failed = true;
    }

    private final PrintWriter wire;
    private ProtocolGuiGame gui;
    private Player actor;
    private ActorBoundary boundary;
    private Selection selection = Selection.NONE;
    private boolean ok, cancel, blocking;
    private String okLabel = "", cancelLabel = "", request;
    private String prompt = "";
    private Consumer<List<Object>> reply;
    private volatile boolean terminal, failed;
    private boolean aborted;
    private volatile long priorityEpoch;
    private volatile long inputRevision;
    private forge.gamemodes.match.input.Input readyInput;
    private long readyGeneration = -1, readyEpoch = -1;

    NativeHumanWorker(PrintWriter wire) { this.wire = wire; }

    private synchronized void emit(Map<String,Object> frame) {
        wire.println(JSON.toJson(frame));
        wire.flush();
        if (wire.checkError()) throw new IllegalStateException("transport_closed");
    }

    private synchronized void invalidate() {
        inputRevision++;
        if (boundary != null) boundary.invalidate();
        request = null;
        reply = null;
    }

    private synchronized void publish(String kind,List<?> choices,int min,int max,
                                      Consumer<List<Object>> handler,Map<String,Object> info,String producerForm) {
        if (aborted || terminal) throw new IllegalStateException("worker_closed");
        Map<String,Object> question = boundary.offer(kind,choices,min,max);
        List<Object> descriptors = new ArrayList<>();
        for (Object value : choices) descriptors.add(boundary.describe(value));
        pendingOffer = JSON.toJsonTree(Map.of("kind",kind,"min",min,"max",max,"choices",descriptors,
                "info",info,"turn",gui.getGameView().getTurn(),"phase",String.valueOf(gui.getGameView().getPhase()),"actor",actor.getId()));
        pendingParent=activeStart.get();
        pendingEdge=producerTrace.publicationEdge(producerForm,pendingParent);
        request = (String) question.get("request_id");
        reply = handler;
        emit(Map.of("event","choice","question",question,"info",info,"replay_offer",pendingOffer,
                "state",boundary.snapshot(gui.getGameView())));
    }

    private synchronized void accept(Answer answer) {
        if (reply == null || !answer.request().equals(request)) throw new IllegalArgumentException("stale_response");
        List<Object> values = boundary.answer(actor,answer.request(),answer.tokens());
        List<Object> selected = new ArrayList<>();
        for (Object v : values) selected.add(boundary.describe(v));
        submitted = JSON.toJsonTree(Map.of("offer",pendingOffer,"selected",selected));
        submittedParent=pendingParent;
        submittedEdge=pendingEdge.deepCopy();
        Consumer<List<Object>> callback = reply;
        request = null;
        reply = null;
        callback.accept(values);
    }

    synchronized void abort() {
        if (terminal || aborted) return;
        aborted = true;
        invalidate();
        emit(Map.of("event","aborted","reason","input_closed"));
    }

    synchronized void completed(Game game) {
        if (aborted || terminal || failed) return;
        if (!game.isGameOver() || game.getOutcome() == null) { failed = true; return; }
        if (pendingTerminal != null) throw new IllegalStateException("duplicate_native_terminal");
        journal("final",Map.of("state",nativeState(game),"outcomes",game.getOutcome().getOutcomeStrings()));
        pendingTerminal = game;
        if (decisions == starts) finishTerminal(game);
    }

    private synchronized void finishTerminal(Game game) {
        if (aborted || terminal || failed) return;
        if (replay) for (String stream : expected.keySet()) if (cursors.getOrDefault(stream,0)!=expected.get(stream).size()) {
            failed=true; throw new IllegalStateException("unconsumed_journal_"+stream);
        }
        causalVerifier.finish();
        try { Files.writeString(evidence.resolve("COMPLETION-CONTRACT.json"),JSON.toJson(causalVerifier.diagnostic())); }
        catch (IOException error) { failed=true; throw new IllegalStateException(error); }
        invalidate();
        emit(Map.of("event","game_complete","turns",game.getOutcome().getLastTurnNumber(),
                "outcomes",game.getOutcome().getOutcomeStrings(),"draw",game.getOutcome().isDraw(),
                "win_condition",game.getOutcome().getWinCondition().name(),
                "coverage",Map.of("reverse_order",reversedSeen,"paid_human",paidSeen)));
        terminal = true;
    }

    private void observeInputReadiness() {
        var controller = (PlayerControllerHuman) gui.getGameController(actor.getView());
        var queue = controller.getInputQueue();
        queue.setRemovalObserver(producerTrace::removed);
        queue.setPresentationListener(new forge.gamemodes.match.input.InputQueue.PresentationListener() {
            @Override public void invalidated() {
                synchronized (NativeHumanWorker.this) { readyInput = null; invalidate(); }
            }
            @Override public void presented(forge.gamemodes.match.input.Input input, long generation) {
                dispatch(() -> {
                synchronized (NativeHumanWorker.this) {
                    if (!queue.isCurrentPresentation(input,generation) || blocking || aborted || terminal) return;
                    readyInput = input;
                    readyGeneration = generation;
                    readyEpoch = priorityEpoch;
                    invalidate();
                    publishInput();
                }
                });
            }
        });
    }

    private synchronized void publishInput() {
        if (actor == null || blocking) return;
        IGameController controller = gui.getGameController(actor.getView());
        if (!(controller instanceof PlayerControllerHuman human)) throw new IllegalStateException("not_human_controller");
        var input = human.getInputQueue().getInput();
        if (input == null || input.getClass().getSimpleName().equals("InputLockUI")) return;
        final long generation = readyGeneration, epoch = readyEpoch, revision = inputRevision;
        if (input != readyInput || epoch != priorityEpoch ||
                !human.getInputQueue().isCurrentPresentation(input,generation)) return;
        // Owned selection receipt: choices and chosen values share one native snapshot.
        final Selection currentSelection = selection;
        LinkedHashSet<Object> choices = new LinkedHashSet<>();
        choices.addAll(currentSelection.cards());
        choices.addAll(currentSelection.targets());
        choices.addAll(currentSelection.actionable());
        if (ok) choices.add("button_ok");
        if (cancel) choices.add("button_cancel");
        if (choices.isEmpty()) return;
        Map<String,Object> info = new java.util.LinkedHashMap<>(Map.of(
                "ok_label",okLabel,"cancel_label",cancelLabel,"prompt",prompt));
        if (input instanceof forge.gamemodes.match.input.InputSelectEntitiesFromList<?>) {
            List<Object> chosen = new ArrayList<>();
            for (var entity : List.copyOf(((forge.gamemodes.match.input.InputSelectEntitiesFromList<?>)input).getSelected())) chosen.add(boundary.describe(entity.getView()));
            info.put("selection",Map.of("min",currentSelection.min(),"max",currentSelection.max(),
                    "chosen",List.copyOf(chosen),"input",input.getClass().getSimpleName(),
                    "generation",generation,"priority_epoch",epoch,"revision",revision,"actor",actor.getId()));
        }
        if (input instanceof forge.gamemodes.match.input.InputSelectStackItems stackInput) {
            List<Object> chosen = new ArrayList<>();
            for (var entry : List.copyOf(stackInput.getSelected())) chosen.add(boundary.describe(entry.getView()));
            info.put("stack_selection",Map.of("chosen",List.copyOf(chosen),
                    "input",input.getClass().getSimpleName(),"generation",generation,
                    "priority_epoch",epoch,"revision",revision,"actor",actor.getId()));
        } else if (choices.stream().anyMatch(forge.game.spellability.StackItemView.class::isInstance)) {
            throw new IllegalArgumentException("unqualified_mixed_stack_target_input");
        }
        emit(Map.of("event","input_ready","input",input.getClass().getSimpleName(),
                "generation",generation,"priority_epoch",epoch,"revision",revision));
        publish("input:"+input.getClass().getSimpleName(),new ArrayList<>(choices),1,1,answer -> {
            Object selected = answer.get(0);
            JsonElement ticket = submitted.deepCopy();
            int parent=submittedParent;
            JsonObject publicationEdge=submittedEdge.deepCopy();
            FThreads.invokeInEdtLater(() -> dispatch(() -> {
                if (!human.getInputQueue().isCurrentPresentation(input,generation) ||
                        epoch != priorityEpoch || revision != inputRevision) {
                    emit(Map.of("event","rejected","reason","input_replaced_before_dispatch"));
                    return;
                }
                if (selected instanceof forge.game.spellability.StackItemView item) boundary.requireCurrentStackItem(item);
                int start=begin("dispatch",ticket,parent,producerTrace.inputInvocationEdge(publicationEdge));
                int previous=activeStart.get();
                activeStart.set(start);
                NativeProducerTrace.Dispatch producer = producerTrace.enterDispatch(start,input,generation,actor);
                try {
                String result = "void";
                if (selected instanceof CardView card) result=String.valueOf(controller.selectCard(card,null,null));
                else if (selected instanceof PlayerView player) controller.selectPlayer(player,null);
                else if (selected instanceof forge.game.spellability.StackItemView item) controller.selectStackItem(item);
                else if (selected.equals("button_ok")) controller.selectButtonOk();
                else if (selected.equals("button_cancel")) controller.selectButtonCancel();
                else throw new IllegalArgumentException("unsupported_click");
                producerTrace.dispatchReturned(producer);
                decision(start,"dispatch",ticket,result);
                } finally { producerTrace.leaveDispatch(); activeStart.set(previous); }
            }));
        },info,"INPUT_REQUEST_INVOKE_LATER");
    }

    @Override
    @SuppressWarnings("unchecked")
    public synchronized void send(NetEvent event) {
        try {
            if (aborted || terminal) return;
            GuiGameEvent call = (GuiGameEvent) event;
            Object[] a = call.getObjects();
            switch (call.getMethod()) {
                case openView -> {
                    PlayerView owner = ((TrackableCollection<PlayerView>) a[0]).iterator().next();
                    actor = gui.getGameView().getGame().getPlayer(owner.getId());
                    boundary = new ActorBoundary(actor);
                    NativeNameMatchProbe.configureSearch(actor.getGame(),false);
                    for (Player p : actor.getGame().getPlayers()) if (p.getController() instanceof forge.ai.PlayerControllerAi ai) ai.getAi().setUseSimulation(null);
                    actor.getGame().subscribeToEvents(this);
                    observeInputReadiness();
                    List<Object> identities=new ArrayList<>();
                    for (Player p : actor.getGame().getPlayers()) identities.add(Map.of(
                            "native_player_id",p.getId(),"name",p.getName(),"is_ai",p.getController().isAI()));
                    try { Files.writeString(evidence.resolve("NATIVE-IDENTITY.json"),JSON.toJson(identities)); }
                    catch (IOException error) { throw new IllegalStateException(error); }
                }
                case setSelection -> {
                    selection = (Selection) a[0];
                    if (!blocking) invalidate();
                }
                case updateButtons -> {
                    if (actor == null || a[0] == null || ((PlayerView) a[0]).getId() != actor.getId() || blocking) return;
                    okLabel = (String) a[1]; cancelLabel = (String) a[2];
                    ok = (Boolean) a[3]; cancel = (Boolean) a[4];
                    invalidate();
                }
                case showPromptMessage -> {
                    if (actor != null && a[0] instanceof PlayerView owner && owner.getId() == actor.getId()) {
                        prompt = (String) a[1];
                        if (!blocking) invalidate();
                    }
                }
                case finishGame -> { readyInput = null; invalidate(); }
                case applyDelta, showRevealedCards -> {
                    if (actor != null) emit(Map.of("event","view","state",boundary.snapshot(gui.getGameView())));
                }
                default -> { /* Native deltas, messages and raw events never cross this boundary. */ }
            }
        } catch (RuntimeException error) { error.printStackTrace(System.err); failed = true; }
    }

    @Override
    public Object sendAndWait(IdentifiableNetEvent event) {
        try {
            GuiGameEvent call = (GuiGameEvent) event;
            Object[] a = call.getObjects();
            if (call.getMethod() == forge.gamemodes.net.ProtocolMethod.getAbilityToPlay
                    && ((List<?>)a[1]).isEmpty()) return null;
            List<?> choices;
            NativeProducerTrace.Dialog producer = producerTrace.enterDialog(call,actor,
                    (PlayerControllerHuman)gui.getGameController(actor.getView()));
            int min = 1, max = 1;
            Map<String,Object> info = dialogInfo(call);
            switch (call.getMethod()) {
                case getAbilityToPlay -> {
                    choices = (List<?>) a[1];
                    if (choices.isEmpty()) return null;
                }
                case getChoices -> {
                    choices = (List<?>) a[3]; min = (Integer) a[1]; max = (Integer) a[2];
                    int[] bounds = choiceBounds(min,max,choices.size());
                    min = bounds[0]; max = bounds[1];
                }
                case confirm, showConfirmDialog -> choices = List.of(true,false);
                case showOptionDialog -> {
                    List<?> options = (List<?>) a[3];
                    choices = java.util.stream.IntStream.range(0,options.size()).boxed().toList();
                }
                case showInputDialog -> {
                    if (!(a[4] instanceof List<?> options) || options.isEmpty()) throw new IllegalArgumentException("unsupported_text_input");
                    choices = options;
                }
                case chooseSingleEntityForEffect -> { choices = (List<?>) a[1]; if ((Boolean) a[3]) min = 0; }
                case order -> { choices = orderChoices(call); min = max = choices.size(); }
                default -> throw new IllegalArgumentException("unsupported_native_dialog");
            }
            CompletableFuture<List<Object>> result = new CompletableFuture<>();
            final JsonElement[] ticket = new JsonElement[1];
            final int[] start = new int[1];
            synchronized (this) {
                blocking = true;
                publish(call.getMethod().name(),choices,min,max,values -> {
                    ticket[0]=submitted.deepCopy();
                    start[0]=begin("dialog",ticket[0],submittedParent,submittedEdge.deepCopy());
                    result.complete(values);
                },info,"BLOCKING_SEND_AND_WAIT");
            }
            try {
                List<Object> answer = result.get(120,TimeUnit.SECONDS);
                producerTrace.dialogReturned(producer,start[0],answer);
                decision(start[0],"dialog",ticket[0],"returned");
                if (call.getMethod()==forge.gamemodes.net.ProtocolMethod.order && choices.size()>=2) {
                    List<Object> reverse=new ArrayList<>(choices); java.util.Collections.reverse(reverse);
                    if (reverse.equals(answer)) reversedSeen=true;
                }
                if (call.getMethod() == forge.gamemodes.net.ProtocolMethod.order) {
                    // Keep order preferences session-local; never silently remember a gameplay choice.
                    return new forge.gui.interfaces.IGuiGame.OrderResult<>(answer,false);
                }
                return call.getMethod() == forge.gamemodes.net.ProtocolMethod.getChoices ? answer :
                        answer.isEmpty() ? null : answer.get(0);
            } finally { synchronized (this) { blocking = false; } }
        } catch (Exception error) {
            error.printStackTrace(System.err);
            failed = true;
            throw new IllegalStateException("native_dialog_failed");
        }
    }

    private static String readLine(Reader reader) throws IOException {
        StringBuilder line = new StringBuilder();
        int value;
        while ((value = reader.read()) != -1 && value != '\n') {
            if (line.length() == MAX_LINE) throw new IOException("response_too_large");
            line.append((char) value);
        }
        return value == -1 && line.isEmpty() ? null : line.toString();
    }

    private static Map<String,Integer> cards(Deck deck) {
        Map<String,Integer> result = new TreeMap<>();
        for (Map.Entry<PaperCard,Integer> item : deck.getMain()) result.merge(item.getKey().getName(),item.getValue(),Integer::sum);
        return result;
    }

    public static void main(String[] args) {
        PrintWriter output = new PrintWriter(System.out,true,StandardCharsets.UTF_8);
        System.setOut(System.err);
        NativeHumanWorker remote = new NativeHumanWorker(output);
        int exit = 1;
        try {
            if (args.length != 1) throw new IllegalArgumentException("expected_owned_input_directory");
            Path root = Path.of(args[0]);
            remote.evidence=root;
            remote.replay=Files.exists(root.resolve("REPLAY.path"));
            if (remote.replay) {
                Path original=Path.of(Files.readString(root.resolve("REPLAY.path")).trim());
                for (String stream : List.of("starts","completions","native","paid-pending","final")) {
                    List<JsonElement> rows=new ArrayList<>();
                    for (String line : Files.readAllLines(original.resolve(stream+".jsonl"))) rows.add(JsonParser.parseString(line));
                    remote.expected.put(stream,rows);
                }
            }
            JsonObject spec = JsonParser.parseString(Files.readString(root.resolve("SPEC.json"))).getAsJsonObject();
            int seat = spec.get("human_seat").getAsInt();
            if (seat < 0 || seat > 1 || !spec.get("open_decklists").getAsBoolean() || spec.getAsJsonArray("decks").size() != 2) {
                throw new IllegalArgumentException("invalid_match_spec");
            }
            remote.matchSpec=spec.deepCopy();
            System.setProperty("java.awt.headless","true");
            GuiBase.setInterface(new GuiDesktop());
            FModel.initialize(null,null);
            FModel.getPreferences().setPref(FPref.UI_ENABLE_SOUNDS,false);
            FModel.getPreferences().setPref(FPref.UI_ENABLE_MUSIC,false);
            FModel.getPreferences().setPref(FPref.PLAYER_NAME,"Human");
            FModel.getPreferences().setPref(FPref.UI_SHOW_ACTIONABLE_HIGHLIGHTS,true);
            FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS,false);
            FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);
            MyRandom.setRandom(new Random(spec.get("seed").getAsLong()));
            remote.rngBase=MyRandom.callCount();
            List<RegisteredPlayer> players = new ArrayList<>();
            Map<Integer,Map<String,Integer>> disclosed = new TreeMap<>();
            for (int i=0;i<2;i++) {
                JsonObject row = spec.getAsJsonArray("decks").get(i).getAsJsonObject();
                String filename = row.get("file").getAsString();
                if (filename.contains("/") || filename.contains("\\")) throw new IllegalArgumentException("invalid_deck_path");
                Deck deck = DeckSerializer.fromFile(root.resolve("decks").resolve(filename).toFile());
                Map<String,Integer> expected = new TreeMap<>();
                row.getAsJsonObject("main").entrySet().forEach(e -> expected.put(e.getKey(),e.getValue().getAsInt()));
                if (deck == null || deck.getMain().countAll() != 60 || !cards(deck).equals(expected) ||
                        expected.values().stream().anyMatch(n -> n <= 0)) throw new IllegalArgumentException("changed_deck_import");
                remote.importedDecks.put(filename,Files.readString(root.resolve("decks").resolve(filename)));
                disclosed.put(i,Map.copyOf(expected));
                players.add(new RegisteredPlayer(deck));
            }
            for (int i=0;i<2;i++) {
                String name = spec.getAsJsonArray("decks").get(i).getAsJsonObject().get("name").getAsString();
                LobbyPlayerAi ai = new LobbyPlayerAi(name,null) {
                    @Override public Player createIngamePlayer(Game game,int id) {
                        Player p = new Player(getName(),game,id);
                        p.setFirstController(new PublicNameController(game,p,this,disclosed));
                        return p;
                    }
                };
                ai.setAiProfile("Default");
                players.get(i).setPlayer(i == seat ? new LobbyPlayerHuman(name) : ai);
            }
            remote.gui = new ProtocolGuiGame(remote);
            HostedMatch match = new HostedMatch();
            match.setStartGameHook(() -> NativeNameMatchProbe.configureSearch(match.getGame(),spec.get("flat_monte_carlo").getAsBoolean()));
            match.setEndGameHook(() -> remote.completed(match.getGame()));
            GameRules rules = new GameRules(GameType.Constructed);
            rules.setGamesPerMatch(1); rules.setAllowCheatShuffle(false); rules.setPlayForAnte(false);
            ArrayBlockingQueue<Input> inbound = new ArrayBlockingQueue<>(128);
            Thread reader = new Thread(() -> {
                try {
                    Reader input = new InputStreamReader(System.in,StandardCharsets.UTF_8);
                    String line;
                    while ((line = readLine(input)) != null) inbound.put(new Input(line,false));
                } catch (Exception ignored) { /* EOF/error aborts the worker, never fabricates a game result. */ }
                finally { try { inbound.put(new Input(null,true)); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); } }
            },"actor-stdin");
            reader.setDaemon(true); reader.start();
            match.startMatch(rules,null,players,players.get(seat),remote.gui);
            while (!remote.terminal && !remote.failed) {
                Input input = inbound.poll(200,TimeUnit.MILLISECONDS);
                if (input == null) continue;
                if (input.eof()) { remote.abort(); exit = 2; break; }
                String checkpoint = null;
                try {
                    checkpoint = decodeCheckpoint(input.line());
                    if (checkpoint == null) remote.accept(decode(input.line()));
                    else remote.checkpoint(checkpoint);
                }
                catch (IllegalArgumentException rejected) { remote.emit(Map.of("event","rejected","reason",rejectionReason(checkpoint,rejected))); }
            }
            if (remote.terminal && !remote.failed) exit = 0;
            if (remote.failed) remote.emit(Map.of("event","error","reason","unsupported_or_failed_native_callback"));
        } catch (Throwable error) {
            remote.emit(Map.of("event","error","reason","native_worker_failed"));
            error.printStackTrace(System.err);
        } finally { remote.invalidate(); }
        System.exit(exit);
    }
}
