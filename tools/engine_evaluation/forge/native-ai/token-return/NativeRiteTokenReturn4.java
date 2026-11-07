// SPDX-License-Identifier: GPL-3.0-or-later
// Constructed native fixtures using the Forge Team/Card-Forge engine and full programs.
// These are not natural games or synthetic replacements for printed card abilities.
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeRiteTokenReturn4 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
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
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) { stream.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Object> ability(SpellAbility sa) {
        if (sa == null) return Map.of("choice", "PASS");
        return Map.of("source", sa.getHostCard().getName(), "source_id", sa.getHostCard().getId(),
                "ability_id", sa.getId(), "api", String.valueOf(sa.getApi()), "is_spell", sa.isSpell());
    }
    private static Card pose(Player player, String name) {
        Card original = player.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        return player.getGame().getAction().moveToPlay(original, player, null, AbilityKey.newMap());
    }
    private static void priority(Game game, Player actor, Player enemy) {
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
    }
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
    private static SpellAbility activation(Card source, Player player, ApiType api) {
        SpellAbility sa = source.getSpellAbilities().stream().filter(s -> s.isActivatedAbility() && s.getApi() == api).findFirst().orElseThrow();
        sa.setActivatingPlayer(player); return sa;
    }
    private static Card actualCardRef(Game game, Card previous) {
        Card current = game.getCardState(previous, null);
        need(current != null && current.getId() == previous.getId(), "Actual native card reference after movement");
        return current;
    }
    private static Map<String, Object> state(Game game, Player actor, Player enemy) throws Exception {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("actor_life", actor.getLife()); value.put("enemy_life", enemy.getLife());
        value.put("native_game_over", game.isGameOver()); value.put("native_stack_empty", game.getStack().isEmpty());
        value.put("Food", food(actor).stream().map(c -> Map.of("id", c.getId(), "is_token", c.isToken(), "tapped", c.isTapped())).toList());
        value.put("Forests", actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest"))
                .map(c -> Map.of("id", c.getId(), "tapped", c.isTapped())).toList());
        value.put("actor_view", new ActorBoundary(actor).snapshot(game.getView())); value.put("rng", rng());
        return value;
    }
    private static Map<String, Object> flags(Card card) {
        return Map.of("name", card.getName(), "id", card.getId(), "isToken", card.isToken(),
                "isCloned", card.isCloned(), "hasAlternateState", card.hasAlternateState());
    }
    private static List<String> pool(Player player) {
        List<String> result = new ArrayList<>();
        for (var mana : player.getManaPool()) result.add(mana.toString());
        return result;
    }
    private void check(int seat, boolean positive, Map<String, Object> row) throws Exception {
        row.put("rng_before_construction", rng());
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("native-rite-token-return-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Rite of Replication", 1); deck.getMain().add("Witch's Oven", 1);
                if (positive) deck.getMain().add("Cauldron Familiar", 1);
                deck.getMain().add("Island", positive ? 57 : 58);
            } else { deck.getMain().add("Cauldron Familiar", 1); deck.getMain().add("Mountain", 59); }
            LobbyPlayerAi lobby = new LobbyPlayerAi("rite-token-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-PROTOCOL-RITE-TOKEN4"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getAllCards().size() == 60 && player.getRegisteredPlayer().getDeck().getMain().countAll() == 60,
                    "Complete native registered60 originals");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor); game.getPhaseHandler().onStackResolved();
        Card opposingCat = pose(enemy, "Cauldron Familiar"), oven = pose(actor, "Witch's Oven");
        List<Card> islands = List.of(pose(actor, "Island"), pose(actor, "Island"), pose(actor, "Island"), pose(actor, "Island"));
        Card realCat = null;
        if (positive) {
            Card original = actor.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals("Cauldron Familiar")).findFirst().orElseThrow();
            realCat = game.getAction().moveTo(actor.getZone(ZoneType.Graveyard), original, null, AbilityKey.newMap());
            row.put("own_real_Cat_GY_pose", "TRUSTED_LIBRARY_TO_GRAVEYARD; NOT_CAUSAL_PAID_DEATH");
            row.put("own_real_Cat_flags_before_assumptions", flags(realCat));
            need(!realCat.isToken() && realCat.getOwner().equals(actor), "Trusted original real Cat owner/identity");
        }
        Card riteOriginal = actor.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals("Rite of Replication")).findFirst().orElseThrow();
        Card rite = game.getAction().moveToHand(riteOriginal, null);
        resolve(game); priority(game, actor, enemy);
        row.put("before_actual_Rite_cast", state(game, actor, enemy));
        SpellAbility cast = rite.getSpellAbilities().stream().filter(sa -> sa.isSpell() && sa.getApi() == ApiType.CopyPermanent).findFirst().orElseThrow();
        cast.setActivatingPlayer(actor); cast.getTargets().add(actualCardRef(game, opposingCat));
        row.put("actual_Rite_cost", cast.getPayCosts().toString()); row.put("actual_Rite_target_id", opposingCat.getId());
        boolean ritePaid = ComputerUtil.playStack(cast, actor, game); row.put("actual_Rite_paid", ritePaid);
        need(ritePaid && islands.stream().allMatch(c -> actualCardRef(game, c).isTapped()), "Genuine Rite paid four actual Islands for 2UU");
        resolve(game);
        List<Card> created = actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Cauldron Familiar")).toList();
        row.put("Rite_created_flags_before_assumptions", created.stream().map(NativeRiteTokenReturn4::flags).toList());
        need(created.size() == 1 && created.get(0).isToken() && created.get(0).getOwner().equals(actor),
                "Actual full native Rite creates one actor-owned Cat token");
        Card token = created.get(0);
        row.put("after_actual_Rite_ETB_before_life_assignment", state(game, actor, enemy));
        row.put("fixture_life_assignment", Map.of("actor", 2, "enemy", 1));
        actor.setLife(2, null); enemy.setLife(1, null); game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && !actualCardRef(game, oven).isTapped()
                && actor.getCreaturesInPlay().size() == 1 && food(actor).isEmpty() && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Declared token-only sacrifice frontier");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Native Default MC off");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView())); row.put("rng_before_choice", rng());
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("first_choice", ability(chosen)); row.put("ordinary_Default_initial_callbacks", 1);
        row.put("first_choice_executed", false); row.put("first_choice_judged", positive); row.put("rng_after_choice", rng());
        List<String> failures = new ArrayList<>();
        boolean selectedOven = chosen != null && chosen.getHostCard().getId() == oven.getId() && chosen.getApi() == ApiType.Token;
        row.put("first_AI_selected_Oven", selectedOven);
        row.put("helper_before_view", new ActorBoundary(actor).snapshot(game.getView())); row.put("helper_before_rng", rng()); row.put("helper_before_pool", pool(actor));
        java.lang.reflect.Method helper = SpellAbilityAi.class.getDeclaredMethod("hasKnownWinningTokenReturn", Player.class, SpellAbility.class);
        need(java.lang.reflect.Modifier.isPrivate(helper.getModifiers()) && java.lang.reflect.Modifier.isStatic(helper.getModifiers())
                && helper.getReturnType() == boolean.class, "Exact native helper ABI");
        helper.setAccessible(true);
        boolean result = (Boolean) helper.invoke(null, actor, activation(actualCardRef(game, oven), actor, ApiType.Token));
        row.put("postchoice_helper", result); row.put("helper_expected", positive);
        row.put("helper_after_rng", rng()); row.put("helper_after_pool", pool(actor)); row.put("helper_after_view", new ActorBoundary(actor).snapshot(game.getView()));
        if (result != positive) failures.add("TOKEN_RETURN_HELPER_EXPECTATION_MISMATCH");
        row.put("independent_Oven_control_is_manual_not_AI_success", true);
        priority(game, actor, enemy);
        boolean ovenPaid = ComputerUtil.playStack(activation(actualCardRef(game, oven), actor, ApiType.Token), actor, game);
        row.put("actual_manual_Oven_paid", ovenPaid);
        need(ovenPaid && actualCardRef(game, oven).isTapped()
                && actor.getCardsIn(ZoneType.Battlefield).stream().noneMatch(c -> c.getId() == token.getId()), "Native Oven really sacrificed its only own creature, the Rite token");
        row.put("token_in_GY_immediately_after_payment", actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == token.getId()));
        resolve(game);
        row.put("token_in_GY_after_native_SBA", actor.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == token.getId()));
        row.put("after_manual_Oven_native_resolution", state(game, actor, enemy));
        need(!game.isGameOver() && enemy.getLife() == 1 && food(actor).size() == 1 && food(actor).get(0).isToken(), "Native token sacrifice/Oven Food alone does not win");
        if (!positive) {
            need(actor.getCardsIn(ZoneType.Graveyard).stream().noneMatch(c -> c.getName().equals("Cauldron Familiar")), "No native Cat remains in actor graveyard; token cannot return");
            row.put("actual_nonwinning_without_real_Cat", true); row.put("actual_native_actor_win", false);
        } else {
            priority(game, actor, enemy); row.put("rng_before_next_choice", rng());
            List<SpellAbility> next = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
            SpellAbility second = next == null || next.isEmpty() ? null : next.get(0);
            row.put("second_choice", ability(second)); row.put("ordinary_Default_subsequent_callbacks", 1); row.put("rng_after_next_choice", rng());
            boolean selected = second != null && second.getHostCard().getId() == realCat.getId() && second.getApi() == ApiType.ChangeZone;
            row.put("second_AI_selected_real_Cat", selected); row.put("second_manual_control_not_AI_success", !selected);
            boolean paid = ComputerUtil.playStack(selected ? second : activation(actualCardRef(game, realCat), actor, ApiType.ChangeZone), actor, game);
            row.put("actual_real_Cat_return_paid", paid); need(paid, "Original non-token Cat pays actual generated Food sacrifice"); resolve(game);
            boolean won = game.isGameOver() && actor.hasWon() && enemy.hasLost(); row.put("actual_native_actor_win", won);
            need(won && food(actor).isEmpty(), "Native real Cat return genuinely wins");
            if (!selectedOven) failures.add("POSITIVE_INITIAL_DEFAULT_MISSED_OVEN");
            if (!selected) failures.add("POSITIVE_NEXT_DEFAULT_MISSED_REAL_CAT");
        }
        row.putIfAbsent("ordinary_Default_subsequent_callbacks", 0);
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife()); row.put("native_game_over", game.isGameOver());
        row.put("rng_after_outcome", rng()); row.put("failures", failures); row.put("status", failures.isEmpty() ? "PASS" : "REGRESSION_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private report directory"); Path out = Path.of(args[0]); need(Files.isDirectory(out), "Runner-created report directory");
        MyRandom.setRandom(new Random(2026110701L)); NativeRiteTokenReturn4 audit = new NativeRiteTokenReturn4(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, callbacks = 0;
        for (boolean positive : List.of(false, true)) for (int seat = 0; seat < 2; seat++) {
            String scene = positive ? "OwnRealCatGY" : "NoRealGY";
            Map<String,Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", 2026110701L, "label", "INTERNAL-PROTOCOL"));
            try { audit.check(seat, positive, row); if (row.get("status").equals("PASS")) pass++; else red++; }
            catch (Throwable error) { errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName()); row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err); }
            callbacks += ((Number)row.getOrDefault("ordinary_Default_initial_callbacks", 0)).intValue();
            Files.writeString(out.resolve(scene+"-seat"+seat+".private.json"), JSON.toJson(row)+"\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String,Object> summary = new LinkedHashMap<>();
        summary.put("label", "INTERNAL-PROTOCOL-PAID-RITE-TOKEN-RETURN4"); summary.put("total", 4); summary.put("pass", pass); summary.put("regression_red", red); summary.put("harness_errors", errors);
        summary.put("ordinary_Default_initial_callbacks", callbacks); summary.put("natural_games", 0); summary.put("expert_games", 0); summary.put("RNG_purity_asserted", false);
        summary.put("token_or_clone_flags_mutated", false); summary.put("manual_controls_are_AI_successes", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary)+"\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
