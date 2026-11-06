// SPDX-License-Identifier: GPL-3.0-or-later
// Full canonical Forge controls, separate from every frozen predecessor.
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
import forge.game.card.CounterEnumType;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.TreeSet;

public final class NativeSorceryPolicyControls extends AITest {
    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private Game game() {
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
        Game game = new Game(players, rules, new Match(rules, players, "Canonical fallback-only pressure"));
        game.setAge(GameStage.Play);
        require(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Unexpected search mode");
        for (Player player : game.getPlayers()) fillLibrary(player, 8);
        return game;
    }

    private void resolve(Game game) {
        int n = 0;
        while (!game.getStack().isEmpty() && n++ < 12) {
            game.getStack().resolveStack();
            game.getAction().checkStateEffects(true);
        }
        require(game.getStack().isEmpty(), "Native stack did not finish resolving");
    }

    private Card nativeNissa(Game game, Player enemy, Map<String, Object> row) {
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, enemy);
        game.getPhaseHandler().onStackResolved();
        List<Card> forests = addCards("Forest", 5, enemy);
        Card nissa = addCardToZone("Nissa, Who Shakes the World", enemy, ZoneType.Hand);
        game.getAction().checkStateEffects(true);
        PlayerControllerAi controller = (PlayerControllerAi) enemy.getController();
        List<SpellAbility> choices = controller.chooseSpellAbilityToPlay();
        require(choices != null && choices.size() == 1 && choices.get(0).getHostCard().getId() == nissa.getId(),
                "SETUP: native Default did not choose canonical Nissa; no forced setup cast");
        require(controller.playWithRollback(choices.get(0), null), "SETUP: Nissa native payment failed");
        require(forests.stream().allMatch(Card::isTapped), "SETUP: Nissa did not pay five Forests");
        resolve(game);
        nissa = game.getCardState(nissa);
        require(nissa.isInZone(ZoneType.Battlefield) && nissa.getCounters(CounterEnumType.LOYALTY) == 5,
                "SETUP: current Nissa incarnation did not enter with native printed loyalty");
        row.put("native_paid_nissa_setup", true);
        return nissa;
    }

