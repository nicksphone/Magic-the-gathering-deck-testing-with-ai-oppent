// SPDX-License-Identifier: GPL-3.0-or-later
// Original boundary tests using the Forge Team/Card-Forge contributors' engine.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.simulation.SimulationTest;
import forge.game.Game;
import forge.game.card.Card;
import forge.game.player.Player;
import forge.game.zone.ZoneType;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.testng.Assert;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class ActorBoundaryTest extends SimulationTest {
    private static final Gson JSON = new Gson();

    @DataProvider(name = "seats")
    public Object[][] seats() { return new Object[][] {{0}, {1}}; }

    private Game position(int seat) {
        Game game = initAndCreateGame();
        Player actor = game.getPlayers().get(seat);
        Player opponent = game.getPlayers().get(1-seat);
        addCardToZone("Island", actor, ZoneType.Hand);
        addCardToZone("Brainstorm", opponent, ZoneType.Hand);
        addCardToZone("Lightning Bolt", opponent, ZoneType.Hand);
        addCardToZone("Counterspell", actor, ZoneType.Library);
        addCardToZone("Cloudblazer", actor, ZoneType.Library);
        addCardToZone("Progenitus", opponent, ZoneType.Library);
        return game;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> zone(Map<String, Object> snapshot, Player player, ZoneType zone) {
        Assert.assertTrue(snapshot.get("players") instanceof List, "An actor-scoped player list is required");
        for (Object entry : (List<?>) snapshot.get("players")) {
            Map<String, Object> row = (Map<String, Object>) entry;
            if (((Number) row.get("player_id")).intValue() == player.getId()) {
                return (Map<String, Object>) ((Map<?, ?>) row.get("zones")).get(zone.name());
            }
        }
        throw new AssertionError("Missing actual player");
    }

    private void plainJson(Object value) {
        if (value == null || value instanceof String || value instanceof Boolean || value instanceof Number) return;
        if (value instanceof Map<?, ?> map) {
            map.forEach((key, item) -> { Assert.assertTrue(key instanceof String); plainJson(item); });
            return;
        }
        if (value instanceof List<?> list) { list.forEach(this::plainJson); return; }
        Assert.fail("A native object escaped into the browser payload: " + value.getClass().getName());
    }

    @Test(dataProvider = "seats")
    public void hiddenHandsAndLibrariesContainCountsNotIdentities(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> view = boundary.snapshot(game.getView());
        Assert.assertEquals(zone(view, actor, ZoneType.Hand).get("count"), 1);
        Assert.assertEquals(zone(view, opponent, ZoneType.Hand).get("count"), 2);
        Assert.assertEquals(((List<?>) zone(view, opponent, ZoneType.Hand).get("visible_cards")).size(), 0);
        Assert.assertEquals(((List<?>) zone(view, actor, ZoneType.Library).get("visible_cards")).size(), 0);
        String json = JSON.toJson(view);
        Assert.assertTrue(json.contains("Island"));
        for (String hidden : List.of("Brainstorm", "Lightning Bolt", "Counterspell", "Cloudblazer", "Progenitus")) {
            Assert.assertFalse(json.contains(hidden), "Hidden identity leaked: " + hidden);
        }
        Assert.assertEquals(opponent.getView().getHand().get(0).getName(), "Brainstorm", "Raw native view really holds the secret");
        plainJson(view);
        String before = json;
        Card secret = opponent.getCardsIn(ZoneType.Hand).get(0);
        game.getAction().moveToHand(secret, null);
        Card top = actor.getCardsIn(ZoneType.Library).get(0);
        game.getAction().moveToLibrary(top, 1, null);
        Assert.assertEquals(JSON.toJson(boundary.snapshot(game.getView())), before,
                "Hidden ordering changes must not change actor-visible bytes");
    }

    @Test(dataProvider = "seats")
    public void permissionSnapshotsAreDetachedAndRevocationHidesAgain(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Card secret = opponent.getCardsIn(ZoneType.Hand).get(0);
        secret.addMayLookTemp(actor);
        Map<String, Object> allowed = boundary.snapshot(game.getView());
        Assert.assertTrue(JSON.toJson(allowed).contains("Brainstorm"), "An actual native viewing grant must work");
        secret.removeMayLookTemp(actor);
        Assert.assertFalse(JSON.toJson(boundary.snapshot(game.getView())).contains("Brainstorm"));
        Assert.assertTrue(JSON.toJson(allowed).contains("Brainstorm"), "Previously delivered authorized data is a scalar snapshot");
        plainJson(allowed);
    }

    @Test(dataProvider = "seats")
    public void facedownBattlefieldShowsShellNotOpposingOriginal(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        Card hidden = addCard("Willbender", opponent);
        Assert.assertTrue(hidden.turnFaceDown(true));
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> shell = boundary.snapshot(game.getView());
        Assert.assertEquals(((List<?>) zone(shell, opponent, ZoneType.Battlefield).get("visible_cards")).size(), 1);
        Assert.assertFalse(JSON.toJson(shell).contains("Willbender"));
        Assert.assertTrue(JSON.toJson(new ActorBoundary(opponent).snapshot(game.getView())).contains("Willbender"),
                "The actual controller can inspect their own face-down card");
        hidden.addMayLookTemp(actor);
        Assert.assertTrue(JSON.toJson(boundary.snapshot(game.getView())).contains("Willbender"));
    }

    @Test(dataProvider = "seats")
    public void facedownExileRemainsHiddenWithoutAnExplicitViewingGrant(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        Card hidden = addCardToZone("Doomskar", opponent, ZoneType.Exile);
        hidden.turnFaceDown(true);
        ActorBoundary boundary = new ActorBoundary(actor);
        Assert.assertFalse(JSON.toJson(boundary.snapshot(game.getView())).contains("Doomskar"));
        hidden.addMayLookTemp(actor);
        Assert.assertTrue(JSON.toJson(boundary.snapshot(game.getView())).contains("Doomskar"));
    }

    @Test(dataProvider = "seats")
    public void foreignGamesAndMissingActorsRejectBeforeProducingViews(int seat) {
        Game game = position(seat);
        ActorBoundary boundary = new ActorBoundary(game.getPlayers().get(seat));
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.snapshot(initAndCreateGame().getView()));
        Assert.expectThrows(NullPointerException.class, () -> new ActorBoundary(null));
    }

    @SuppressWarnings("unchecked")
    private List<String> tokens(Map<String, Object> question) {
        Assert.assertTrue(question.get("choices") instanceof List, "Native options require opaque choice tokens");
        List<String> result = new ArrayList<>();
        for (Object row : (List<?>) question.get("choices")) result.add((String) ((Map<String, Object>) row).get("token"));
        return result;
    }

    @Test(dataProvider = "seats")
    public void forgedStaleDuplicateAndWrongActorAnswersDoNotConsumeTheRealQuestion(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> question = boundary.offer("choose", List.of("first", "second"), 1, 1);
        String id = (String) question.get("request_id");
        List<String> ids = tokens(question);
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.answer(opponent, id, List.of(ids.get(1))));
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.answer(actor, "stale", List.of(ids.get(1))));
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.answer(actor, id, List.of("forged")));
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.answer(actor, id, List.of()));
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.answer(actor, id, List.of(ids.get(0), ids.get(0))));
        Assert.assertEquals(boundary.answer(actor, id, List.of(ids.get(1))), List.of("second"));
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.answer(actor, id, List.of(ids.get(1))));
        plainJson(question);
    }

    @Test(dataProvider = "seats")
    public void optionalEmptyAnswersAndOrderedMultipleAnswersRetainNativeValues(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> optional = boundary.offer("optional", List.of("a"), 0, 1);
        tokens(optional);
        Assert.assertEquals(boundary.answer(actor, (String) optional.get("request_id"), List.of()), List.of());
        Map<String, Object> multiple = boundary.offer("order", List.of("a", "b"), 2, 2);
        List<String> ids = tokens(multiple);
        Assert.assertEquals(boundary.answer(actor, (String) multiple.get("request_id"), List.of(ids.get(1), ids.get(0))), List.of("b", "a"));
    }

    @Test(dataProvider = "seats")
    public void hiddenNativeChoiceValuesAreNotSerializedAndUnknownTypesFailClosed(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Object secret = opponent.getCardsIn(ZoneType.Hand).get(0).getView();
        Map<String, Object> question = boundary.offer("choose unseen card", List.of(secret), 1, 1);
        Assert.assertFalse(JSON.toJson(question).contains("Brainstorm"));
        plainJson(question);
        List<String> ids = tokens(question);
        Assert.expectThrows(IllegalArgumentException.class, () -> boundary.offer("unsafe", List.of(new Object()), 1, 1));
        Assert.assertSame(boundary.answer(actor, (String) question.get("request_id"), ids).get(0), secret);
    }

    @Test(dataProvider = "seats")
    public void nullTokensRejectAsInvalidInputAndLeaveTheCurrentQuestionUsable(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> question = boundary.offer("choose", List.of("first"), 1, 1);
        List<String> ids = tokens(question);
        List<String> malformed = new ArrayList<>();
        malformed.add(null);
        Assert.expectThrows(IllegalArgumentException.class,
                () -> boundary.answer(actor, (String) question.get("request_id"), malformed));
        Assert.assertEquals(boundary.answer(actor, (String) question.get("request_id"), ids), List.of("first"));
    }

    @Test(dataProvider = "seats")
    public void unclassifiedCardsRejectAndReplacementQuestionsInvalidateOldTokens(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> first = boundary.offer("choose", List.of("old"), 1, 1);
        List<String> oldIds = tokens(first);
        Card unclassified = createCard("Lightning Bolt", actor);
        Assert.expectThrows(IllegalArgumentException.class,
                () -> boundary.offer("unsafe", List.of(unclassified.getView()), 1, 1));
        Map<String, Object> next = boundary.offer("choose", List.of("new"), 1, 1);
        List<String> ids = tokens(next);
        Assert.expectThrows(IllegalArgumentException.class,
                () -> boundary.answer(actor, (String) first.get("request_id"), oldIds));
        Assert.assertEquals(boundary.answer(actor, (String) next.get("request_id"), ids), List.of("new"));
    }

    @Test(dataProvider = "seats")
    public void ownerOnlyPermissionDoesNotLeakThroughVirtualPlayableZoneCounts(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1-seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        String before = JSON.toJson(boundary.snapshot(game.getView()));
        int virtualBefore = opponent.getView().getZoneSize(ZoneType.Flashback);
        Card secret = opponent.getCardsIn(ZoneType.Library).get(0);
        secret.addMayLookTemp(opponent);
        opponent.updateZoneForView(opponent.getZone(ZoneType.Library));
        Assert.assertEquals(opponent.getView().getZoneSize(ZoneType.Flashback), virtualBefore + 1,
                "The actual native virtual collection depends on a private permission");
        Assert.assertEquals(JSON.toJson(boundary.snapshot(game.getView())), before,
                "An opponent-only permission must not alter actor-visible bytes");
    }

    @Test(dataProvider = "seats")
    @SuppressWarnings("unchecked")
    public void snapshotNeverExportsVirtualOrUnsupportedVariantDecks(int seat) {
        Game game = position(seat);
        Map<String, Object> view = new ActorBoundary(game.getPlayers().get(seat)).snapshot(game.getView());
        for (Map<String, Object> player : (List<Map<String, Object>>) view.get("players")) {
            Map<String, Object> zones = (Map<String, Object>) player.get("zones");
            Assert.assertEquals(zones.keySet(), java.util.Set.of("Hand", "Library", "Graveyard",
                    "Battlefield", "Exile", "Command", "Sideboard"));
        }
    }

    @Test(dataProvider = "seats")
    public void invalidationRejectsAFormerlyValidAnswerBeforeItCanDispatch(int seat) {
        Game game = position(seat);
        Player actor = game.getPlayers().get(seat);
        ActorBoundary boundary = new ActorBoundary(actor);
        Map<String, Object> question = boundary.offer("choose", List.of("old"), 1, 1);
        List<String> ids = tokens(question);
        boundary.invalidate();
        Assert.expectThrows(IllegalArgumentException.class,
                () -> boundary.answer(actor, (String) question.get("request_id"), ids));
        Map<String, Object> replacement = boundary.offer("choose", List.of("new"), 1, 1);
        Assert.assertEquals(boundary.answer(actor, (String) replacement.get("request_id"), tokens(replacement)), List.of("new"));
    }
}
