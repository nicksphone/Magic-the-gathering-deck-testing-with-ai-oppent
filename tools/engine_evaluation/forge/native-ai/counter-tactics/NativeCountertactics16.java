// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled fixtures using complete Card-Forge 61e9442 native programs; not natural games.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.deck.Deck;
import forge.game.*;
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
import java.util.*;

public final class NativeCountertactics16 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long[] SEEDS = {2026110601L, 2026110602L, 2026110603L, 2026110604L};
    private static void need(boolean condition, String message) {
        if (!condition) throw new IllegalStateException("HARNESS: " + message);
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
    private static Map<String, Integer> registered(Player player) {
        Map<String, Integer> counts = new TreeMap<>();
        for (var entry : player.getRegisteredPlayer().getDeck().getMain())
            counts.merge(entry.getKey().getName(), entry.getValue(), Integer::sum);
        return counts;
    }
    private static Map<String, Integer> physical(Player player) {
        Map<String, Integer> counts = new TreeMap<>();
        for (Card card : player.getAllCards()) counts.merge(card.getPaperCard().getName(), 1, Integer::sum);
        return counts;
    }
    private static Map<String, Object> ability(SpellAbility spell) {
        if (spell == null) return Map.of("choice", "PASS");
        List<Integer> spells = new ArrayList<>(), players = new ArrayList<>();
        for (SpellAbility target : spell.getTargets().getTargetSpells()) spells.add(target.getId());
        for (Player target : spell.getTargets().getTargetPlayers()) players.add(target.getId());
        return Map.of("source", spell.getHostCard().getName(), "source_id", spell.getHostCard().getId(),
                "spell_ability_id", spell.getId(), "api", String.valueOf(spell.getApi()),
                "is_spell", spell.isSpell(), "target_spell_ids", spells, "target_player_ids", players);
    }
    private static List<Map<String, Object>> stack(Game game) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (var item : game.getStack()) {
            Map<String, Object> row = new LinkedHashMap<>(ability(item.getSpellAbility()));
            row.put("native_stack_id", item.getId()); rows.add(row);
        }
        return rows;
    }
    private static Card take(Player player, String name) {
        Card card = player.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        return player.getGame().getAction().moveToHand(card, null);
    }
    private static Card pose(Player player, String name) {
        Card card = player.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        return player.getGame().getAction().moveToPlay(card, player, null, forge.game.ability.AbilityKey.newMap());
    }
    private static SpellAbility spell(Card card, Player player) {
        SpellAbility spell = card.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
        spell.setActivatingPlayer(player); return spell;
    }
    private static SpellAbility top(Game game) { return game.getStack().iterator().next().getSpellAbility(); }
    private static long tapped(List<Card> lands) { return lands.stream().filter(Card::isTapped).count(); }
    private static void resolve(Game game) {
        int count = 0;
        while (!game.getStack().isEmpty() && !game.isGameOver() && count++ < 8) {
            game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
        }
        need(game.getStack().isEmpty() || game.isGameOver(), "Bounded actual stack resolution");
    }

    private void check(long seed, int seat, String scene, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(seed)); // Once before this fresh fixture, never reset after construction.
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("declared-countertactics-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Counterspell", 1); deck.getMain().add("Opt", 1);
                deck.getMain().add("Craw Wurm", 1); deck.getMain().add("Island", 57);
            } else {
                deck.getMain().add("Lightning Bolt", 1); deck.getMain().add("Supreme Verdict", 1);
                deck.getMain().add("Vexing Shusher", 1); deck.getMain().add("Mountain", 53);
                deck.getMain().add("Plains", 2); deck.getMain().add("Island", 1); deck.getMain().add("Forest", 1);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("countertactics-seat-" + index, null);
            lobby.setAiProfile("Default"); players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-COUNTERTACTICS16"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60
                    && player.getAllCards().size() == 60 && registered(player).equals(physical(player)), "Full registered60 physical originals");
        }
        actor.setLife(3, null); enemy.setLife(20, null);
        boolean friendly = scene.equals("FriendlyOpt"), verdict = scene.equals("SupremeVerdict"), shusher = scene.equals("ShusherLowerBolt");
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, friendly ? actor : enemy);
        game.getPhaseHandler().onStackResolved();
        Card counter = take(actor, "Counterspell");
        List<Card> ownLands = new ArrayList<>(), enemyLands = new ArrayList<>();
        int ownCount = scene.equals("UnfundedBolt") ? 1 : friendly ? 3 : 2;
        for (int i = 0; i < ownCount; i++) ownLands.add(pose(actor, "Island"));
        if (verdict) {
            pose(actor, "Craw Wurm");
            for (String name : List.of("Plains", "Plains", "Island", "Mountain")) enemyLands.add(pose(enemy, name));
        } else for (int i = 0; i < (shusher ? 4 : 1); i++) enemyLands.add(pose(enemy, "Mountain"));
        game.getAction().checkStateEffects(true);
        Card shusherCard = null;
        if (shusher) {
            SpellAbility cast = spell(take(enemy, "Vexing Shusher"), enemy);
            need(ComputerUtil.playStack(cast, enemy, game) && game.getStack().size() == 1 && tapped(enemyLands) == 2,
                    "Real paid Shusher spell before the lethal response position");
            resolve(game);
            shusherCard = enemy.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Vexing Shusher")).findFirst().orElseThrow();
        }
        Player caster = friendly ? actor : enemy;
        String pendingName = friendly ? "Opt" : verdict ? "Supreme Verdict" : "Lightning Bolt";
        SpellAbility pending = spell(take(caster, pendingName), caster);
        if (!friendly && !verdict) pending.getTargets().add(actor);
        need(ComputerUtil.playStack(pending, caster, game) && game.getStack().size() == 1, "Actual paid pending canonical spell");
        pending = top(game);
        need(pending.getHostCard().isInZone(ZoneType.Stack) && pending.getActivatingPlayer() == caster, "Native stack spell association");
        need(tapped(ownLands) == (friendly ? 1 : 0) && actor.getManaPool().totalMana() == 0,
                "Actor exactly UU funded, or single-U negative, after actual Opt payment");
        need(tapped(enemyLands) == (friendly ? 0 : verdict ? 4 : shusher ? 3 : 1), "Actual opponent spell mana payment");
        if (shusher) {
            SpellAbility activation = shusherCard.getSpellAbilities().stream()
                    .filter(sa -> sa.isActivatedAbility() && sa.getApi() == ApiType.Effect).findFirst().orElseThrow();
            activation.setActivatingPlayer(enemy); activation.getTargets().add(pending);
            need(ComputerUtil.playStack(activation, enemy, game) && game.getStack().size() == 2 && tapped(enemyLands) == 4,
                    "Actual paid Shusher activation above actual paid Bolt");
            need(!top(game).isSpell() && top(game).getTargets().getFirstTargetedSpell().getId() == pending.getId(),
                    "Unresolved protection activation targets the lower Bolt");
        }
        game.getAction().checkStateEffects(true);
        game.getPhaseHandler().setPriority(actor); actor.setHasPriority(true); enemy.setHasPriority(false);
        need(!game.isGameOver() && actor.getLife() == 3 && counter.isInZone(ZoneType.Hand)
                && actor.getCardsIn(ZoneType.Hand).size() == 1, "Genuine nonterminal one-counter response position");
        if (!friendly && !verdict) need(pending.getTargets().contains(actor), "Actual lethal Bolt targets the three-life actor");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Unmodified ordinary Default controller");
        row.put("registered_actor", registered(actor)); row.put("registered_enemy", registered(enemy));
        row.put("before_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("paid_setup_actor_lands", tapped(ownLands)); row.put("paid_setup_enemy_lands", tapped(enemyLands));
        row.put("native_stack_before_choice", stack(game)); row.put("rng_before_choice", rng());
        long started = System.nanoTime();
        // FIRST AND ONLY ordinary Default response callback; no prior counter/affordability/target probes.
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("choice_elapsed_ms", (System.nanoTime() - started) / 1_000_000.0);
        row.put("first_choice", ability(chosen)); row.put("first_choice_list_size", choices == null ? 0 : choices.size());
        row.put("rng_after_first_choice", rng()); row.put("ordinary_Default_callbacks", 1);
        row.put("actor_view_after_first_choice", new ActorBoundary(actor).snapshot(game.getView()));

        // Diagnostics begin only after the immutable first-choice record above.
        SpellAbility diagnostic = spell(counter, actor);
        boolean affordable = ComputerUtilCost.canPayCost(diagnostic, actor, false);
        boolean targetable = diagnostic.canTargetSpellAbility(pending);
        boolean counterable = pending.isCounterableBy(diagnostic);
        row.put("diagnostic_affordable", affordable); row.put("diagnostic_pending_targetable", targetable);
        row.put("diagnostic_pending_counterable", counterable);
        need(affordable != scene.equals("UnfundedBolt"), "Declared actor mana precondition");
        need(counterable != verdict && targetable, "Canonical counterable/uncounterable target semantics");
        boolean expectCounter = scene.equals("LethalBolt") || shusher;
        List<String> policy = new ArrayList<>();
        boolean choseCounter = chosen != null && chosen.getHostCard().getId() == counter.getId() && chosen.getApi() == ApiType.Counter;
        boolean choseLower = choseCounter && chosen.getTargets().getFirstTargetedSpell() != null
                && chosen.getTargets().getFirstTargetedSpell().getId() == pending.getId();
        if (expectCounter && !choseLower) policy.add("Strict lethal response did not choose Counterspell targeting the actual Bolt");
        if (!expectCounter && chosen != null) policy.add("Required decline control selected a response");
        row.put("expected_counter", expectCounter); row.put("selected_counter_executed", false);
        if (chosen != null) {
            if (choseCounter) {
                long beforePaid = tapped(ownLands);
                boolean paid = ComputerUtil.playStack(chosen, actor, game);
                row.put("selected_counter_executed", paid); row.put("selected_counter_new_lands_tapped", tapped(ownLands) - beforePaid);
                if (!paid || tapped(ownLands) - beforePaid != 2) policy.add("Selected counter did not genuinely pay UU and enter stack");
                if (paid) resolve(game);
                if (expectCounter && choseLower && (actor.getLife() != 3 || game.isGameOver()
                        || !pending.getHostCard().isInZone(ZoneType.Graveyard))) policy.add("Native chosen counter did not preserve actor and remove the Bolt");
            } else policy.add("First choice selected an unexpected noncounter action; not executed by harness");
        } else if (shusher) {
            // Explicit manual legal counter CONTROL after the recorded decline; never an AI pass.
            diagnostic.resetTargets(); diagnostic.getTargets().add(pending);
            long beforePaid = tapped(ownLands);
            boolean paid = ComputerUtil.playStack(diagnostic, actor, game);
            need(paid && tapped(ownLands) - beforePaid == 2, "Manual post-choice lower-Bolt counter must really pay UU");
            resolve(game);
            need(actor.getLife() == 3 && !game.isGameOver() && pending.getHostCard().isInZone(ZoneType.Graveyard),
                    "Manual control demonstrates native lower-Bolt save before Shusher protection");
            row.put("manual_post_choice_lower_bolt_control", Map.of("paid_UU", true, "actor_life", actor.getLife(), "counts_as_AI_pass", false));
        } else if (!friendly) {
            resolve(game);
            if (!verdict) need(actor.hasLost() && actor.getLife() <= 0 && game.isGameOver(), "Unanswered actual Bolt resolves lethally");
            row.put("controlled_resolution_not_natural_game", true);
        }
        row.put("actor_life_after", actor.getLife()); row.put("native_actor_lost", actor.hasLost());
        row.put("native_game_over", game.isGameOver()); row.put("policy_failed", policy);
        row.put("rng_after_diagnostics_and_resolution", rng());
        row.put("status", policy.isEmpty() ? "PASS" : "POLICY_RED");
    }

    public static void main(String[] args) throws Exception {
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEEDS[0]));
        NativeCountertactics16 audit = new NativeCountertactics16(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        List<Map<String, Object>> cases = new ArrayList<>();
        for (long seed : SEEDS) for (int seat = 0; seat < 2; seat++)
            cases.add(new LinkedHashMap<>(Map.of("seed", seed, "seat", seat, "scene", "LethalBolt")));
        String[] extras = {"UnfundedBolt", "SupremeVerdict", "FriendlyOpt", "ShusherLowerBolt"};
        for (int index = 0; index < extras.length; index++) for (int seat = 0; seat < 2; seat++)
            cases.add(new LinkedHashMap<>(Map.of("seed", SEEDS[index], "seat", seat, "scene", extras[index])));
        need(cases.size() == 16, "Exactly sixteen predeclared cases");
        int passed = 0, red = 0, errors = 0, index = 0;
        for (Map<String, Object> row : cases) {
            String id = String.format("case%02d", ++index); row.put("case_id", id);
            try {
                audit.check(((Number) row.get("seed")).longValue(), (int) row.get("seat"), (String) row.get("scene"), row);
                if (row.get("status").equals("PASS")) passed++; else red++;
            } catch (Throwable error) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
            }
            Files.writeString(out.resolve(id + ".private.json"), JSON.toJson(row) + "\n");
            System.out.println("@@COUNTERTACTICS16 " + JSON.toJson(Map.of("case_id", id, "scene", row.get("scene"), "seat", row.get("seat"), "status", row.get("status"))));
            System.out.flush();
        }
        Map<String, Object> summary = Map.of("label", "CONTROLLED-NATIVE-COUNTERTACTICS16-BASELINE",
                "total", 16, "pass", passed, "policy_red", red, "harness_errors", errors,
                "natural_games", 0, "ordinary_Default_choices", cases.stream().filter(r -> r.containsKey("first_choice")).count(),
                "seed_search_or_late_RNG_reset", false, "RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary));
        System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
