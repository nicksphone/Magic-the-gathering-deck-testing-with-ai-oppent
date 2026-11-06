// SPDX-License-Identifier: GPL-3.0-or-later
// Original observer unit using the Forge Team/Card-Forge engine and canonical cards.
// Engine pin inherited: 61e9442c433711a82258daca3236f936a1d6f70e.
// Constructor/pose adapted from retained NativeSaveAudit.java, not a natural game.
// Preserve upstream notices and the accompanying Forge GPL LICENSE.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import forge.GuiDesktop;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.ability.AbilityKey;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.zone.PlayerZone;
import forge.game.zone.ZoneType;
import forge.gui.GuiBase;
import forge.item.PaperCard;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import forge.util.ThreadUtil;
import java.io.PrintWriter;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

public final class NativeObserverUnit {
    private static final Gson JSON = new Gson();
    private static final List<ZoneType> ZONES = List.of(ZoneType.Hand, ZoneType.Library,
            ZoneType.Battlefield, ZoneType.Graveyard, ZoneType.Exile, ZoneType.Command, ZoneType.Sideboard);

    private static void require(boolean ok, String message) {
        if (!ok) throw new IllegalStateException(message);
    }

    private static Game fixture() {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck(i == 0 ? "Canonical Bolt 60" : "Canonical Plains 60");
            deck.getMain().add(i == 0 ? "Mountain" : "Plains", i == 0 ? 56 : 60);
            if (i == 0) deck.getMain().add("Lightning Bolt", 4);
            require(deck.getMain().countAll() == 60, "Exactly 60 registered cards per deck");
            LobbyPlayerAi lobby = new LobbyPlayerAi("Unit seat " + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setGamesPerMatch(1);
        rules.setAllowCheatShuffle(false);
        rules.setPlayForAnte(false);
        Game game = new Match(rules, registered, "NONNATURAL OBSERVER UNIT ONLY").createGame();
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        for (int i = 0; i < 2; i++) {
            Player player = game.getRegisteredPlayers().get(i);
            player.setLife(i == 0 ? 20 : 3, null); // Declared constructor pose, never a restored outcome.
            for (PaperCard paper : registered.get(i).getDeck().getMain().toFlatList()) {
                game.getAction().moveToLibrary(Card.fromPaperCard(paper, player), -1, null);
            }
            require(player.getAllCards().size() == 60, "All physical cards instantiated");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, game.getRegisteredPlayers().get(0), 2);
        return game;
    }

    private static JsonObject observe(NativeHumanWorker worker, Method method, Game game) throws Exception {
        return JSON.toJsonTree(method.invoke(worker, game)).getAsJsonObject();
    }

    private static Set<Integer> observedIds(JsonObject state) {
        Set<Integer> ids = new HashSet<>();
        for (var player : state.getAsJsonArray("players")) {
            for (var zone : player.getAsJsonObject().getAsJsonObject("zones").entrySet()) {
                for (var card : zone.getValue().getAsJsonArray()) ids.add(card.getAsJsonArray().get(0).getAsInt());
            }
        }
        for (var spell : state.getAsJsonArray("stack")) ids.add(spell.getAsJsonObject().get("source").getAsInt());
        return ids;
    }

    private static void conserve(JsonObject state, Set<Integer> registered) {
        require(registered.size() == 120, "Registry must contain 120 distinct physical IDs");
        require(observedIds(state).containsAll(registered), "Registered physical card lost");
    }

    private static void write(Path root, String name, Object value) throws Exception {
        Files.writeString(root.resolve(name), JSON.toJson(value) + "\n");
    }

    private static void unit(Path root) throws Exception {
        Game game = fixture();
        Player caster = game.getRegisteredPlayers().get(0), loser = game.getRegisteredPlayers().get(1);
        Set<Integer> registry = new HashSet<>();
        for (Player player : game.getRegisteredPlayers()) for (Card card : player.getAllCards()) {
            require(registry.add(card.getId()), "Duplicate registered physical ID");
        }
        NativeHumanWorker worker = new NativeHumanWorker(new PrintWriter(System.out, true));
        Method method = NativeHumanWorker.class.getDeclaredMethod("nativeState", Game.class);
        method.setAccessible(true); // Read-only invocation of the actual private production observer.
        JsonObject opening = observe(worker, method, game);
        conserve(opening, registry);
        write(root, "opening.json", opening);

        Map<ZoneType, PlayerZone> originalZones = new EnumMap<>(ZoneType.class);
        Map<ZoneType, List<Card>> originalCards = new EnumMap<>(ZoneType.class);
        for (ZoneType zone : ZONES) {
            originalZones.put(zone, loser.getZone(zone));
            List<Card> cards = new ArrayList<>();
            for (Card card : loser.getCardsIn(zone)) cards.add(card);
            originalCards.put(zone, cards);
        }
        Card land = caster.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals("Mountain")).findFirst().orElseThrow();
        Card bolt = caster.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals("Lightning Bolt")).findFirst().orElseThrow();
        land = game.getAction().moveToPlay(land, null, AbilityKey.newMap());
        bolt = game.getAction().moveToHand(bolt, null);
        require(!land.isTapped() && caster.getManaPool().isEmpty(), "No free/preloaded mana");
        var spell = bolt.getFirstSpellAbility();
        spell.setActivatingPlayer(caster);
        spell.resetTargets();
        spell.getTargets().add(loser);
        require(ComputerUtil.playStack(spell, caster, game), "Native canonical payment/play accepted");
        require(game.getStack().size() == 1 && land.isTapped() && loser.getLife() == 3 &&
                spell.getHostCard().getId() == bolt.getId() && spell.getHostCard().isInZone(ZoneType.Stack),
                "Real paid pending physical Bolt before damage");
        JsonObject pending = observe(worker, method, game);
        conserve(pending, registry);
        write(root, "pending.json", pending);
        game.getStack().resolveStack();
        game.getAction().checkGameOverCondition(); // Actual native life-loss/SBA path, not manual elimination.
        require(game.isGameOver() && loser.getLife() == 0, "Real Bolt resolution must end the duel");
        require(game.getPlayers().size() == 1 && game.getRegisteredPlayers().size() == 2 &&
                game.getLostPlayers().size() == 1, "active=1, registered=2, lost=1");
        require(game.getRegisteredPlayers().get(1) == loser && game.getLostPlayers().get(0) == loser,
                "Same native losing Player retained, not a registration/deck reconstruction");
        require(caster.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == spell.getHostCard().getId()),
                "Resolved physical Bolt in graveyard");
        for (ZoneType zone : ZONES) {
            require(loser.getZone(zone) == originalZones.get(zone), "Same native PlayerZone reference");
            List<Card> before = originalCards.get(zone);
            require(loser.getCardsIn(zone).size() == before.size(), "Losing zone count retained");
            for (int i = 0; i < before.size(); i++) require(loser.getZone(zone).get(i) == before.get(i),
                    "Same native losing Card references and order retained");
        }
        JsonObject after = observe(worker, method, game);
        conserve(after, registry);
        require(after.getAsJsonArray("players").size() == 2 && observedIds(after).size() == 120,
                "Actual observer must include all 120 registered physical cards after loss");
        require(after.equals(observe(worker, method, game)), "Observer must not mutate native observations");
        write(root, "after-loss.json", after);

        // Legacy getter control: project actual observed rows to the actual active Player IDs.
        // This is explicitly a control observation, not a restored native state or another observer implementation.
        Set<Integer> activeIds = new HashSet<>();
        Set<Integer> actualActiveCards = new HashSet<>();
        for (Player player : game.getPlayers()) {
            activeIds.add(player.getId());
            for (Card card : player.getAllCards()) actualActiveCards.add(card.getId());
        }
        JsonObject oldScope = after.deepCopy();
        JsonArray activeRows = new JsonArray();
        for (var row : after.getAsJsonArray("players")) if (activeIds.contains(row.getAsJsonObject().get("id").getAsInt())) activeRows.add(row.deepCopy());
        oldScope.add("players", activeRows);
        require(actualActiveCards.size() == 60 && observedIds(oldScope).equals(actualActiveCards),
                "Actual old active-only getter scope observes 60, not 120");
        write(root, "old-active-scope-control.json", oldScope);
        JsonObject missing = after.deepCopy();
        missing.getAsJsonArray("players").get(1).getAsJsonObject().getAsJsonObject("zones")
                .getAsJsonArray("Library").remove(0); // Deliberate missing OBSERVATION only; never remove a native card.
        require(observedIds(missing).size() == 119, "Negative observation removes exactly one physical ID");
        boolean rejected = false;
        try { conserve(missing, registry); } catch (IllegalStateException expected) { rejected = true; }
        require(rejected, "Missing-observation negative must still fail conservation");
        write(root, "missing-observation-control.json", missing);
        write(root, "UNIT.json", Map.of("status", "PASS", "scope", "TRUSTED_NONNATURAL_OBSERVER_UNIT_ONLY",
                "actual_private_observer_invoked", true, "active_players", 1, "registered_players", 2,
                "same_player_and_zone_and_card_references", true, "registered_physical_ids", 120,
                "legacy_active_scope_ids", 60, "negative_observation_ids", 119, "negative_rejected", rejected));
    }

    public static void main(String[] args) {
        int exit = 1;
        try {
            require(args.length == 1, "Expected owned observer-unit output directory");
            GuiBase.setInterface(new GuiDesktop());
            FModel.initialize(null, null);
            FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
            FModel.getPreferences().setPref(FPref.UI_ENABLE_SOUNDS, false);
            FModel.getPreferences().setPref(FPref.UI_ENABLE_MUSIC, false);
            MyRandom.setRandom(new Random(2026110507L));
            CompletableFuture<Void> done = new CompletableFuture<>();
            ThreadUtil.invokeInGameThread(() -> {
                try { unit(Path.of(args[0])); done.complete(null); }
                catch (Throwable error) { done.completeExceptionally(error); }
            });
            done.get(45, TimeUnit.SECONDS);
            exit = 0;
        } catch (Throwable error) { error.printStackTrace(System.err); }
        System.exit(exit);
    }
}
