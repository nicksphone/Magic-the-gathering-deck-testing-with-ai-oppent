// SPDX-License-Identifier: GPL-3.0-or-later
// Original MTG Deck Testing Lab compatibility fixture, using the Forge Team and
// Card-Forge contributors' unchanged native engine and canonical card database.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Preserve upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.GuiDesktop;
import forge.ai.ComputerUtil;
import forge.ai.LobbyPlayerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameObject;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameState;
import forge.game.GameType;
import forge.game.Match;
import forge.game.ability.AbilityKey;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.gui.GuiBase;
import forge.item.PaperCard;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import forge.util.ThreadUtil;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

public final class NativeSaveAudit {
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private static final List<ZoneType> ZONES = List.of(ZoneType.Battlefield, ZoneType.Hand,
            ZoneType.Graveyard, ZoneType.Library, ZoneType.Exile, ZoneType.Command, ZoneType.Sideboard);

    private static void require(boolean ok, String message) {
        if (!ok) throw new IllegalStateException(message);
    }

    private static void write(Path file, Object object) throws Exception {
        Files.createDirectories(file.getParent());
        Files.writeString(file, JSON.toJson(object) + "\n", StandardCharsets.UTF_8);
    }

    private static Deck deck(boolean bolt) {
        Deck deck = new Deck(bolt ? "Canonical Bolt 60" : "Canonical Plains 60");
        deck.getMain().add(bolt ? "Mountain" : "Plains", bolt ? 56 : 60);
        if (bolt) deck.getMain().add("Lightning Bolt", 4);
        require(deck.getMain().countAll() == 60, "Registered main must have exactly 60 cards");
        return deck;
    }

    private static Game create(int seat) {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("Seat " + i, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck(i == seat)).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        rules.setGamesPerMatch(3);
        Match match = new Match(rules, registered, "Declared paid Bolt save compatibility fixture");
        Game game = match.createGame();
        game.setAge(GameStage.Play);
        game.AI_FLAT_MONTE_CARLO = false;
        // Trusted, declared fixture setup, not an opening draw or natural-game claim.
        // Every physical card comes from the complete registered canonical deck.
        for (int i = 0; i < 2; i++) {
            Player player = game.getPlayers().get(i);
            player.setLife(20, null);
            for (PaperCard paper : registered.get(i).getDeck().getMain().toFlatList()) {
                Card card = Card.fromPaperCard(paper, player);
                game.getAction().moveToLibrary(card, -1, null);
            }
            require(player.getAllCards().size() == 60, "Must instantiate all 60 physical cards");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, game.getPlayers().get(seat), 2);
        return game;
    }

    private static Map<String, Object> card(Game game, Card card) {
        return Map.of("name", card.getName(), "owner_seat", game.getPlayers().indexOf(card.getOwner()),
                "controller_seat", game.getPlayers().indexOf(card.getController()),
                "tapped", card.isTapped(), "sick", card.hasSickness(), "face_down", card.isFaceDown());
    }

    private static Map<String, Object> facts(Game game) {
        List<Object> players = new ArrayList<>();
        for (Player player : game.getPlayers()) {
            Map<String, Object> zones = new LinkedHashMap<>();
            for (ZoneType zone : ZONES) {
                List<Map<String, Object>> cards = new ArrayList<>();
                for (Card c : player.getCardsIn(zone)) cards.add(card(game, c));
                // Library/graveyard order is significant. Other physical zones are multisets.
                if (zone != ZoneType.Library && zone != ZoneType.Graveyard) {
                    cards.sort(Comparator.comparing(JSON::toJson));
                }
                zones.put(zone.name(), cards);
            }
            players.add(Map.of("seat", game.getPlayers().indexOf(player), "life", player.getLife(),
                    "physical_cards", player.getAllCards().size(), "zones", zones,
                    "mana_pool", player.getManaPool().toString()));
        }
        List<Object> stack = new ArrayList<>();
        for (var entry : game.getStack()) {
            SpellAbility sa = entry.getSpellAbility();
            List<Object> targets = new ArrayList<>();
            for (GameObject target : sa.getTargets()) {
                if (target instanceof Player p) targets.add(Map.of("player_seat", game.getPlayers().indexOf(p)));
                else if (target instanceof Card c) targets.add(card(game, c));
                else throw new IllegalStateException("Unexpected target kind in declared Bolt fixture");
            }
            stack.add(Map.of("source", card(game, sa.getHostCard()), "is_spell", sa.isSpell(),
                    "activator_seat", game.getPlayers().indexOf(sa.getActivatingPlayer()), "targets", targets));
        }
        return Map.of("players", players, "pending_stack", stack, "stack_count", game.getStack().size(),
                "turn", game.getPhaseHandler().getTurn(), "phase", game.getPhaseHandler().getPhase().name(),
                "active_seat", game.getPlayers().indexOf(game.getPhaseHandler().getPlayerTurn()),
                "priority_seat", game.getPlayers().indexOf(game.getPhaseHandler().getPriorityPlayer()),
                "game_over", game.isGameOver(), "match_outcomes", game.getMatch().getOutcomes().size());
    }

