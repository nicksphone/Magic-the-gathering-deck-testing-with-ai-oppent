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

public final class NativeCounterWorship2 extends AITest {
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

    private void check(int seat, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(2026110601L));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("registered-Worship-protocol-seat-" + index);
            if (index == seat) {
                deck.getMain().add("Counterspell", 1); deck.getMain().add("Worship", 1);
                deck.getMain().add("Craw Wurm", 1); deck.getMain().add("Island", 57);
            } else { deck.getMain().add("Lightning Bolt", 1); deck.getMain().add("Mountain", 59); }
            LobbyPlayerAi lobby = new LobbyPlayerAi("Worship-protocol-seat-" + index, null);
            lobby.setAiProfile("Default"); players.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(players, rules, new Match(rules, players, "CONTROLLED-WORSHIP-LIFE-REDUCED-PROTOCOL"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false); game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getAllCards().size() == 60 && registered(player).equals(physical(player)), "Full registered/materialized60 canonical originals");
        }
        actor.setLife(3, null); enemy.setLife(20, null);
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, enemy); game.getPhaseHandler().onStackResolved();
        Card counter = take(actor, "Counterspell"); List<Card> lands = new ArrayList<>();
        lands.add(pose(actor, "Island")); lands.add(pose(actor, "Island"));
        Card worship = pose(actor, "Worship"), wurm = pose(actor, "Craw Wurm");
        Card mountain = pose(enemy, "Mountain");
        game.getAction().checkStateEffects(true);
        need(worship.isInPlay() && wurm.isInPlay() && wurm.getController() == actor
                && worship.getView().canBeShownTo(actor.getView()) && actor.getCreaturesInPlay().size() == 1,
                "Actual public canonical Worship with controlled creature, not keyword/life-limit injection");
        SpellAbility cast = spell(take(enemy, "Lightning Bolt"), enemy); cast.getTargets().add(actor);
        need(ComputerUtil.playStack(cast, enemy, game) && mountain.isTapped() && game.getStack().size() == 1,
                "Opponent genuinely pays R for native Bolt targeting the three-life actor");
        SpellAbility pending = top(game); int boltId = pending.getHostCard().getId();
        need(pending.getTargets().contains(actor) && actor.getLife() == 3 && !game.isGameOver()
                && tapped(lands) == 0 && actor.getManaPool().totalMana() == 0
                && counter.isInZone(ZoneType.Hand) && actor.getCardsIn(ZoneType.Hand).size() == 1,
                "Actual lethal-looking pending Bolt and funded UU response");
        game.getPhaseHandler().setPriority(actor); actor.setHasPriority(true); enemy.setHasPriority(false);
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Ordinary unmodified Default controller");
        Map<String, Object> observation = new LinkedHashMap<>();
        observation.put("actor_input", new ActorBoundary(actor).snapshot(game.getView()));
        observation.put("native_stack_input", stack(game)); observation.put("incoming_rng_serialized", rng());
        // First and only Default response before helper, target/cost or replacement diagnostics.
        List<SpellAbility> selected = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = selected == null || selected.isEmpty() ? null : selected.get(0);
        observation.put("first_choice", ability(chosen)); observation.put("ending_rng_serialized", rng());
        row.put("ordinary_choice_observation", observation); row.put("ordinary_Default_callbacks", 1);
        row.put("no_forced_ordinary_decline_expectation", true);
        boolean targetLegal = pending.canTarget(actor, true);
        row.put("actual_Bolt_target_legal", targetLegal);
        row.put("actor_can_lose_life", actor.canLoseLife()); row.put("actor_cannot_lose_for_life", actor.cantLoseForZeroOrLessLife());
        need(targetLegal && ComputerUtilCost.canPayCost(spell(counter, actor), actor, false), "Legal native Bolt target and genuinely funded counter");
        java.lang.reflect.Method helper = forge.ai.ability.CounterAi.class.getDeclaredMethod(
                "isCriticalDamageTarget", Player.class, SpellAbility.class);
        helper.setAccessible(true);
        boolean critical = (Boolean) helper.invoke(new forge.ai.ability.CounterAi(), actor, pending);
        row.put("candidate_helper_isCriticalDamageTarget", critical);
        row.put("native_damage_forecast_after_choice", ComputerUtilCombat.predictDamageTo(actor, 3, pending.getHostCard(), false));
        List<String> failed = new ArrayList<>();
        if (critical) failed.add("Critical-damage helper ignores actual Worship LifeReduced replacement");
        // Protocol ground truth: intentionally leave the ordinary response unexecuted.
        need(game.getStack().size() == 1 && tapped(lands) == 0 && counter.isInZone(ZoneType.Hand),
                "No counter cast or paid response before genuine uncountered Bolt control");
        game.getStack().resolveStack(); game.getAction().checkStateEffects(true);
        need(actor.getLife() == 1 && !actor.hasLost() && !game.isGameOver() && game.getStack().isEmpty()
                && worship.isInPlay() && wurm.isInPlay()
                && enemy.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == boltId),
                "Native Worship replacement leaves actor at1 after actual uncountered Bolt");
        row.put("recorded_choice_executed", false); row.put("actor_life_after", actor.getLife());
        row.put("actual_life_lost", 2); row.put("life_loss_is_not_damage_dealt_claim", true);
        row.put("controlled_internal_protocol_not_natural_game", true);
        row.put("protocol_failed", failed); row.put("status", failed.isEmpty() ? "PASS" : "PROTOCOL_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 2 && args[1].equals("candidate"), "Candidate-only internal Worship protocol");
        Path out = Path.of(args[0]); MyRandom.setRandom(new Random(2026110601L));
        NativeCounterWorship2 audit = new NativeCounterWorship2(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0;
        for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>(Map.of("seat", seat, "seed", 2026110601L, "scene", "NativeWorshipLifeReduced"));
            try { audit.check(seat, row); if (row.get("status").equals("PASS")) pass++; else red++; }
            catch (Throwable error) { errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName()); row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err); }
            Files.writeString(out.resolve("seat" + seat + ".private.json"), JSON.toJson(row) + "\n");
            System.out.println(JSON.toJson(Map.of("seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = Map.of("label", "SEPARATE-NATIVE-WORSHIP-CRITICAL-DAMAGE-PROTOCOL2", "total", 2,
                "pass", pass, "protocol_red", red, "harness_errors", errors, "candidate_only_internal_protocol", true,
                "forced_ordinary_decline_assertion", false, "natural_games", 0);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
