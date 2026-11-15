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

public final class NativeTokenReturnProtocol10 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final List<String> SCENES = List.of(
            "CommaSelfFirst", "CommaSelfLast", "TypedFutureSorcery", "SnowOrdinaryMana", "ResourcePayoffDepletion");
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
    private static SpellAbility back(Card cat, Player actor) {
        SpellAbility value = cat.getSpellAbilities().stream()
                .filter(s -> s.isActivatedAbility() && s.getApi() == ApiType.ChangeZone).findFirst().orElseThrow();
        value.setActivatingPlayer(actor);
        return value;
    }
    private static void producerMetadata(SpellAbility producer, String cost) {
        producer.getMapParams().put("Cost", cost);
        producer.getMapParams().put("TokenAmount", "1");
        producer.setPayCosts(new forge.game.cost.Cost(cost, true));
    }
    private static forge.game.trigger.Trigger observer(Card card, String valid, String body) {
        forge.game.trigger.Trigger trigger = card.getTriggers().get(0);
        trigger.getMapParams().put("Origin", "Any");
        trigger.getMapParams().put("Destination", "Battlefield");
        trigger.getMapParams().put("ValidCard", valid);
        trigger.getMapParams().put("TriggerDescription", "TEST-ONLY internal observer metadata");
        SpellAbility effective = forge.game.ability.AbilityFactory.getAbility(body, card);
        effective.setActivatingPlayer(card.getController());
        trigger.setOverridingAbility(effective);
        return trigger;
    }
    private static String pool(Player actor) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (var mana : actor.getManaPool()) rows.add(Map.of("color", mana.getColor(),
                "source", mana.getSourceCard() == null ? -1 : mana.getSourceCard().getId()));
        return JSON.toJson(rows);
    }
    private void check(long seed, int seat, String scene, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(seed)); // Once before this fixture; never reset afterward.
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("internal-token-return-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Witch's Oven", 1); deck.getMain().add("Cauldron Familiar", 1);
                deck.getMain().add("Blood Artist", 1); deck.getMain().add("Swamp", 57);
            } else { deck.getMain().add("Blood Artist", 1); deck.getMain().add("Mountain", 59); }
            LobbyPlayerAi lobby = new LobbyPlayerAi("protocol-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-PROTOCOL-TOKEN-RETURN10"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getAllCards().size() == 60 && player.getRegisteredPlayer().getDeck().getMain().countAll() == 60,
                    "Complete actual registered60 original inventories");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor);
        game.getPhaseHandler().onStackResolved();
        Card oven = pose(actor, "Witch's Oven"), cat = pose(actor, "Cauldron Familiar");
        Card swamp = pose(actor, "Swamp"); pose(actor, "Swamp");
        resolve(game);
        boolean comma = scene.startsWith("Comma"), future = scene.equals("TypedFutureSorcery"), snow = scene.equals("SnowOrdinaryMana");
        Card watcher = null;
        forge.game.trigger.Trigger watchedTrigger = null;
        SpellAbility producer = ovenActivation(oven, actor);
        if (comma) {
            watcher = pose(enemy, "Blood Artist"); resolve(game);
            String valid = scene.equals("CommaSelfFirst") ? "Card.Self,Artifact.Other" : "Artifact.Other,Card.Self";
            watchedTrigger = observer(watcher, valid, "DB$ GainLife | Defined$ You | LifeAmount$ 1");
            row.put("test_only_observer_valid", valid);
            row.put("test_only_effective_API", watchedTrigger.getOverridingAbility().getApi().name());
        } else {
            // Trusted native-zone fixture pose, not a paid canonical gameplay claim.
            cat = game.getAction().moveToGraveyard(cat, null); resolve(game);
            producerMetadata(producer, snow ? "S T" : "T");
            row.put("test_only_producer_cost", snow ? "S T" : "T");
            row.put("test_only_producer_token_amount", "1");
        }
        SpellAbility returning = back(cat, actor);
        if (future) {
            Map<String, String> before = new LinkedHashMap<>(returning.getMapParams());
            returning.getRestrictions().setSorcerySpeed(true);
            need(before.equals(returning.getMapParams()), "SorcerySpeed mutated only the typed restriction, not MapParams");
            game.getPhaseHandler().devModeSet(PhaseType.END_OF_TURN, enemy);
            game.getPhaseHandler().onStackResolved();
            row.put("typed_future_sorcery_only_no_MapParams_change", true);
            row.put("actual_turn_owner", enemy.getId());
            row.put("actual_phase", PhaseType.END_OF_TURN.name());
        }
        if (scene.equals("ResourcePayoffDepletion")) {
            watcher = pose(actor, "Blood Artist"); resolve(game);
            watcher.getCurrentState().setType(new forge.card.CardType(List.of("Artifact", "Food"), false));
            need(watcher.getType().hasSubtype("Food") && !watcher.isCreature(), "Test-only typed Food payoff permanent");
            watchedTrigger = observer(watcher, "Creature.YouCtrl", "DB$ LoseLife | Defined$ Player.Opponent | LifeAmount$ 1");
            returning.getMapParams().put("Cost", "Sac<2/Food>");
            returning.setPayCosts(new forge.game.cost.Cost("Sac<2/Food>", true));
            row.put("test_only_payoff_card", watcher.getId());
            row.put("test_only_return_cost", "Sac<2/Food>");
        }
        actor.setLife(5, null); enemy.setLife(scene.equals("ResourcePayoffDepletion") ? 2 : 1, null);
        game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && !oven.isTapped(), "Settled nonterminal frontier");
        need(food(actor).size() == (scene.equals("ResourcePayoffDepletion") ? 1 : 0), "Exact initial native resource count");
        Method helper = SpellAbilityAi.class.getDeclaredMethod("hasKnownWinningTokenReturn", Player.class, SpellAbility.class);
        need(helper.getReturnType() == boolean.class && Modifier.isPrivate(helper.getModifiers()) && Modifier.isStatic(helper.getModifiers()),
                "Exact private token-return helper ABI");
        helper.setAccessible(true);
        String rngBefore = rng(), poolBefore = pool(actor), viewBefore = JSON.toJson(new ActorBoundary(actor).snapshot(game.getView()));
        boolean certificate = (Boolean) helper.invoke(null, actor, producer);
        need(rngBefore.equals(rng()) && poolBefore.equals(pool(actor))
                && viewBefore.equals(JSON.toJson(new ActorBoundary(actor).snapshot(game.getView()))),
                "Helper query must not mutate RNG, pool, or actor-visible state");
        row.put("before_actor_view", viewBefore); row.put("rng_before_helper", rngBefore);
        row.put("helper_result", certificate); row.put("expected_helper_result", false);
        row.put("helper_query_state_pure", true); row.put("ordinary_AI_callbacks", 0);
        if (snow) {
            need(!swamp.getType().isSnow() && !actor.getManaPool().iterator().hasNext(),
                    "Only ordinary basic mana, no floating or snow resource");
            SpellAbility mana = swamp.getManaAbilities().get(0);
            forge.game.mana.Mana ordinary = new forge.game.mana.Mana(forge.card.MagicColor.BLACK, swamp, mana.getManaPart(), actor);
            need(!ordinary.isSnow(), "Actual native mana source is nonsnow");
            forge.game.mana.ManaCostBeingPaid cost = new forge.game.mana.ManaCostBeingPaid(producer.getPayCosts().getCostMana().getMana());
            need(!cost.isNeeded(ordinary, actor.getManaPool()), "Native object-based mana admission rejects ordinary mana for S");
            row.put("native_ordinary_mana_rejected_for_snow", true);
        } else {
            boolean paid = ComputerUtil.playStack(producer, actor, game);
            need(paid, "Native postquery producer control must actually pay"); resolve(game);
            row.put("native_producer_paid", true);
            if (comma) {
                need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Actual native Food token produced");
                need(watchedTrigger.matchesValidParam("ValidCard", food(actor).get(0)), "Native selector matches Food in both union orders");
                need(enemy.getLife() == 2, "Unknown opposing GainLife actually runs on Food entry");
                Card grave = actor.getCardsIn(ZoneType.Graveyard).stream().filter(c -> c.getName().equals("Cauldron Familiar")).findFirst().orElseThrow();
                need(ComputerUtil.playStack(back(grave, actor), actor, game), "Real canonical Food payment and Cat return"); resolve(game);
                need(!game.isGameOver() && enemy.getLife() == 1, "Native composed line is nonterminal, not a claimed win");
                row.put("native_unknown_union_trigger_ran", true);
                row.put("native_control_nonterminal", true);
            } else if (future) {
                need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Actual Food exists for return cost");
                need(returning.getRestrictions().isSorcerySpeed(), "Typed restriction remains installed on the existing graveyard ability");
                need(!returning.getRestrictions().canPlay(cat, returning), "Native future admission denies sorcery-only activation on opponent end step");
                row.put("native_future_admission_denied", true);
            } else {
                need(food(actor).size() == 2 && food(actor).stream().anyMatch(Card::isToken), "Exactly one existing payoff Food plus one real new Food");
                need(returning.getPayCosts().getCostParts().size() == 1, "Return has only the declared two-Food sacrifice cost");
                need(ComputerUtil.playStack(returning, actor, game), "Actual native return must consume both Food resources"); resolve(game);
                need(food(actor).isEmpty() && !game.isGameOver() && enemy.getLife() == 1,
                        "Consumed payoff source no longer drains; actual return is nonterminal");
                row.put("native_both_resources_consumed", true);
                row.put("native_control_nonterminal", true);
            }
        }
        row.put("enemy_life_after_control", enemy.getLife());
        row.put("canonical_card_or_gameplay_claim", false);
        row.put("status", certificate ? "PROTOCOL_RED" : "PASS");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh internal-protocol report directory");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110740L));
        NativeTokenReturnProtocol10 audit = new NativeTokenReturnProtocol10(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, index = 0;
        for (String scene : SCENES) {
            long seed = 2026110741L + index++;
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>(Map.of("label", "INTERNAL-PROTOCOL", "scene", scene, "seat", seat, "seed", seed));
                try { audit.check(seed, seat, scene, row); if (row.get("status").equals("PASS")) pass++; else red++; }
                catch (Throwable error) { errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                    row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err); }
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW);
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "INTERNAL-PROTOCOL-TOKEN-RETURN10"); summary.put("total", 10);
        summary.put("pass", pass); summary.put("protocol_red", red); summary.put("harness_errors", errors);
        summary.put("ordinary_AI_callbacks", 0); summary.put("natural_games", 0); summary.put("canonical_card_or_gameplay_claim", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