    private static void save(Game game, Path directory) throws Exception {
        Files.createDirectories(directory);
        GameState state = new GameState();
        Map<String, Object> before = facts(game);
        state.initFromGame(game);
        Files.writeString(directory.resolve("state.private.txt"), state.toString(), StandardCharsets.UTF_8);
        write(directory.resolve("facts.private.json"), before);
        require(before.equals(facts(game)), "Export must not change the observed native position");
    }

    private static void export(int seat, Path out) throws Exception {
        Game game = create(seat);
        Player actor = game.getPlayers().get(seat), opponent = game.getPlayers().get(1 - seat);
        Card land = actor.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals("Mountain")).findFirst().orElseThrow();
        Card bolt = actor.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals("Lightning Bolt")).findFirst().orElseThrow();
        // Native moves establish the declared fixture; only the cast below is the paid episode.
        game.getAction().moveToPlay(land, null, AbilityKey.newMap());
        game.getAction().moveToHand(bolt, null);
        Map<String, Object> before = facts(game);
        require(!land.isTapped() && actor.getManaPool().isEmpty(), "No free/preloaded mana");
        SpellAbility spell = bolt.getFirstSpellAbility();
        spell.setActivatingPlayer(actor);
        spell.resetTargets();
        spell.getTargets().add(opponent);
        require(ComputerUtil.playStack(spell, actor, game), "Real canonical Bolt payment must succeed");
        require(land.isTapped() && game.getStack().size() == 1 && opponent.getLife() == 20,
                "Paid Bolt must be genuinely pending before any damage");
        require(bolt.getZone().getZoneType() == ZoneType.Stack, "Physical Bolt must enter native Stack zone");
        save(game, out.resolve("pending"));
        game.getStack().resolveStack();
        require(game.getStack().isEmpty() && opponent.getLife() == 17 && land.isTapped(),
                "Native Bolt must deal exactly 3 after the real payment");
        require(actor.getCardsIn(ZoneType.Graveyard).contains(bolt), "Resolved Bolt must be in graveyard");
        require(actor.getAllCards().size() == 60 && opponent.getAllCards().size() == 60,
                "Settled episode must conserve all physical deck cards");
        save(game, out.resolve("settled"));
        write(out.resolve("EPISODE.private.json"), Map.of("status", "PAID_CANONICAL_BOLT_EXPORTED",
                "seat", seat, "registered_cards", List.of(60, 60), "before", before,
                "mana_paid_by_native_cost_engine", true, "physical_land_tapped", true,
                "native_resolution_damage", 3, "natural_game_qualification", false,
                "rng_or_bo3_resume_qualified", false));
    }

    private static void restore(int seat, Path input, Path out) throws Exception {
        Game game = create(seat);
        write(out.resolve("before.private.json"), facts(game));
        GameState state = new GameState();
        state.parse(Files.readString(input.resolve("state.private.txt"), StandardCharsets.UTF_8).lines());
        state.applyToGame(game); // This method is running on the native game thread, so apply is synchronous.
        write(out.resolve("facts.private.json"), facts(game));
        write(out.resolve("RESTORE.private.json"), Map.of("status", "NATIVE_PARSE_APPLY_RETURNED",
                "fresh_jvm", true, "seat", seat, "input", input.toString(),
                "pending_stack_count", game.getStack().size(), "game_over", game.isGameOver(),
                "custom_stack_reconstruction", false, "full_restart_qualified", false));
    }

    public static void main(String[] args) {
        int exit = 1;
        try {
            require(args.length >= 3, "export SEAT OUTPUT | restore SEAT INPUT OUTPUT");
            GuiBase.setInterface(new GuiDesktop());
            FModel.initialize(null, null);
            FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
            FModel.getPreferences().setPref(FPref.UI_ENABLE_SOUNDS, false);
            FModel.getPreferences().setPref(FPref.UI_ENABLE_MUSIC, false);
            MyRandom.setRandom(new Random(2026110507L));
            int seat = Integer.parseInt(args[1]);
            require(seat == 0 || seat == 1, "Expected a declared physical seat");
            CompletableFuture<Void> done = new CompletableFuture<>();
            ThreadUtil.invokeInGameThread(() -> {
                try {
                    if (args[0].equals("export") && args.length == 3) export(seat, Path.of(args[2]));
                    else if (args[0].equals("restore") && args.length == 4) restore(seat, Path.of(args[2]), Path.of(args[3]));
                    else throw new IllegalArgumentException("Unknown audit command");
                    done.complete(null);
                } catch (Throwable error) { done.completeExceptionally(error); }
            });
            done.get(45, TimeUnit.SECONDS);
            exit = 0;
        } catch (Throwable error) { error.printStackTrace(System.err); }
        System.exit(exit);
    }
}
