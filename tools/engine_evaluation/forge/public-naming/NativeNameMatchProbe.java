// SPDX-License-Identifier: GPL-3.0-or-later
// Original MTG Deck Testing Lab probe, using Card-Forge's native engine.
// Upstream work: Forge Team and Card-Forge contributors,
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Original upstream headers/licenses remain unchanged. This probe does not
// manufacture winners, simulate a timeout draw, or touch the application's DB.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.common.eventbus.Subscribe;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.ai.simulation.FlatMonteCarloStats;
import forge.GuiDesktop;
import forge.deck.CardPool;
import forge.deck.Deck;
import forge.deck.DeckSection;
import forge.deck.io.DeckSerializer;
import forge.game.Game;
import forge.game.GameLogEntry;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.event.GameEventPlayerPriority;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.gui.GuiBase;
import forge.item.PaperCard;
import forge.model.FModel;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.util.MyRandom;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;

public final class NativeNameMatchProbe {
    private static final Gson JSON = new Gson();

    private static void emit(Map<String, Object> row) {
        System.out.println("@@MTG_PROBE_JSON " + JSON.toJson(row));
        System.out.flush();
    }

    static void configureSearch(Game game, boolean enabled) {
        game.AI_FLAT_MONTE_CARLO = enabled;
        game.AI_FLAT_MONTE_CARLO_MAX = false;
        game.AI_FLAT_MONTE_CARLO_LITE = false;
        game.AI_TIMEOUT = 5;
        FlatMonteCarloStats.reset();
    }

    private static Map<String, Integer> pool(CardPool cards) {
        Map<String, Integer> result = new TreeMap<>();
        for (Map.Entry<PaperCard, Integer> entry : cards) {
            result.merge(entry.getKey().getName(), entry.getValue(), Integer::sum);
        }
        return result;
    }

    private static Map<String, Integer> expected(JsonObject row) {
        Map<String, Integer> result = new TreeMap<>();
        row.entrySet().forEach(entry -> result.put(entry.getKey(), entry.getValue().getAsInt()));
        return result;
    }

    private static Map<String, Integer> inventory(Deck deck) {
        Map<String, Integer> result = new TreeMap<>(pool(deck.getMain()));
        pool(deck.getOrCreate(DeckSection.Sideboard)).forEach(
                (name, count) -> result.merge(name, count, Integer::sum));
        return result;
    }

