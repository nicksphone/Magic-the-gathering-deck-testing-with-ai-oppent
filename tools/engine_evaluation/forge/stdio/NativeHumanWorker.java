// SPDX-License-Identifier: GPL-3.0-or-later
// Original host adapter for the Forge Team/Card-Forge engine and human controller.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
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
            error.printStackTrace(System.err);
            invalidate();
            failed = true;
        }
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

    NativeHumanWorker(PrintWriter wire) { this.wire = wire; }

    private synchronized void emit(Map<String,Object> frame) {
        wire.println(JSON.toJson(frame));
        wire.flush();
        if (wire.checkError()) throw new IllegalStateException("transport_closed");
    }

    private synchronized void invalidate() {
        if (boundary != null) boundary.invalidate();
        request = null;
        reply = null;
    }

    private synchronized void publish(String kind,List<?> choices,int min,int max,
                                      Consumer<List<Object>> handler,Map<String,Object> info) {
        if (aborted || terminal) throw new IllegalStateException("worker_closed");
        Map<String,Object> question = boundary.offer(kind,choices,min,max);
        request = (String) question.get("request_id");
        reply = handler;
        emit(Map.of("event","choice","question",question,"info",info,
                "state",boundary.snapshot(gui.getGameView())));
    }

    private synchronized void accept(Answer answer) {
        if (reply == null || !answer.request().equals(request)) throw new IllegalArgumentException("stale_response");
        List<Object> values = boundary.answer(actor,answer.request(),answer.tokens());
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
        invalidate();
        emit(Map.of("event","game_complete","turns",game.getOutcome().getLastTurnNumber(),
                "outcomes",game.getOutcome().getOutcomeStrings(),"draw",game.getOutcome().isDraw(),
                "win_condition",game.getOutcome().getWinCondition().name()));
        terminal = true;
    }

    private void publishInput() {
        if (actor == null || blocking) return;
        IGameController controller = gui.getGameController(actor.getView());
        if (!(controller instanceof PlayerControllerHuman human)) throw new IllegalStateException("not_human_controller");
        var input = human.getInputQueue().getInput();
        if (input == null || input.getClass().getSimpleName().equals("InputLockUI")) return;
        LinkedHashSet<Object> choices = new LinkedHashSet<>();
        choices.addAll(selection.cards());
        choices.addAll(selection.targets());
        choices.addAll(selection.actionable());
        if (ok) choices.add("button_ok");
        if (cancel) choices.add("button_cancel");
        if (choices.isEmpty()) return;
        publish("input:"+input.getClass().getSimpleName(),new ArrayList<>(choices),1,1,answer -> {
            Object selected = answer.get(0);
            FThreads.invokeInEdtLater(() -> dispatch(() -> {
                if (human.getInputQueue().getInput() != input) {
                    emit(Map.of("event","rejected","reason","input_replaced_before_dispatch"));
                    return;
                }
                if (selected instanceof CardView card) controller.selectCard(card,null,null);
                else if (selected instanceof PlayerView player) controller.selectPlayer(player,null);
                else if (selected.equals("button_ok")) controller.selectButtonOk();
                else if (selected.equals("button_cancel")) controller.selectButtonCancel();
                else throw new IllegalArgumentException("unsupported_click");
            }));
        },Map.of("ok_label",okLabel,"cancel_label",cancelLabel,"prompt",prompt));
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
                }
                case setSelection -> {
                    selection = (Selection) a[0];
                    if (!blocking) { invalidate(); publishInput(); }
                }
                case updateButtons -> {
                    if (actor == null || a[0] == null || ((PlayerView) a[0]).getId() != actor.getId() || blocking) return;
                    okLabel = (String) a[1]; cancelLabel = (String) a[2];
                    ok = (Boolean) a[3]; cancel = (Boolean) a[4];
                    invalidate(); publishInput();
                }
                case showPromptMessage -> {
                    if (actor != null && a[0] instanceof PlayerView owner && owner.getId() == actor.getId()) prompt = (String) a[1];
                }
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
            List<?> choices;
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
            synchronized (this) {
                blocking = true;
                publish(call.getMethod().name(),choices,min,max,result::complete,info);
            }
            try {
                List<Object> answer = result.get(120,TimeUnit.SECONDS);
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
            JsonObject spec = JsonParser.parseString(Files.readString(root.resolve("SPEC.json"))).getAsJsonObject();
            int seat = spec.get("human_seat").getAsInt();
            if (seat < 0 || seat > 1 || !spec.get("open_decklists").getAsBoolean() || spec.getAsJsonArray("decks").size() != 2) {
                throw new IllegalArgumentException("invalid_match_spec");
            }
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
                try { remote.accept(decode(input.line())); }
                catch (IllegalArgumentException rejected) { remote.emit(Map.of("event","rejected","reason","invalid_or_stale_response")); }
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
