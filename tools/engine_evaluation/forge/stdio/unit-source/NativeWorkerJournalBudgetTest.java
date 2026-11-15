// SPDX-License-Identifier: GPL-3.0-or-later
// Original controls for the Forge Team/Card-Forge host adapter.
// Controlled native poses and INTERNAL counter boundaries, not natural games.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.event.GameEventGameStarted;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.util.MyRandom;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public final class NativeWorkerJournalBudgetTest extends SimulationTest {
    private static final long LIMIT = 536870912L;
    private static final Gson JSON = new Gson();

    private static Field field(String name) throws Exception {
        try {
            Field field = NativeHumanWorker.class.getDeclaredField(name);
            field.setAccessible(true);
            return field;
        } catch (NoSuchFieldException missing) {
            throw new AssertionError("Missing worker journal accounting field: " + name, missing);
        }
    }

    private static void set(NativeHumanWorker worker, String name, Object value) throws Exception {
        field(name).set(worker, value);
    }

    private static boolean flag(NativeHumanWorker worker, String name) throws Exception {
        return field(name).getBoolean(worker);
    }

    private static long bytes(NativeHumanWorker worker) throws Exception {
        return field("journalBytes").getLong(worker);
    }

    private static Path evidence(NativeHumanWorker worker) throws Exception {
        return (Path) field("evidence").get(worker);
    }

    private static NativeHumanWorker worker(StringWriter output) throws Exception {
        NativeHumanWorker worker = new NativeHumanWorker(new PrintWriter(output));
        set(worker, "evidence", Files.createTempDirectory("journal-budget-unit-"));
        return worker;
    }

    private static byte[] encoded(Object value) {
        return (JSON.toJsonTree(value).toString() + "\n").getBytes(StandardCharsets.UTF_8);
    }

    private static void journal(NativeHumanWorker worker, String stream, Object value) throws Exception {
        Method method = NativeHumanWorker.class.getDeclaredMethod("journal", String.class, Object.class);
        method.setAccessible(true);
        try {
            method.invoke(worker, stream, value);
        } catch (InvocationTargetException wrapped) {
            if (wrapped.getCause() instanceof Exception error) throw error;
            if (wrapped.getCause() instanceof Error error) throw error;
            throw wrapped;
        }
    }

    private static void exhausted(NativeHumanWorker worker, String stream, Object value) {
        IllegalStateException error = Assert.expectThrows(IllegalStateException.class,
                () -> journal(worker, stream, value));
        Assert.assertEquals(error.getMessage(), "journal_budget");
    }

    @DataProvider(name = "lateTurns")
    public Object[][] lateTurns() {
        return new Object[][] {{0, 31}, {1, 31}, {0, 81}, {1, 81}};
    }

    @DataProvider(name = "seats")
    public Object[][] seats() { return new Object[][] {{0}, {1}}; }

    private Game pose(int seat) {
        MyRandom.setRandom(new Random(2026110601L));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck("CONTROLLED journal-budget seat " + i);
            if (i == seat) {
                deck.getMain().add("Lightning Bolt", 4);
                deck.getMain().add("Mountain", 56);
            } else deck.getMain().add("Plains", 60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("journal-budget-seat" + i, null);
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED journal-budget unit"));
        game.setAge(GameStage.Play);
        Player actor = game.getPlayers().get(seat), other = game.getPlayers().get(1 - seat);
        actor.setLife(20, null);
        other.setLife(3, null);
        game.getPhaseHandler().devModeSet(PhaseType.END_OF_TURN, other);
        addCardToZone("Mountain", actor, ZoneType.Battlefield);
        addCardToZone("Lightning Bolt", actor, ZoneType.Hand);
        for (int i = 0; i < 55; i++) addCardToZone("Mountain", actor, ZoneType.Library);
        for (int i = 0; i < 3; i++) addCardToZone("Lightning Bolt", actor, ZoneType.Library);
        for (int i = 0; i < 60; i++) addCardToZone("Plains", other, ZoneType.Library);
        game.getPhaseHandler().setPriority(actor);
        Assert.assertFalse(game.isGameOver());
        return game;
    }

    @Test(dataProvider = "lateTurns")
    public void controlledLateTurnObservationIsNotATurnBudget(int seat, int turn) throws Exception {
        Game game = pose(seat);
        Player actor = game.getPlayers().get(seat);
        // CONTROLLED dev pose: this does not certify natural play through these turns.
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor, turn);
        StringWriter output = new StringWriter();
        NativeHumanWorker worker = worker(output);
        set(worker, "actor", actor);
        worker.nativeEvent(new GameEventGameStarted(GameType.Constructed, actor, game.getPlayers()));
        Assert.assertFalse(flag(worker, "failed"));
        Assert.assertFalse(flag(worker, "terminal"));
        Assert.assertFalse(game.isGameOver());
        JsonObject row = JsonParser.parseString(Files.readString(evidence(worker).resolve("native.jsonl")))
                .getAsJsonObject();
        Assert.assertEquals(row.getAsJsonObject("state").get("turn").getAsInt(), turn);
        Assert.assertTrue(output.toString().isEmpty());
    }

    @Test
    public void utf8AndLfAreAggregatedAcrossStreams() throws Exception {
        NativeHumanWorker worker = worker(new StringWriter());
        Map<String, String> first = Map.of("text", "\u00e9\u6f22\ud83d\ude00");
        Map<String, String> second = Map.of("text", "line\nnext");
        Assert.assertTrue(encoded(first).length > (JSON.toJsonTree(first) + "\n").length());
        journal(worker, "native", first);
        journal(worker, "paid-pending", second);
        journal(worker, "native", second);
        long total = encoded(first).length + 2L * encoded(second).length;
        Assert.assertEquals(bytes(worker), total);
        Assert.assertEquals(Files.readAllBytes(evidence(worker).resolve("paid-pending.jsonl")), encoded(second));
        Assert.assertEquals(Files.readString(evidence(worker).resolve("native.jsonl")),
                new String(encoded(first), StandardCharsets.UTF_8) + new String(encoded(second), StandardCharsets.UTF_8));
    }

    @Test
    public void inclusiveLimitAcceptsLastLfThenRejectsEveryLaterStream() throws Exception {
        NativeHumanWorker worker = worker(new StringWriter());
        Map<String, String> row = Map.of("text", "\u00e9");
        // INTERNAL boundary injection, not a 512 MiB write or natural game.
        set(worker, "journalBytes", LIMIT - encoded(row).length);
        journal(worker, "native", row);
        Assert.assertEquals(bytes(worker), LIMIT);
        Assert.assertFalse(flag(worker, "failed"));
        Assert.assertEquals(Files.readAllBytes(evidence(worker).resolve("native.jsonl")), encoded(row));
        exhausted(worker, "paid-pending", row);
        Assert.assertEquals(bytes(worker), LIMIT);
        Assert.assertTrue(flag(worker, "failed"));
        Assert.assertFalse(Files.exists(evidence(worker).resolve("paid-pending.jsonl")));
        Assert.assertFalse(Files.exists(evidence(worker).resolve("MISMATCH.json")));
        set(worker, "journalBytes", 0L); // Replenishing a counter must not unstick failure.
        IllegalStateException stopped = Assert.expectThrows(IllegalStateException.class,
                () -> journal(worker, "native", row));
        Assert.assertEquals(stopped.getMessage(), "diagnostic_already_stopped");
        Assert.assertEquals(bytes(worker), 0L);
        Assert.assertEquals(Files.readAllBytes(evidence(worker).resolve("native.jsonl")), encoded(row));
    }

    @Test
    public void oneByteOverRemainingDoesNotAppendOrAdvanceVerifier() throws Exception {
        NativeHumanWorker worker = worker(new StringWriter());
        Map<String, String> first = Map.of("text", "accepted");
        Map<String, String> next = Map.of("text", "\u6f22");
        journal(worker, "native", first);
        Object verifier = field("causalVerifier").get(worker);
        Map<?, ?> before = Map.copyOf((Map<?, ?>) field("cursors").get(worker));
        long near = LIMIT - encoded(next).length + 1;
        set(worker, "journalBytes", near);
        exhausted(worker, "native", next);
        Assert.assertTrue(flag(worker, "failed"));
        Assert.assertEquals(bytes(worker), near);
        Assert.assertSame(field("causalVerifier").get(worker), verifier);
        Assert.assertEquals(field("cursors").get(worker), before);
        Assert.assertEquals(Files.readAllBytes(evidence(worker).resolve("native.jsonl")), encoded(first));
    }

    @Test
    public void actualIoFailureIsStickyAndDoesNotChargeUnwrittenBytes() throws Exception {
        NativeHumanWorker worker = worker(new StringWriter());
        Path stream = evidence(worker).resolve("native.jsonl");
        Files.createDirectory(stream); // Genuine filesystem write failure, not a mocked exception.
        Map<String, String> row = Map.of("text", "unwritten");
        IllegalStateException failedWrite = Assert.expectThrows(IllegalStateException.class,
                () -> journal(worker, "native", row));
        Assert.assertTrue(failedWrite.getCause() instanceof IOException);
        Assert.assertTrue(flag(worker, "failed"));
        Assert.assertEquals(bytes(worker), 0L);
        Assert.assertNull(field("causalVerifier").get(worker));
        Assert.assertTrue(((Map<?, ?>) field("cursors").get(worker)).isEmpty());
        Files.delete(stream);
        Assert.expectThrows(IllegalStateException.class, () -> journal(worker, "native", row));
        Assert.assertFalse(Files.exists(stream));
    }

    @Test
    public void replayMismatchStillRecordsWrittenRowAndDiagnostic() throws Exception {
        NativeHumanWorker worker = worker(new StringWriter());
        JsonElement expectedRow = JSON.toJsonTree(Map.of("text", "expected"));
        @SuppressWarnings("unchecked")
        Map<String, List<JsonElement>> reference =
                (Map<String, List<JsonElement>>) field("expected").get(worker);
        reference.put("starts", List.of());
        reference.put("completions", List.of());
        reference.put("final", List.of(JSON.toJsonTree(Map.of("done", true))));
        reference.put("native", List.of(expectedRow));
        set(worker, "replay", true);
        journal(worker, "native", expectedRow);
        Map<String, String> mismatch = Map.of("text", "different");
        IllegalStateException error = Assert.expectThrows(IllegalStateException.class,
                () -> journal(worker, "native", mismatch));
        Assert.assertEquals(error.getMessage(), "strict_replay_mismatch_native_1");
        Assert.assertTrue(flag(worker, "failed"));
        Assert.assertEquals(bytes(worker), (long) encoded(expectedRow).length + encoded(mismatch).length);
        Assert.assertEquals(Files.readAllLines(evidence(worker).resolve("native.jsonl")).size(), 2);
        JsonObject diagnostic = JsonParser.parseString(Files.readString(evidence(worker).resolve("MISMATCH.json")))
                .getAsJsonObject();
        Assert.assertEquals(diagnostic.get("contract").getAsString(), "CAUSAL_COMPLETION_REPLAY");
        Assert.assertEquals(diagnostic.get("index").getAsInt(), 1);
        Assert.assertEquals(diagnostic.get("actual"), JSON.toJsonTree(mismatch));
        Assert.assertEquals(((Map<?, ?>) field("cursors").get(worker)).get("native"), 1);
    }

    @Test(dataProvider = "seats")
    public void realNativePaidWinCannotCompleteAQuotaFailedWorker(int seat) throws Exception {
        Game game = pose(seat);
        Player actor = game.getPlayers().get(seat), other = game.getPlayers().get(1 - seat);
        List<SpellAbility> chosen = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        Assert.assertNotNull(chosen);
        Assert.assertEquals(chosen.size(), 1);
        SpellAbility ability = chosen.get(0);
        Assert.assertEquals(ability.getHostCard().getName(), "Lightning Bolt");
        Assert.assertTrue(ability.canPlay());
        Assert.assertTrue(ability.isTargetNumberValid());
        Assert.assertEquals(ability.getTargets().getFirstTargetedPlayer(), other);
        Assert.assertTrue(ComputerUtil.playStack(ability, actor, game));
        Assert.assertEquals(game.getStack().size(), 1);
        Assert.assertEquals(other.getLife(), 3);
        Assert.assertEquals(actor.getCardsIn(ZoneType.Battlefield).stream().filter(Card::isTapped).count(), 1L);
        game.getStack().resolveStack();
        game.getAction().checkStateEffects(true);
        Assert.assertEquals(other.getLife(), 0);
        Assert.assertTrue(game.isGameOver());
        Assert.assertNotNull(game.getOutcome());
        StringWriter output = new StringWriter();
        NativeHumanWorker worker = worker(output);
        set(worker, "journalBytes", LIMIT);
        exhausted(worker, "native", Map.of("text", "over-budget"));
        worker.completed(game);
        Assert.assertTrue(flag(worker, "failed"));
        Assert.assertFalse(flag(worker, "terminal"));
        Assert.assertTrue(output.toString().isEmpty());
        Assert.assertFalse(Files.exists(evidence(worker).resolve("final.jsonl")));
        Assert.assertFalse(Files.exists(evidence(worker).resolve("COMPLETION-CONTRACT.json")));
    }

    @DataProvider(name = "unpairedSurrogates")
    public Object[][] unpairedSurrogates() {
        return new Object[][] {{"\ud800"}, {"\udc00"}};
    }

    @Test(dataProvider = "unpairedSurrogates")
    public void unpairedUtf16FailsClosedBeforeAnyJournalMutation(String unpaired) throws Exception {
        StringWriter output = new StringWriter();
        NativeHumanWorker worker = worker(output);
        Map<String, String> accepted = Map.of("text", "already accepted");
        journal(worker, "native", accepted);
        long before = bytes(worker);
        Object verifier = field("causalVerifier").get(worker);
        Map<?, ?> cursors = Map.copyOf((Map<?, ?>) field("cursors").get(worker));
        Map<String, String> malformed = Map.of("text", unpaired);
        Assert.assertTrue(JSON.toJsonTree(malformed).toString().contains(unpaired));
        IllegalStateException error = Assert.expectThrows(IllegalStateException.class,
                () -> journal(worker, "native", malformed));
        Assert.assertTrue(error.getCause() instanceof java.nio.charset.CharacterCodingException);
        Assert.assertTrue(flag(worker, "failed"));
        Assert.assertFalse(flag(worker, "terminal"));
        Assert.assertEquals(bytes(worker), before);
        Assert.assertSame(field("causalVerifier").get(worker), verifier);
        Assert.assertEquals(field("cursors").get(worker), cursors);
        Assert.assertEquals(Files.readAllBytes(evidence(worker).resolve("native.jsonl")), encoded(accepted));
        Assert.assertFalse(Files.exists(evidence(worker).resolve("MISMATCH.json")));
        IllegalStateException stopped = Assert.expectThrows(IllegalStateException.class,
                () -> journal(worker, "paid-pending", accepted));
        Assert.assertEquals(stopped.getMessage(), "diagnostic_already_stopped");
        Assert.assertFalse(Files.exists(evidence(worker).resolve("paid-pending.jsonl")));
        Assert.assertEquals(bytes(worker), before);
        Assert.assertEquals(field("cursors").get(worker), cursors);
        worker.completed(null); // A failed worker must not consult or invent an outcome.
        Assert.assertTrue(output.toString().isEmpty());
        Assert.assertFalse(Files.exists(evidence(worker).resolve("final.jsonl")));
    }
}
