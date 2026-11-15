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

public final class NativeCounterTargetLegality2 extends AITest {
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

    private void check(int seat, boolean candidate, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(2026110601L));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("registered-shroud-protocol-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Counterspell", 1); deck.getMain().add("Gilded Light", 1);
                deck.getMain().add("Island", 57); deck.getMain().add("Plains", 1);
            } else { deck.getMain().add("Lightning Bolt", 1); deck.getMain().add("Mountain", 59); }
            LobbyPlayerAi lobby = new LobbyPlayerAi("shroud-protocol-seat-" + index, null);
            lobby.setAiProfile("Default"); players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-PAID-GL-STALE-BOLT-TARGET"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false); game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getAllCards().size() == 60 && registered(player).equals(physical(player)), "Registered/materialized60 full canonical originals");
        }
        actor.setLife(3, null); enemy.setLife(20, null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, enemy); game.getPhaseHandler().onStackResolved();
        List<Card> ownLands = new ArrayList<>();
        for (int i = 0; i < 3; i++) ownLands.add(pose(actor, "Island"));
        Card plains = pose(actor, "Plains"); ownLands.add(plains);
        Card mountain = pose(enemy, "Mountain"), counter = take(actor, "Counterspell");
        Card lightCard = take(actor, "Gilded Light");
        SpellAbility bolt = spell(take(enemy, "Lightning Bolt"), enemy); bolt.getTargets().add(actor);
        need(ComputerUtil.playStack(bolt, enemy, game) && mountain.isTapped() && game.getStack().size() == 1,
                "Actual paid Bolt targeted actor before protection");
        bolt = top(game); int boltId = bolt.getHostCard().getId();
        SpellAbility light = spell(lightCard, actor);
        need(ComputerUtil.playStack(light, actor, game) && game.getStack().size() == 2
                && tapped(ownLands) == 2 && plains.isTapped(), "Actual Gilded Light pays1W above Bolt");
        need(top(game).getHostCard().getName().equals("Gilded Light"), "Resolve only actual top Gilded Light");
        game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
        need(game.getStack().size() == 1 && top(game).getId() == bolt.getId()
                && top(game).getTargets().contains(actor) && actor.getLife() == 3 && !game.isGameOver(),
                "Bolt retains recorded target after actual Gilded Light resolution");
        need(ownLands.stream().filter(c -> c.getName().equals("Island") && !c.isTapped()).count() == 2
                && actor.getManaPool().totalMana() == 0 && actor.getCardsIn(ZoneType.Hand).size() == 1
                && counter.isInZone(ZoneType.Hand), "Actual1W payment leaves funded UU and only Counterspell in hand");
        game.getPhaseHandler().setPriority(actor); actor.setHasPriority(true); enemy.setHasPriority(false);
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Unmodified ordinary Default");
        Map<String, Object> ordinary = new LinkedHashMap<>();
        ordinary.put("actor_input", new ActorBoundary(actor).snapshot(game.getView())); ordinary.put("stack_input", stack(game));
        ordinary.put("incoming_rng_serialized", rng());
        // Sole actual Default response before helper, target-legality, or cost diagnostics.
        List<SpellAbility> selected = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = selected == null || selected.isEmpty() ? null : selected.get(0);
        ordinary.put("first_choice", ability(chosen)); ordinary.put("ending_rng_serialized", rng());
        row.put("ordinary_choice_observation", ordinary); row.put("ordinary_Default_callbacks", 1);
        row.put("no_forced_decline_golden", true);
        boolean legalNow = actor.canBeTargetedBy(bolt);
        row.put("actual_pending_Bolt_target_legal_now", legalNow); row.put("recorded_target_still_present", bolt.getTargets().contains(actor));
        need(!legalNow, "Real resolved Gilded Light makes actual Bolt target illegal");
        need(ComputerUtilCost.canPayCost(spell(counter, actor), actor, false), "Counterspell remains genuinely funded after GL");
        List<String> failed = new ArrayList<>();
        row.put("candidate_helper_assertion_applicable", candidate);
        if (candidate) {
            java.lang.reflect.Method helper = forge.ai.ability.CounterAi.class.getDeclaredMethod(
                    "isCriticalDamageTarget", Player.class, SpellAbility.class);
            helper.setAccessible(true);
            boolean critical = (Boolean) helper.invoke(new forge.ai.ability.CounterAi(), actor, bolt);
            row.put("candidate_helper_isCriticalDamageTarget", critical);
            if (critical) failed.add("Candidate helper calls an actually illegal stale player target critical");
        }
        // This protocol control intentionally does not execute the recorded counter choice.
        // It resolves the genuine UNCOUNTERED Bolt to measure the target-legality ground truth.
        need(game.getStack().size() == 1 && counter.isInZone(ZoneType.Hand) && tapped(ownLands) == 2,
                "No counter cast or forged response before uncountered Bolt control");
        game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
        need(actor.getLife() == 3 && !game.isGameOver() && !actor.hasLost() && game.getStack().isEmpty()
                && enemy.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == boltId),
                "Actual uncountered Bolt fizzles with zero damage after shroud");
        row.put("recorded_choice_executed", false); row.put("actual_uncountered_Bolt_damage", 0);
        row.put("actor_life_after", actor.getLife()); row.put("controlled_protocol_not_natural_game", true);
        row.put("protocol_failed", failed); row.put("status", failed.isEmpty() ? "PASS" : "PROTOCOL_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 2 && (args[1].equals("baseline") || args[1].equals("candidate")), "Explicit baseline-observation or candidate-protocol epoch");
        boolean candidate = args[1].equals("candidate"); Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110601L));
        NativeCounterTargetLegality2 audit = new NativeCounterTargetLegality2(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0;
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>(Map.of("seat", seat, "seed", 2026110601L, "scene", "RealPaidGildedLightStaleBolt"));
            try { audit.check(seat, candidate, row); if (row.get("status").equals("PASS")) pass++; else red++; }
            catch (Throwable error) { errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName()); row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err); }
            Files.writeString(out.resolve("seat" + seat + ".private.json"), JSON.toJson(row) + "\n");
            System.out.println(JSON.toJson(Map.of("seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = Map.of("label", "SEPARATE-PAID-GL-TARGET-LEGALITY-PROTOCOL2", "total", 2,
                "pass", pass, "protocol_red", red, "harness_errors", errors, "candidate_helper_assertions_applicable", candidate,
                "ordinary_choice_has_no_forced_decline_expectation", true, "natural_games", 0);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
