// SPDX-License-Identifier: GPL-3.0-or-later
// Constructed canonical native positions; never a replay of a private natural hand.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import forge.ai.AITest;
import forge.ai.LobbyPlayerAi;
import forge.ai.PlayerControllerAi;
import forge.deck.Deck;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameStage;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.TreeMap;

public final class NativeLinkedDamageLethalAudit extends AITest {
    private record Scene(Game game, Player actor, Player enemy, Card source, Card creature,
                         List<Card> lands, boolean landfall) {}

    private static void require(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    private Scene setup(int seat, JsonObject declaration) {
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi("canonical-seat" + i, null) {
                @Override public Player createIngamePlayer(Game game, int id) {
                    Player player = new Player(getName(), game, id);
                    player.setFirstController(new PublicNameController(game, player, this, Map.of()));
                    return player;
                }
            };
            lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck()).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "Canonical linked damage audit"));
        game.setAge(GameStage.Play);
        require(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Unexpected search mode");
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        actor.setLife(20, null);
        enemy.setLife(1, null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor);
        game.getPhaseHandler().onStackResolved();
        fillLibrary(actor, 8);
        fillLibrary(enemy, 8);
        List<Card> lands = new ArrayList<>(addCards("Mountain", 2, actor));
        String creatureName = declaration.get("creature").getAsString();
        // Existing battlefield pose: no creature ETB or search is invented here.
        Card creature = creatureName.isEmpty() ? null : addCard(creatureName, enemy);
        if (declaration.get("name").getAsString().equals("player-hexproof")) {
            addCard("Leyline of Sanctity", enemy);
        }
        Card source = addCardToZone("Searing Blaze", actor, ZoneType.Hand);
        boolean landfall = declaration.get("landfall").getAsBoolean();
        if (landfall) {
            Card land = addCardToZone("Mountain", actor, ZoneType.Hand);
            require(actor.canPlayLand(land, false, null), "SETUP: native land play is not legal");
            Card entered = actor.playLand(land, null);
            require(entered != null && entered.isInZone(ZoneType.Battlefield)
                    && entered.getId() == land.getId(), "SETUP: genuine native land entry failed");
            lands.add(entered);
        }
        if (declaration.get("name").getAsString().equals("unfunded")) {
            for (Card land : lands) land.setTapped(true);
        }
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        require(game.getStack().isEmpty() && !game.isGameOver(), "SETUP: not a fresh live empty-stack game");
        return new Scene(game, actor, enemy, source, creature, lands, landfall);
    }

    // Structural observations only: no legality, cost, forecasting, evaluator or RNG calls.
    private Map<String, Object> physical(Scene scene) {
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> players = new ArrayList<>();
        for (Player player : scene.game.getPlayers()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", player.getId()); row.put("life", player.getLife());
            row.put("mana_count", player.getManaPool().totalMana());
            List<Map<String, Object>> cards = new ArrayList<>();
            for (ZoneType zone : List.of(ZoneType.Hand, ZoneType.Battlefield, ZoneType.Graveyard,
                    ZoneType.Library, ZoneType.Exile)) {
                for (Card card : player.getCardsIn(zone)) {
                    cards.add(Map.of("id", card.getId(), "name", card.getName(), "zone", zone.name(),
                            "timestamp", card.getGameTimestamp(), "tapped", card.isTapped(),
                            "damage", card.getDamage(), "counters", card.getCounters().toString()));
                }
            }
            row.put("cards", cards); players.add(row);
        }
        result.put("players", players); result.put("stack_empty", scene.game.getStack().isEmpty());
        result.put("terminal", scene.game.isGameOver());
        return result;
    }

    private List<Map<String, Object>> chain(SpellAbility root) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (SpellAbility ability = root; ability != null; ability = ability.getSubAbility()) {
            Map<String, Object> node = new LinkedHashMap<>();
            node.put("api", String.valueOf(ability.getApi()));
            node.put("params", new TreeMap<>(ability.getMapParams()));
            node.put("mandatory_flag", ability.isMandatory());
            List<String> targets = new ArrayList<>();
            for (var target : ability.getTargets()) {
                targets.add(target instanceof Player p ? "player:" + p.getId()
                        : target instanceof Card c ? "card:" + c.getId() : target.toString());
            }
            node.put("targets", targets); result.add(node);
        }
        return result;
    }

    private void observeAfterChoice(Scene s, Map<String, Object> row) {
        row.put("native_landfall", s.actor.hasLandfall());
        row.put("native_lands_played", s.actor.getLandsPlayedThisTurn());
        row.put("source_id", s.source.getId());
        row.put("source_printed_mana_cost", s.source.getManaCost().toString());
        row.put("mana_source_ids", s.lands.stream().map(Card::getId).toList());
        row.put("source_ability_chain_after_choice", chain(s.source.getSpellAbilities().get(0)));
        require(s.actor.hasLandfall() == s.landfall, "SETUP: actual landfall does not match declared scene");
        require(s.actor.getLandsPlayedThisTurn() == (s.landfall ? 1 : 0), "SETUP: native land-play history differs");
    }

    private void paidResolve(Scene s, SpellAbility selected, boolean manual, Map<String, Object> row) {
        PlayerControllerAi controller = (PlayerControllerAi) s.actor.getController();
        row.put("selected_chain", chain(selected));
        require(selected.getHostCard().getId() == s.source.getId(), "Selected another source");
        boolean paid;
        if (manual) {
            paid = controller.playWithRollback(selected, root -> {
                root.resetTargets();
                require(root.canTarget(s.enemy), "MANUAL: root player target is not legal");
                root.getTargets().add(s.enemy);
                SpellAbility child = root.getSubAbility();
                require(child != null && s.creature != null, "MANUAL: missing linked creature");
                child.resetTargets();
                require(child.canTarget(s.creature), "MANUAL: linked creature target is not legal");
                child.getTargets().add(s.creature);
                require(root.isTargetNumberValid() && child.isTargetNumberValid(), "MANUAL: incomplete targets");
            });
        } else {
            require(selected.getTargets().contains(s.enemy), "AI did not target declared opposing player");
            require(selected.getSubAbility() != null && selected.getSubAbility().getTargets().contains(s.creature),
                    "AI did not target declared linked creature");
            paid = controller.playWithRollback(selected, null);
        }
        row.put("native_payment_succeeded", paid);
        require(paid && selected.getHostCard().isInZone(ZoneType.Stack) && !s.game.getStack().isEmpty(),
                "No actual paid native cast/stack entry");
        row.put("paid_chain", chain(selected));
        row.put("paid_mana", selected.getPayingMana().stream().map(m -> Map.of(
                "color", m.getColor(), "source_id", m.getSourceCard().getId())).toList());
        long tapped = s.lands.stream().filter(Card::isTapped).count();
        row.put("tapped_mana_sources", tapped);
        require(tapped == 2 && selected.getPayingMana().size() == 2
                && s.actor.getManaPool().totalMana() == 0, "Native RR payment not demonstrated");
        int resolutions = 0;
        while (!s.game.getStack().isEmpty() && !s.game.isGameOver() && resolutions++ < 8) {
            s.game.getStack().resolveStack();
            s.game.getAction().checkStateEffects(true);
        }
        row.put("resolved_physical", physical(s));
        row.put("enemy_life_after", s.enemy.getLife());
        row.put("own_life_after", s.actor.getLife());
        row.put("native_terminal", s.game.isGameOver());
        row.put("native_actor_won", s.actor.hasWon());
        row.put("native_enemy_lost", s.enemy.hasLost());
        require(s.enemy.getLife() == (s.landfall ? -2 : 0) && s.actor.getLife() == 20,
                "Native linked damage/life differs from declared canonical effect");
        require(s.game.isGameOver() && s.actor.hasWon() && s.enemy.hasLost(), "Native winner not reached");
        require(s.game.getCardState(s.source).isInZone(ZoneType.Graveyard), "Source did not reach graveyard");
    }

    private void check(int seat, JsonObject declaration, boolean manual, Map<String, Object> row) {
        Scene s = setup(seat, declaration);
        Map<String, Object> before = physical(s);
        row.put("before_choice_physical", before);
        SpellAbility chosen;
        if (manual) {
            row.put("default_choice_invocations", 0);
            chosen = s.source.getSpellAbilities().get(0);
            chosen.setActivatingPlayer(s.actor);
        } else {
            row.put("default_choice_invocations", 1);
            List<SpellAbility> choices = ((PlayerControllerAi) s.actor.getController()).chooseSpellAbilityToPlay();
            require(choices == null || choices.size() <= 1, "Unexpected multiple actions");
            chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        }
        row.put("chosen", chosen == null ? "PASS" : chosen.getHostCard().getName());
        Map<String, Object> after = physical(s);
        row.put("after_choice_physical", after);
        row.put("physical_choice_pure", before.equals(after));
        observeAfterChoice(s, row);
        require(before.equals(after), "Choice changed physical cards, life, stack or mana before payment");
        boolean expect = declaration.get("expect_win").getAsBoolean();
        row.put("expected_native_win", expect);
        if (chosen != null) paidResolve(s, chosen, manual, row);
        if (expect) require(chosen != null, "Default declined declared legal lethal; expectation unchanged");
        else require(chosen == null, "Negative control unexpectedly selected a spell");
        row.put("passed", true);
    }

    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        JsonObject declaration = JsonParser.parseString(Files.readString(output.resolve("DECLARATION.json"))).getAsJsonObject();
        require(declaration.get("seed").getAsLong() == 2026110623L, "Undeclared seed");
        MyRandom.setRandom(new Random(2026110623L));
        NativeLinkedDamageLethalAudit test = new NativeLinkedDamageLethalAudit();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        List<Map<String, Object>> rows = new ArrayList<>();
        int failures = 0, errors = 0;
        // All AI cases precede all separately constructed manual controls.
        for (boolean manual : new boolean[]{false, true}) {
            for (int seat : new int[]{0, 1}) for (var item : declaration.getAsJsonArray("ai_scenes")) {
                JsonObject scene = item.getAsJsonObject();
                if (manual && !scene.get("expect_win").getAsBoolean()) continue;
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("cohort", manual ? "MANUAL-TRUSTED-LEGAL-ACTION-NOT-AI" : "AI-FIRST-DEFAULT-CHOICE");
                row.put("scene", scene.get("name").getAsString()); row.put("seat", seat); rows.add(row);
                try { test.check(seat, scene, manual, row); }
                catch (Throwable failure) {
                    row.put("failure", failure.toString());
                    if (failure instanceof AssertionError) failures++; else { errors++; failure.printStackTrace(); }
                    System.err.println("FAILED " + row.get("cohort") + " " + seat + " " + row.get("scene") + ": " + failure);
                }
            }
        }
        String json = new Gson().toJson(Map.of("label", declaration.get("label").getAsString(),
                "seed", 2026110623L, "passed", rows.size()-failures-errors, "failures", failures,
                "errors", errors, "natural_game_reproduction", false, "cases", rows));
        Files.writeString(output.resolve("summary.private.json"), json + "\n");
        System.out.println(json);
        System.exit(failures == 0 && errors == 0 ? 0 : 1);
    }
}