    private void check(int seat, String scene, Map<String, Object> row) {
        Game game = game();
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        actor.setLife(scene.equals("backlash-hold") ? 2 : scene.equals("selfdamage-hold") ? 4 : 20, null);
        enemy.setLife(scene.equals("no-prevention-lethal") ? 3 : 20, null);
        Card target = scene.equals("pw-kill") ? nativeNissa(game, enemy, row) : null;
        PhaseType phase = scene.equals("main1-hold") ? PhaseType.MAIN1
                : scene.equals("upkeep-hold") ? PhaseType.UPKEEP : PhaseType.MAIN2;
        game.getPhaseHandler().devModeSet(phase, scene.equals("opponent-turn-hold") ? enemy : actor);
        game.getPhaseHandler().onStackResolved();
        int mountains = scene.equals("axe") || scene.equals("pw-kill") ? 5 : scene.equals("tax-hold") ? 1 : 3;
        List<Card> mana = addCards("Mountain", mountains, actor);
        if (scene.equals("unfunded-hold")) for (Card land : mana) land.setTapped(true);
        if (scene.equals("activated-hold")) {
            mana.add(addCard("Swamp", actor));
            addCard("Immersturm Skullcairn", actor);
        }
        if (scene.equals("lifegain-hold")) {
            mana.add(addCard("Forest", actor));
            mana.add(addCard("Plains", actor));
        }
        if (scene.equals("creature-kill")) target = addCard("Centaur Courser", enemy);
        if (scene.equals("prevention-hold") || scene.equals("no-prevention-lethal")) addCard("Glacial Chasm", enemy);
        if (scene.equals("hexproof-hold")) addCard("Leyline of Sanctity", enemy);
        if (scene.equals("tax-hold")) addCard("Chill", enemy);
        if (scene.equals("fixed-life-hold")) addCard("Platinum Emperion", enemy);
        if (scene.equals("backlash-hold")) addCard("Eidolon of the Great Revel", actor);
        if (scene.equals("selfdamage-hold")) addCard("Fireslinger", actor).setSickness(false);
        String name = scene.equals("axe") || scene.equals("pw-kill") ? "Lava Axe"
                : scene.equals("creature-kill") || scene.equals("flexible-hold") ? "Volcanic Hammer"
                : scene.equals("instant-hold") ? "Lightning Bolt"
                : scene.equals("no-prevention-lethal") ? "Flames of the Blood Hand"
                : scene.equals("lifegain-hold") ? "Fiery Justice" : "Lava Spike";
        int handCount = scene.startsWith("pressure") ? Integer.parseInt(scene.substring(8))
                : scene.equals("activated-hold") || scene.equals("selfdamage-hold") ? 0 : 1;
        List<Card> original = new ArrayList<>();
        for (int i = 0; i < handCount; i++) original.add(addCardToZone(name, actor, ZoneType.Hand));
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        boolean expect = scene.startsWith("pressure") || scene.equals("axe") || scene.equals("pw-kill")
                || scene.equals("creature-kill") || scene.equals("no-prevention-lethal");
        List<Map<String, Object>> steps = new ArrayList<>();
        row.put("steps", steps);
        row.put("source_ids", original.stream().map(Card::getId).toList());
        row.put("expected_cast", expect);
        int enemyBefore = enemy.getLife(), ownBefore = actor.getLife();
        long initiallyTapped = mana.stream().filter(Card::isTapped).count();
        PlayerControllerAi controller = (PlayerControllerAi) actor.getController();
        for (int step = 0; step < (expect ? handCount : 1); step++) {
            require(game.getStack().isEmpty(), "Not a fresh empty-stack decision");
            List<SpellAbility> choices = controller.chooseSpellAbilityToPlay();
            SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
            Map<String, Object> action = new LinkedHashMap<>();
            action.put("step", step+1);
            action.put("chosen_source", chosen == null ? "PASS" : chosen.getHostCard().getName());
            action.put("hand_before_payment", actor.getCardsIn(ZoneType.Hand).size());
            action.put("enemy_life_before_payment", enemy.getLife());
            action.put("tapped_before_payment", mana.stream().filter(Card::isTapped).count());
            steps.add(action);
            if (!expect) {
                require(chosen == null, "Preservation control unexpectedly chose an action");
                require(original.stream().allMatch(card -> card.isInZone(ZoneType.Hand))
                        && mana.stream().filter(Card::isTapped).count() == initiallyTapped
                        && actor.getManaPool().totalMana() == 0 && enemy.getLife() == enemyBefore
                        && actor.getLife() == ownBefore, "Decline mutated cards, mana or life");
                break;
            }
            require(chosen != null, "Native Default declined declared positive at decision " + (step+1));
            int sourceId = chosen.getHostCard().getId();
            require(original.stream().anyMatch(card -> card.getId() == sourceId && card.isInZone(ZoneType.Hand)),
                    "Choice is not one of the original canonical hand cards");
            require(chosen.getTargets().contains(target == null ? enemy : target), "Native target preference changed");
            action.put("source_id", sourceId);
            action.put("native_target", target == null ? "opponent" : target.getName());
            require(controller.playWithRollback(chosen, null), "Native selected cast/payment failed");
            require(chosen.getHostCard().isInZone(ZoneType.Stack) && !game.getStack().isEmpty(), "No actual native stack entry");
            int cost = name.equals("Lava Axe") ? 5 : name.equals("Volcanic Hammer") ? 2
                    : name.equals("Flames of the Blood Hand") ? 3 : 1;
            require(mana.stream().filter(Card::isTapped).count() == cost * (step+1)
                    && actor.getManaPool().totalMana() == 0, "Native cost was not actually paid");
            resolve(game);
            action.put("paid_sources", cost);
            action.put("enemy_life_after", enemy.getLife());
            action.put("native_game_terminal", game.isGameOver());
            require(actor.getLife() == ownBefore, "Positive cast harmed its actor");
            if (target != null) {
                require(game.getCardState(target).isInZone(ZoneType.Graveyard) && enemy.getLife() == enemyBefore, "Native removal target did not die without stealing face preference");
            } else {
                int damage = name.equals("Lava Axe") ? 5 : name.equals("Flames of the Blood Hand") ? 4 : 3;
                require(enemy.getLife() == enemyBefore-damage*(step+1), "Native damage resolution differs");
            }
        }
        if (expect) {
            TreeSet<Integer> graveyard = new TreeSet<>();
            for (Card card : actor.getCardsIn(ZoneType.Graveyard)) graveyard.add(card.getId());
            require(graveyard.equals(new TreeSet<>(original.stream().map(Card::getId).toList()))
                    && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Original source IDs did not complete native lifecycle");
            if (scene.equals("no-prevention-lethal")) require(game.isGameOver() && actor.hasWon(), "NoPrevention native lethal did not win");
            else require(!game.isGameOver(), "Nonlethal/removal control unexpectedly ended game");
        }
        row.put("passed", true);
    }

    private static Throwable unwrap(Throwable failure) {
        return failure instanceof InvocationTargetException ? ((InvocationTargetException) failure).getCause() : failure;
    }

    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        JsonObject declaration = JsonParser.parseString(Files.readString(output.resolve("DECLARATION.json"))).getAsJsonObject();
        require(declaration.get("seed").getAsLong() == 2026110617L, "Undeclared seed");
        MyRandom.setRandom(new Random(2026110617L));
        NativeSorceryPolicyControls test = new NativeSorceryPolicyControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        List<Map<String, Object>> rows = new ArrayList<>();
        int failures = 0, errors = 0;
        Class<?> chainClass = Class.forName("forge.evaluation.NativeSorceryChainControls");
        Object chain = chainClass.getConstructor().newInstance();
        Method chainCheck = chainClass.getDeclaredMethod("check", int.class, Map.class);
        chainCheck.setAccessible(true);
        for (int seat : new int[]{0, 1}) {
            Map<String, Object> row = new LinkedHashMap<>(); row.put("cohort", "unchanged-chain2-check-method"); row.put("seat", seat); rows.add(row);
            try { chainCheck.invoke(chain, seat, row); }
            catch (Throwable failure) { Throwable cause = unwrap(failure); row.put("failure", cause.toString()); if (cause instanceof AssertionError) failures++; else errors++; }
        }
        for (int seat : new int[]{0, 1}) for (var value : declaration.getAsJsonArray("new_scenes")) {
            String scene = value.getAsString();
            Map<String, Object> row = new LinkedHashMap<>(); row.put("cohort", "new-controls"); row.put("seat", seat); row.put("scene", scene); rows.add(row);
            try { test.check(seat, scene, row); }
            catch (Throwable failure) { row.put("failure", failure.toString()); if (failure instanceof AssertionError) failures++; else errors++; System.err.println("FAIL " + row.get("seat") + " " + scene + ": " + failure); }
        }
        Class<?> lethalClass = Class.forName("forge.evaluation.NativeLethalTimingControls");
        Object lethal = lethalClass.getConstructor().newInstance();
        Method lethalCheck = lethalClass.getDeclaredMethod("check", int.class, String.class, String.class, boolean.class, PhaseType.class);
        lethalCheck.setAccessible(true);
        for (int seat : new int[]{0, 1}) for (String scene : List.of("lethal-mode", "lethal-instant", "nonlethal", "partial-prevention", "full-prevention", "hexproof", "tax-unpayable", "cannot-lose", "zero-life-not-loss", "own-backlash", "lethal-activated", "infect-not-life-lethal", "nonlethal-endstep")) {
            Map<String, Object> row = new LinkedHashMap<>(); row.put("cohort", "unchanged-lethal26-check-method"); row.put("seat", seat); row.put("scene", scene); rows.add(row);
            String card = scene.equals("lethal-instant") ? "Skullcrack" : scene.equals("lethal-activated") || scene.equals("infect-not-life-lethal") ? "Goblin Fireslinger" : "Boros Charm";
            try { lethalCheck.invoke(lethal, seat, scene, card, scene.startsWith("lethal-") || scene.equals("nonlethal-endstep"), scene.equals("nonlethal-endstep") ? PhaseType.END_OF_TURN : PhaseType.MAIN1); row.put("passed", true); }
            catch (Throwable failure) { Throwable cause = unwrap(failure); row.put("failure", cause.toString()); if (cause instanceof AssertionError) failures++; else errors++; }
        }
        String json = new Gson().toJson(Map.of("seed", 2026110617L, "passed", rows.size()-failures-errors,
                "failures", failures, "errors", errors, "natural_games", 0, "cases", rows));
        Files.writeString(output.resolve("summary.private.json"), json+"\n");
        System.out.println(json);
        System.exit(failures == 0 && errors == 0 ? 0 : 1);
    }
}
