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
import forge.game.player.RegisteredPlayer;
import forge.gui.GuiBase;
import forge.item.PaperCard;
import forge.model.FModel;
import forge.player.GamePlayerUtil;
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

public final class NativeMatchProbe {
    private static final Gson JSON = new Gson();

    private static void emit(Map<String, Object> row) {
        System.out.println("@@MTG_PROBE_JSON " + JSON.toJson(row));
        System.out.flush();
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
            MyRandom.setRandom(new Random(spec.get("seed").getAsLong()));
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
                players.add(new RegisteredPlayer(deck).setPlayer(
                        GamePlayerUtil.createAiPlayer(row.get("name").getAsString(), i, "Default")));
            }
            GameRules rules = new GameRules(GameType.Constructed);
            rules.setAppliedVariants(EnumSet.of(GameType.Constructed));
            rules.setGamesPerMatch(3);
            rules.setPlayForAnte(false);
            rules.setAISideboardingEnabled(true);
            rules.setAllowCheatShuffle(false);
            Match match = new Match(rules, players, "Isolated native BO3 probe");
            emit(Map.of("kind", "match_started", "decks", decks(players), "seed", spec.get("seed").getAsLong(),
                        "open_decklists", true, "AI", "Default heuristic; MC off"));
            int games = 0;
            try (PrintWriter logs = new PrintWriter(Files.newBufferedWriter(
                    root.resolve("game-logs.private.jsonl"), StandardCharsets.UTF_8))) {
                while (!match.isMatchOver() && games < spec.get("max_natural_games").getAsInt()) {
                    final int index = games;
                    Game game = match.createGame();
                    game.setNoGUIUser();
                    game.AI_FLAT_MONTE_CARLO = false;
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
                        "games_to_win", rules.getGamesToWinMatch(), "inventory_conserved", true));
            exit = 0;
        } catch (Throwable error) {
            error.printStackTrace();
            emit(Map.of("kind", "probe_error", "exception", error.getClass().getName(),
                        "message", String.valueOf(error.getMessage()), "match_complete", false));
        }
        System.exit(exit);
    }
}