    private static List<Map<String, Object>> decks(List<RegisteredPlayer> players) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (RegisteredPlayer player : players) {
            result.add(Map.of("name", player.getPlayer().getName(),
                    "main", pool(player.getDeck().getMain()),
                    "sideboard", pool(player.getDeck().getOrCreate(DeckSection.Sideboard))));
        }
        return result;
    }

    public static void main(String[] args) {
        int exit = 1;
        try {
            if (args.length != 1) throw new IllegalArgumentException("Expected owned prototype directory");
            Path root = Path.of(args[0]);
            JsonObject spec = JsonParser.parseString(Files.readString(root.resolve("SPEC.json"))).getAsJsonObject();
            if (!spec.get("open_decklists").getAsBoolean()) {
                throw new IllegalArgumentException("This diagnostic requires explicitly public deck lists");
            }
            System.setProperty("java.awt.headless", "true");
            GuiBase.setInterface(new GuiDesktop());
            FModel.initialize(null, null);
            FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
            MyRandom.setRandom(new Random(spec.get("seed").getAsLong()));
            boolean corrected = spec.get("use_public_name_controller").getAsBoolean();
            boolean search = spec.has("flat_monte_carlo") && spec.get("flat_monte_carlo").getAsBoolean();
            Map<Integer,Map<String,Integer>> publicDecks = new TreeMap<>();
            for (int i=0;i<2;i++) {
                JsonObject row=spec.getAsJsonArray("decks").get(i).getAsJsonObject();
                Map<String,Integer> cards=new TreeMap<>(expected(row.getAsJsonObject("main")));
                expected(row.getAsJsonObject("sideboard")).forEach((name,n) -> cards.merge(name,n,Integer::sum));
                publicDecks.put(i,Map.copyOf(cards));
            }
            List<RegisteredPlayer> players = new ArrayList<>();
            List<Map<String, Integer>> originals = new ArrayList<>();
            for (int i = 0; i < 2; i++) {
                JsonObject row = spec.getAsJsonArray("decks").get(i).getAsJsonObject();
                Deck deck = DeckSerializer.fromFile(root.resolve("decks").resolve(row.get("file").getAsString()).toFile());
                if (deck == null || !pool(deck.getMain()).equals(expected(row.getAsJsonObject("main")))
                        || !pool(deck.getOrCreate(DeckSection.Sideboard)).equals(expected(row.getAsJsonObject("sideboard")))) {
                    throw new IllegalStateException("Native deck import dropped or changed a card");
                }
                originals.add(inventory(deck));
                LobbyPlayerAi lobby=new LobbyPlayerAi(row.get("name").getAsString(),null) {
                    @Override public Player createIngamePlayer(Game game,int id) {
                        Player player=new Player(getName(),game,id);
                        player.setFirstController(corrected ? new PublicNameController(game,player,this,publicDecks) :
                                new PlayerControllerAi(game,player,this));
                        return player;
                    }
                };
                lobby.setAiProfile("Default");
                players.add(new RegisteredPlayer(deck).setPlayer(lobby));
            }
            GameRules rules = new GameRules(GameType.Constructed);
            rules.setAppliedVariants(EnumSet.of(GameType.Constructed));
            rules.setGamesPerMatch(3);
            rules.setPlayForAnte(false);
            rules.setAISideboardingEnabled(true);
            rules.setAllowCheatShuffle(false);
            Match match = new Match(rules, players, "Isolated native BO3 probe");
            emit(Map.of("kind", "match_started", "decks", decks(players), "seed", spec.get("seed").getAsLong(),
                        "open_decklists", true, "AI", search ? "Default Flat-MC" : "Default heuristic; MC off", "corrected_naming", corrected,
                        "filtered_hands",FModel.getPreferences().getPrefBoolean(FPref.FILTERED_HANDS)));
            int games = 0;
            AtomicInteger totalObservations=new AtomicInteger();
            try (PrintWriter logs = new PrintWriter(Files.newBufferedWriter(
                    root.resolve("game-logs.private.jsonl"), StandardCharsets.UTF_8));
                 PrintWriter observations = new PrintWriter(Files.newBufferedWriter(
                    root.resolve("actor-observations.private.jsonl"), StandardCharsets.UTF_8))) {
                while (!match.isMatchOver() && games < spec.get("max_natural_games").getAsInt()) {
                    final int index = games;
                    Game game = match.createGame();
                    game.setNoGUIUser();
                    configureSearch(game,search);
                    List<String> observationErrors=new ArrayList<>();
                    game.subscribeToEvents(new Object() {
                        @Subscribe public void priority(GameEventPlayerPriority event) {
                            if (event.priority()==null) return;
                            try {
                                Player actor=game.getPlayer(event.priority().getId());
                                observations.println(JSON.toJson(Map.of("game",index,"event","native_priority",
                                        "actor",actor.getId(),"phase",event.phase()==null?"":event.phase().name(),
                                        "view",new ActorBoundary(actor).snapshot(game.getView()))));
                                totalObservations.incrementAndGet();
                            } catch (Throwable error) {
                                if (observationErrors.size()<20) observationErrors.add(error.getClass().getName()+":"+error.getMessage());
                            }
                        }
                    });
                    long started = System.nanoTime();
                    match.startGame(game, () -> emit(Map.of("kind", "native_prepared_game", "game", index,
                                                            "decks", decks(players))));
                    if (!game.isGameOver() || game.getOutcome() == null) {
                        throw new IllegalStateException("Native game returned without a terminal outcome");
                    }
                    for (int i = 0; i < players.size(); i++) {
                        if (!inventory(players.get(i).getDeck()).equals(originals.get(i))) {
                            throw new IllegalStateException("Native sideboarding changed combined inventory");
                        }
                    }
                    List<GameLogEntry> entries = new ArrayList<>(game.getGameLog().getLogEntries(null));
                    Collections.reverse(entries);
                    for (GameLogEntry entry : entries) {
                        logs.println(JSON.toJson(Map.of("game", index, "type", entry.type().name(),
                                                       "message", entry.message())));
                    }
                    logs.flush();
                    observations.flush();
                    if (!observationErrors.isEmpty() || observations.checkError() || logs.checkError()) {
                        throw new IllegalStateException("Native observer capture incomplete: "+observationErrors);
                    }
                    emit(Map.of("kind","native_search_stats","game",index,"enabled",search,
                            "decisions",FlatMonteCarloStats.getDecisions(),"rollouts",FlatMonteCarloStats.getRollouts(),
                            "failures",FlatMonteCarloStats.getFailureCount(),
                            "unsimulatable_cards",FlatMonteCarloStats.getUnsimulatableCardCount(),
                            "p95_ms",FlatMonteCarloStats.getPercentileMillis(95),
                            "summary",FlatMonteCarloStats.summary()));
                    emit(Map.of("kind", "native_game_complete", "game", index,
                            "seconds", (System.nanoTime()-started)/1e9,
                            "turns", game.getOutcome().getLastTurnNumber(),
                            "draw", game.getOutcome().isDraw(),
                            "win_condition", game.getOutcome().getWinCondition().name(),
                            "outcomes", game.getOutcome().getOutcomeStrings(),
                            "decks", decks(players), "log_entries", entries.size()));
                    games++;
                }
            }
            if (!match.isMatchOver()) throw new IllegalStateException("Finite game cap, not a completed match");
            emit(Map.of("kind", "native_match_complete", "games", games,
                        "games_to_win", rules.getGamesToWinMatch(), "inventory_conserved", true,
                        "actor_observations",totalObservations.get()));
            exit = 0;
        } catch (Throwable error) {
            error.printStackTrace();
            emit(Map.of("kind", "probe_error", "exception", error.getClass().getName(),
                        "message", String.valueOf(error.getMessage()), "match_complete", false));
        }
        System.exit(exit);
    }
}
