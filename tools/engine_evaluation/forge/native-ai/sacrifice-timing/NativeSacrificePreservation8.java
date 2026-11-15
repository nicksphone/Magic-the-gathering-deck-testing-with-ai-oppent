// SPDX-License-Identifier: GPL-3.0-or-later
// INTERNAL-PROTOCOL: constructed real native frames, not expert or natural games.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.AbilityKey;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeSacrificePreservation8 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final List<String> SCENES = List.of(
            "RestInPeace", "OpponentTwoLife", "OpponentPlatinumAngel", "OpponentHushbringer");
    private static void need(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true);
        return card;
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) {
            stream.writeObject(MyRandom.getRandom());
        }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Object> ability(SpellAbility sa) {
        if (sa == null) return Map.of("choice", "PASS");
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("source", sa.getHostCard().getName());
        record.put("source_id", sa.getHostCard().getId());
        record.put("ability_id", sa.getId());
        record.put("api", String.valueOf(sa.getApi()));
        record.put("is_spell", sa.isSpell());
        record.put("native_description", sa.toString());
        record.put("native_cost", String.valueOf(sa.getPayCosts()));
        return record;
    }
    private static Card pose(Player player, String name) {
        Card original = player.getCardsIn(ZoneType.Library).stream()
                .filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        return player.getGame().getAction().moveToPlay(original, player, null, AbilityKey.newMap());
    }
    private static Card actualCardRef(Game game, Card previous) {
        Card current = game.getCardState(previous, null);
        need(current != null && current.getId() == previous.getId(), "Actual native card reference after move");
        return current;
    }
    private static void priority(Game game, Player actor, Player enemy) {
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true);
        enemy.setHasPriority(false);
    }
    // Inherited verbatim from the parent's frozen Timing6 waiting-trigger resolver.
    private static void resolve(Game game) {
        for (int count = 0; count < 20; count++) {
            if (game.isGameOver()) return;
            game.getAction().checkStateEffects(true);
            if (game.isGameOver()) return;
            game.getTriggerHandler().runWaitingTriggers();
            game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        need(game.getStack().isEmpty() || game.isGameOver(), "Bounded actual native stack resolution");
    }
    private static List<Card> food(Player player) {
        return player.getCardsIn(ZoneType.Battlefield).stream()
                .filter(c -> c.getType().hasSubtype("Food") && c.getController().equals(player)).toList();
    }
    private static SpellAbility ovenActivation(Card oven, Player player) {
        SpellAbility sa = oven.getSpellAbilities().stream()
                .filter(s -> s.isActivatedAbility() && s.getApi() == ApiType.Token).findFirst().orElseThrow();
        sa.setActivatingPlayer(player);
        return sa;
    }
    private void check(long seed, int seat, String scene, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(seed));
        row.put("rng_before_construction", rng());
        String blocker = switch (scene) {
            case "RestInPeace" -> "Rest in Peace";
            case "OpponentPlatinumAngel" -> "Platinum Angel";
            case "OpponentHushbringer" -> "Hushbringer";
            default -> null;
        };
        int enemyLife = scene.equals("OpponentTwoLife") ? 2 : 1;
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("sacrifice-preservation-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Witch's Oven", 1);
                deck.getMain().add("Cauldron Familiar", 1);
                deck.getMain().add("Blood Artist", 1);
                deck.getMain().add("Swamp", 57);
            } else {
                if (blocker != null) deck.getMain().add(blocker, 1);
                deck.getMain().add("Mountain", blocker == null ? 60 : 59);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("preservation-seat-" + index, null);
            lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed);
        rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-PROTOCOL-SACRIFICE-PRESERVATION8"));
        game.setAge(GameStage.Play);
        NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int count = 0; count < entry.getValue(); count++)
                    addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60
                    && player.getAllCards().size() == 60, "Complete native registered60 originals");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor);
        game.getPhaseHandler().onStackResolved();
        if (blocker != null) pose(enemy, blocker);
        Card oven = pose(actor, "Witch's Oven");
        Card cat = pose(actor, "Cauldron Familiar");
        Card artist = pose(actor, "Blood Artist");
        List<Card> mana = List.of(pose(actor, "Swamp"), pose(actor, "Swamp"));
        resolve(game);
        actor.setLife(2, null);
        enemy.setLife(enemyLife, null);
        game.getAction().checkStateEffects(true);
        priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty()
                && actor.getLife() == 2 && enemy.getLife() == enemyLife,
                "Settled declared nonterminal life totals");
        need(actor.getCardsIn(ZoneType.Battlefield).size() == 5 && actor.getCardsIn(ZoneType.Hand).isEmpty()
                && cat.isInZone(ZoneType.Battlefield) && artist.isInZone(ZoneType.Battlefield)
                && !oven.isTapped() && mana.stream().noneMatch(Card::isTapped) && food(actor).isEmpty(),
                "Trusted full-program battlefield, own two Swamps, no prior cost payment or Food");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(),
                "Unmodified native Default, Monte Carlo off");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("rng_before_choice", rng());
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        // Freeze the actual first observation before any reflective diagnostic or manual action.
        row.put("first_choice", ability(chosen));
        row.put("ordinary_choice_count", choices == null ? 0 : choices.size());
        row.put("ordinary_Default_initial_callbacks", 1);
        row.put("first_choice_judged", false);
        row.put("first_choice_executed", false);
        row.put("rng_after_choice", rng());
        row.put("after_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));

        SpellAbility diagnostic = ovenActivation(actualCardRef(game, oven), actor);
        Method helper = SpellAbilityAi.class.getDeclaredMethod(
                "hasKnownWinningSacrificeCost", Player.class, SpellAbility.class);
        need(helper.getReturnType() == boolean.class && Modifier.isPrivate(helper.getModifiers())
                && Modifier.isStatic(helper.getModifiers()), "Exact planned private static boolean helper ABI");
        helper.setAccessible(true);
        boolean helperResult = (Boolean) helper.invoke(null, actor, diagnostic);
        row.put("postchoice_hasKnownWinningSacrificeCost", helperResult);
        row.put("rng_after_helper", rng());
        List<String> failed = new ArrayList<>();
        if (helperResult) failed.add("False immediate sacrifice-cost win in " + scene);

        need(!game.isGameOver() && game.getStack().isEmpty()
                && !actualCardRef(game, oven).isTapped()
                && actualCardRef(game, cat).isInZone(ZoneType.Battlefield)
                && actualCardRef(game, artist).isInZone(ZoneType.Battlefield)
                && mana.stream().noneMatch(c -> actualCardRef(game, c).isTapped())
                && actor.getLife() == 2 && enemy.getLife() == enemyLife,
                "No observed choice executed or sacrifice cost changed before independent manual control");
        row.put("manual_control_not_AI_success", true);
        row.put("rng_before_manual_control", rng());
        priority(game, actor, enemy);
        boolean paid = ComputerUtil.playStack(ovenActivation(actualCardRef(game, oven), actor), actor, game);
        row.put("manual_oven_paid", paid);
        need(paid && actualCardRef(game, oven).isTapped(), "Manual native Oven paid genuine tap/sacrifice cost");
        List<Card> sacrificed = List.of(actualCardRef(game, cat), actualCardRef(game, artist)).stream()
                .filter(c -> !c.isInZone(ZoneType.Battlefield)).toList();
        need(sacrificed.size() == 1, "Exactly one original creature moved as actual cost victim");
        Card victim = sacrificed.get(0);
        ZoneType destination = scene.equals("RestInPeace") ? ZoneType.Exile : ZoneType.Graveyard;
        need(victim.isInZone(destination), "Actual cost victim's native destination");
        row.put("actual_cost_victim", Map.of("name", victim.getName(), "id", victim.getId(),
                "zone", destination.name()));
        row.put("rng_after_manual_payment", rng());
        resolve(game);
        row.put("rng_after_native_resolution", rng());
        row.put("manual_native_game_over", game.isGameOver());
        row.put("manual_actor_has_won", actor.hasWon());
        row.put("manual_enemy_has_lost", enemy.hasLost());
        row.put("actor_life_after", actor.getLife());
        row.put("enemy_life_after", enemy.getLife());
        row.put("food_after", food(actor).size());
        row.put("after_manual_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        need(!game.isGameOver() && !actor.hasWon() && !enemy.hasLost() && game.getStack().isEmpty(),
                "Manual unopposed native resolution must be NONTERMINAL");
        need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Oven genuinely resolved to one native Food");
        need(actualCardRef(game, victim).isInZone(destination), "Reacquired cost victim after native resolution");
        int expectedEnemyLife = scene.equals("OpponentTwoLife") ? 1 : scene.equals("OpponentPlatinumAngel") ? 0 : 1;
        int expectedActorLife = scene.equals("OpponentTwoLife") || scene.equals("OpponentPlatinumAngel") ? 3 : 2;
        need(enemy.getLife() == expectedEnemyLife && actor.getLife() == expectedActorLife,
                "Native single death drain, replacement, suppression or Angel prevention at zero");
        if (blocker != null) need(enemy.getCardsIn(ZoneType.Battlefield).stream()
                .anyMatch(c -> c.getName().equals(blocker)), "Native opposing blocker remains active");
        row.put("later_two_step_win_claimed", false);
        row.put("failures", failed);
        row.put("status", failed.isEmpty() ? "PASS" : "HELPER_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private report directory argument; launch only after exact parent pins and GO");
        Path out = Path.of(args[0]);
        need(Files.isDirectory(out), "Runner-created local report directory");
        MyRandom.setRandom(new Random(2026110629L));
        NativeSacrificePreservation8 audit = new NativeSacrificePreservation8();
        audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, callbacks = 0, index = 0;
        for (String scene : SCENES) {
            long seed = 2026110629L + index++;
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", seed,
                        "label", "INTERNAL-PROTOCOL", "ordinary_choice_is_observation_only", true));
                try {
                    audit.check(seed, seat, scene, row);
                    if (row.get("status").equals("PASS")) pass++; else red++;
                } catch (Throwable error) {
                    errors++;
                    row.put("status", "HARNESS_ERROR");
                    row.put("error_type", error.getClass().getName());
                    row.put("error", String.valueOf(error.getMessage()));
                    error.printStackTrace(System.err);
                }
                callbacks += ((Number) row.getOrDefault("ordinary_Default_initial_callbacks", 0)).intValue();
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n",
                        StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status"))));
                System.out.flush();
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "INTERNAL-PROTOCOL-NATIVE-SACRIFICE-PRESERVATION8");
        summary.put("total", 8);
        summary.put("pass", pass);
        summary.put("helper_red", red);
        summary.put("harness_errors", errors);
        summary.put("ordinary_Default_initial_callbacks", callbacks);
        summary.put("ordinary_choices_judged", false);
        summary.put("manual_controls_are_AI_successes", false);
        summary.put("natural_games", 0);
        summary.put("expert_games", 0);
        summary.put("RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n",
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        System.out.println(JSON.toJson(summary));
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
