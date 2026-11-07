// SPDX-License-Identifier: GPL-3.0-or-later
// Original in-process boundary tests using the Forge Team/Card-Forge engine.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.simulation.SimulationTest;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameType;
import forge.game.GameView;
import forge.game.card.CardView;
import forge.game.player.Player;
import forge.game.player.PlayerView;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbilityView;
import forge.game.zone.ZoneType;
import forge.gamemodes.match.HostedMatch;
import forge.gamemodes.net.IRemote;
import forge.gamemodes.net.ProtocolGuiGame;
import forge.gamemodes.net.event.GuiGameEvent;
import forge.gamemodes.net.event.IdentifiableNetEvent;
import forge.gamemodes.net.event.NetEvent;
import forge.gui.FThreads;
import forge.interfaces.IGameController;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.player.GamePlayerUtil;
import forge.player.LobbyPlayerHuman;
import forge.trackable.TrackableCollection;
import forge.util.MyRandom;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class NativeHumanBoundaryTest extends SimulationTest {
    private static final Gson JSON = new Gson();

    @DataProvider(name = "seats")
    public Object[][] seats() { return new Object[][] {{0}, {1}}; }

    // Raw native callbacks stay in this trusted receiver. Its client queue holds
    // only detached JSON-shaped questions, never GameView, events or controllers.
    private static final class Remote implements IRemote {
        final BlockingQueue<Map<String, Object>> questions = new LinkedBlockingQueue<>();
        final Map<String, Consumer<List<Object>>> replies = new HashMap<>();
        volatile ProtocolGuiGame gui;
        volatile ActorBoundary boundary;
        volatile Player actor;
        volatile boolean landSubmitted;
        volatile int deltas, blockingQuestions;

        synchronized void invalidate() {
            if (boundary != null) boundary.invalidate();
            replies.clear();
        }

        private synchronized void publish(String kind, List<?> choices, int min, int max,
                                          Consumer<List<Object>> handler) {
            Map<String, Object> question = boundary.offer(kind, choices, min, max);
            replies.clear();
            replies.put((String) question.get("request_id"), handler);
            questions.add(question);
        }

        synchronized void submit(Player caller, String request, List<String> tokens) {
            Consumer<List<Object>> reply = replies.get(request);
            if (reply == null) throw new IllegalArgumentException("No current callback");
            List<Object> nativeAnswer = boundary.answer(caller, request, tokens);
            replies.remove(request);
            reply.accept(nativeAnswer);
        }

        @Override
        @SuppressWarnings("unchecked")
        public void send(NetEvent event) {
            GuiGameEvent call = (GuiGameEvent) event;
            Object[] a = call.getObjects();
            switch (call.getMethod()) {
                case openView -> {
                    PlayerView owner = ((TrackableCollection<PlayerView>) a[0]).iterator().next();
                    actor = gui.getGameView().getGame().getPlayer(owner.getId());
                    boundary = new ActorBoundary(actor);
                }
                case applyDelta -> deltas++;
                case setSelection, finishGame -> invalidate();
                case updateButtons -> {
                    PlayerView owner = (PlayerView) a[0];
                    invalidate();
                    if (actor == null || owner == null || owner.getId() != actor.getId()) return;
                    IGameController controller = gui.getGameController(owner);
                    List<Object> choices = new ArrayList<>();
                    GameView view = gui.getGameView();
                    if (!landSubmitted && view.getPlayerTurn() != null &&
                            view.getPlayerTurn().equals(owner) &&
                            view.getPhase() == forge.game.phase.PhaseType.MAIN1) {
                        choices.addAll(owner.getHand());
                    }
                    if ((Boolean) a[3]) choices.add("ok");
                    if ((Boolean) a[4]) choices.add("cancel");
                    if (choices.isEmpty()) return;
                    publish("priority", choices, 1, 1, answer -> {
                        Object selected = answer.get(0);
                        if (selected instanceof CardView card) {
                            landSubmitted = true;
                            FThreads.invokeInEdtLater(() -> controller.selectCard(card, null, null));
                        } else if (selected.equals("ok")) {
                            FThreads.invokeInEdtLater(controller::selectButtonOk);
                        } else {
                            FThreads.invokeInEdtLater(controller::selectButtonCancel);
                        }
                    });
                }
                default -> { /* No raw state, logs, messages or events go to the client. */ }
            }
        }

        @Override
        public Object sendAndWait(IdentifiableNetEvent event) {
            GuiGameEvent call = (GuiGameEvent) event;
            Object[] a = call.getObjects();
            List<?> choices;
            int min = 1, max = 1;
            switch (call.getMethod()) {
                case getAbilityToPlay -> choices = (List<?>) a[1];
                case getChoices -> {
                    choices = (List<?>) a[3];
                    min = (Integer) a[1];
                    max = (Integer) a[2];
                    if (max < 0 || max > choices.size()) max = choices.size();
                }
                case confirm, showConfirmDialog -> choices = List.of(true, false);
                case showOptionDialog -> choices = List.of(a[4]);
                case showInputDialog -> choices = List.of(a[3]);
                default -> throw new IllegalArgumentException("Unimplemented native dialog: " + call.getMethod());
            }
            CompletableFuture<List<Object>> reply = new CompletableFuture<>();
            blockingQuestions++;
            publish(call.getMethod().name(), choices, min, max, reply::complete);
            try {
                List<Object> answer = reply.get(30, TimeUnit.SECONDS);
                return call.getMethod() == forge.gamemodes.net.ProtocolMethod.getChoices ? answer : answer.get(0);
            } catch (Exception error) {
                invalidate();
                throw new IllegalStateException("Native question did not receive a valid answer", error);
            }
        }
    }

    private Deck deck(String name, String card) {
        Deck deck = new Deck(name);
        deck.getMain().add(card, 40);
        return deck;
    }

    @SuppressWarnings("unchecked")
    private List<String> choose(Map<String, Object> question) {
        List<Map<String, Object>> options = (List<Map<String, Object>>) question.get("choices");
        int count = ((Number) question.get("min")).intValue();
        if (count == 0) count = Math.min(1, ((Number) question.get("max")).intValue());
        List<String> result = new ArrayList<>();
        if (question.get("kind").equals("priority")) {
            // Deliberately click a particular offered native card, not a raw card id.
            for (Map<String, Object> option : options) {
                if (option.get("display") instanceof Map<?, ?> display && display.containsKey("card_id")) {
                    return List.of((String) option.get("token"));
                }
            }
        }
        if (question.get("kind").equals("getAbilityToPlay")) {
            for (Map<String, Object> option : options) {
                Map<?, ?> display = (Map<?, ?>) option.get("display");
                if (!display.get("description").toString().toLowerCase().contains("cycling")) {
                    return List.of((String) option.get("token"));
                }
            }
        }
        for (Map<String, Object> option : options) {
            if (result.size() == count) break;
            result.add((String) option.get("token"));
        }
        return result;
    }

    @Test(dataProvider = "seats", timeOut = 120_000)
    @SuppressWarnings("unchecked")
    public void tokenAnswerPlaysALandThroughTheRealHumanController(int seat) throws Exception {
        FModel.getPreferences().setPref(FPref.UI_SHOW_ACTIONABLE_HIGHLIGHTS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        MyRandom.setRandom(new Random(7));
        Remote remote = new Remote();
        ProtocolGuiGame gui = new ProtocolGuiGame(remote);
        remote.gui = gui;
        RegisteredPlayer human = new RegisteredPlayer(deck("Human", "Drifting Meadow"))
                .setPlayer(new LobbyPlayerHuman("Human"));
        RegisteredPlayer ai = new RegisteredPlayer(deck("AI", "Forest"))
                .setPlayer(GamePlayerUtil.createAiPlayer("AI"));
        List<RegisteredPlayer> players = seat == 0 ? List.of(human, ai) : List.of(ai, human);
        HostedMatch match = new HostedMatch();
        match.startMatch(GameType.Constructed, null, players, human, gui);
        boolean invalidChecked = false, landed = false;
        int answered = 0;
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(70);
        try {
            while (System.nanoTime() < deadline) {
                if (remote.actor != null && remote.actor.getCardsIn(ZoneType.Battlefield).size() == 1) {
                    landed = true;
                    break;
                }
                Map<String, Object> question = remote.questions.poll(1, TimeUnit.SECONDS);
                if (question == null) continue;
                List<String> answer = choose(question);
                String request = (String) question.get("request_id");
                if (!invalidChecked && question.get("kind").equals("priority")) {
                    Game game = gui.getGameView().getGame();
                    Player other = game.getPlayers().stream().filter(p -> p != remote.actor).findFirst().orElseThrow();
                    String before = JSON.toJson(remote.boundary.snapshot(gui.getGameView()));
                    Assert.expectThrows(IllegalArgumentException.class, () -> remote.submit(other, request, answer));
                    Assert.expectThrows(IllegalArgumentException.class,
                            () -> remote.submit(remote.actor, request, List.of("unoffered-token")));
                    Assert.assertEquals(JSON.toJson(remote.boundary.snapshot(gui.getGameView())), before);
                    invalidChecked = true;
                }
                try {
                    remote.submit(remote.actor, request, answer);
                    answered++;
                } catch (IllegalArgumentException superseded) {
                    // A native replacement prompt can legitimately supersede a queued button update.
                }
            }
            Assert.assertTrue(landed, "The chosen native land must really enter the battlefield");
            Assert.assertTrue(invalidChecked);
            Assert.assertTrue(remote.deltas >= 2);
            Assert.assertTrue(remote.blockingQuestions >= 1, "The human's actual land ability choice must cross the same boundary");
            Map<String, Object> state = remote.boundary.snapshot(gui.getGameView());
            for (Map<String, Object> player : (List<Map<String, Object>>) state.get("players")) {
                Map<String, Object> zones = (Map<String, Object>) player.get("zones");
                Map<?, ?> library = (Map<?, ?>) zones.get("Library");
                Assert.assertEquals(library.get("visible_cards"), List.of());
                if (((Number) player.get("player_id")).intValue() != remote.actor.getId()) {
                    Assert.assertEquals(((Map<?, ?>) zones.get("Hand")).get("visible_cards"), List.of());
                }
            }
            System.out.println("@@HUMAN_BOUNDARY " + JSON.toJson(Map.of("seat", seat, "land_really_played", true,
                    "answered", answered, "deltas", remote.deltas, "blocking_choices", remote.blockingQuestions,
                    "wrong_actor_and_forged_rejected", true, "private_zones_hidden", true)));
        } finally {
            // Harness termination after the boundary assertion, not a natural-game certificate.
            remote.invalidate();
            if (remote.actor != null) FThreads.invokeInEdtLater(() -> gui.getGameController(remote.actor.getView()).concede());
            long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
            while (match.getGameView() != null && !match.getGameView().isGameOver() && System.nanoTime() < end) Thread.sleep(50);
        }
        Assert.assertTrue(match.getGameView() == null || match.getGameView().isGameOver(), "Harness ended without a stranded game");
    }
}
