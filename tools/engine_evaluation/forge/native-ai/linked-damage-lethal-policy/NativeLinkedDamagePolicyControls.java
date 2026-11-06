// SPDX-License-Identifier: GPL-3.0-or-later
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
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.TreeMap;

public final class NativeLinkedDamagePolicyControls extends AITest {
    private record Scene(Game game, Player actor, Player enemy, Card source,
                         Card creature, List<Card> lands) {}

    private static void require(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    private Scene setup(int seat, JsonObject d) {
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
        Game game = new Game(players, rules, new Match(rules, players, "Linked damage design controls"));
        game.setAge(GameStage.Play);
        require(!game.getAIFlatMonteCarlo() && !game.getAIFlatMonteCarloMax()
                && !game.getAIFlatMonteCarloLite(), "Unexpected search mode");
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        actor.setLife(d.get("own_life").getAsInt(), null);
        enemy.setLife(d.get("enemy_life").getAsInt(), null);
        String name = d.get("name").getAsString();
        game.getPhaseHandler().devModeSet(name.equals("infect-activated-boundary") ? PhaseType.MAIN1 : PhaseType.MAIN2, actor);
        game.getPhaseHandler().onStackResolved();
        fillLibrary(actor, 8); fillLibrary(enemy, 8);
        List<Card> lands = new ArrayList<>(addCards("Mountain", 2, actor));
        String creatureName = d.get("creature").getAsString();
        Card creature = creatureName.isEmpty() ? null : addCard(creatureName, enemy);
        if (d.has("enemy_permanent")) addCard(d.get("enemy_permanent").getAsString(), enemy);
        if (d.has("own_permanent")) addCard(d.get("own_permanent").getAsString(), actor);
        boolean activated = name.equals("infect-activated-boundary");
        Card source = addCardToZone(d.get("spell").getAsString(), actor,
                activated ? ZoneType.Battlefield : ZoneType.Hand);
        if (activated) {
            source.setSickness(false);
            addCard("Phyresis", actor).attachToEntity(source, null);
        }
        if (d.get("landfall").getAsBoolean()) {
            Card land = addCardToZone("Mountain", actor, ZoneType.Hand);
            require(actor.canPlayLand(land, false, null), "SETUP: native land play illegal");
            Card entered = actor.playLand(land, null);
            require(entered != null && entered.isInZone(ZoneType.Battlefield), "SETUP: native land entry failed");
            lands.add(entered);
        }
        game.getAction().checkStaticAbilities();
        game.getAction().checkStateEffects(true);
        require(!game.isGameOver() && game.getStack().isEmpty(), "SETUP: not a fresh live empty-stack decision");
        return new Scene(game, actor, enemy, source, creature, lands);
    }

    private Map<String, Object> physical(Scene s) {
        List<Map<String, Object>> players = new ArrayList<>();
        for (Player p : s.game.getPlayers()) {
            List<Map<String, Object>> cards = new ArrayList<>();
            for (ZoneType zone : List.of(ZoneType.Hand, ZoneType.Battlefield, ZoneType.Graveyard,
                    ZoneType.Library, ZoneType.Exile)) for (Card card : p.getCardsIn(zone)) {
                cards.add(Map.of("id", card.getId(), "name", card.getName(), "zone", zone.name(),
                        "tapped", card.isTapped(), "damage", card.getDamage(), "counters", card.getCounters().toString()));
            }
            players.add(Map.of("id", p.getId(), "life", p.getLife(), "mana", p.getManaPool().totalMana(),
                    "counters", p.getCounters().toString(), "cards", cards));
        }
        return Map.of("players", players, "stack_empty", s.game.getStack().isEmpty(), "terminal", s.game.isGameOver());
    }

    private List<Map<String, Object>> chain(SpellAbility root) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (SpellAbility sa = root; sa != null; sa = sa.getSubAbility()) {
            List<String> targets = new ArrayList<>();
            for (var target : sa.getTargets()) targets.add(target instanceof Player p ? "player:"+p.getId()
                    : target instanceof Card c ? "card:"+c.getId() : target.toString());
            result.add(Map.of("api", String.valueOf(sa.getApi()), "params", new TreeMap<>(sa.getMapParams()),
                    "mandatory", sa.isMandatory(), "targets", targets));
        }
        return result;
    }

    private void resolveNative(Scene s, Map<String, Object> row) {
        int resolutions = 0, triggerBatches = 0;
        while (!s.game.isGameOver() && resolutions < 16) {
            // Same SBA/APNAP ordering as the ordinary priority caller, no fresh chooser.
            do {
                s.game.getAction().checkStateEffects(true);
                if (s.game.isGameOver()) break;
                if (++triggerBatches > 24) throw new AssertionError("Native pending triggers did not settle");
            } while (s.game.getStack().addAllTriggeredAbilitiesToStack());
            if (s.game.isGameOver() || s.game.getStack().isEmpty()) break;
            s.game.getStack().resolveStack();
            resolutions++;
        }
        row.put("native_resolutions", resolutions);
        row.put("native_trigger_batches", triggerBatches);
        require(s.game.isGameOver() || (s.game.getStack().isEmpty()
                && !s.game.getStack().hasSimultaneousStackEntries()), "Native resolution bound exceeded");
    }

    private void check(int seat, JsonObject d, Map<String, Object> row) {
        Scene s = setup(seat, d);
        Map<String, Object> before = physical(s);
        row.put("before_choice", before);
        row.put("default_choice_invocations", 1);
        PlayerControllerAi controller = (PlayerControllerAi) s.actor.getController();
        List<SpellAbility> choices = controller.chooseSpellAbilityToPlay();
        require(choices == null || choices.size() <= 1, "Unexpected multiple actions");
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("chosen", chosen == null ? "PASS" : chosen.getHostCard().getName());
        Map<String, Object> after = physical(s);
        row.put("after_choice", after); row.put("physical_choice_pure", before.equals(after));
        row.put("source_id", s.source.getId());
        row.put("source_ability_chain_after_choice", chain(s.source.getSpellAbilities().get(0)));
        row.put("native_landfall", s.actor.hasLandfall());
        row.put("source_infect_after_choice", s.source.isInfectDamage(s.enemy));
        require(before.equals(after), "Choice changed physical pose before payment");
        require(s.actor.hasLandfall() == d.get("landfall").getAsBoolean(), "Actual landfall differs from declaration");
        if (d.get("name").getAsString().equals("infect-activated-boundary")) {
            require(s.source.isInfectDamage(s.enemy), "Native canonical aura did not grant infect");
        }
        String expectation = d.get("expect").getAsString();
        row.put("expectation", expectation);
        if (chosen != null) {
            require(chosen.getHostCard().getId() == s.source.getId(), "Unexpected source choice");
            row.put("selected_chain", chain(chosen));
            boolean paid = controller.playWithRollback(chosen, null);
            row.put("native_payment_succeeded", paid);
            require(paid && !s.game.getStack().isEmpty(), "Native selected cast did not pay/enter stack");
            row.put("paid_mana", chosen.getPayingMana().stream().map(m -> Map.of("color", m.getColor(),
                    "source_id", m.getSourceCard().getId())).toList());
            row.put("tapped_sources", s.lands.stream().filter(Card::isTapped).map(Card::getId).toList());
            resolveNative(s, row);
            row.put("after_resolution", physical(s)); row.put("enemy_life_after", s.enemy.getLife());
            row.put("own_life_after", s.actor.getLife()); row.put("native_actor_won", s.actor.hasWon());
            row.put("native_enemy_lost", s.enemy.hasLost());
        }
        if (expectation.equals("decline")) require(chosen == null, "Declared preservation control chose an action");
        else {
            require(chosen != null, "Native Default declined declared positive");
            require(chosen.getTargets().contains(s.creature), "Creature-only source selected another target");
            int paid = expectation.equals("removal") ? 1 : 2;
            require(chosen.getPayingMana().size() == paid
                    && s.lands.stream().filter(Card::isTapped).count() == paid
                    && s.actor.getManaPool().totalMana() == 0, "Actual native payment differs");
            require(s.game.getCardState(s.creature).isInZone(ZoneType.Graveyard), "Selected creature did not die");
            require(s.game.getCardState(s.source).isInZone(ZoneType.Graveyard), "Source did not complete native lifecycle");
            if (expectation.equals("removal")) require(s.enemy.getLife() == 20 && s.actor.getLife() == 20
                    && !s.game.isGameOver(), "Ordinary removal unexpectedly changed player life/outcome");
            else require(s.enemy.getLife() == -2 && s.actor.getLife() == 20 && s.game.isGameOver()
                    && s.actor.hasWon() && s.enemy.hasLost(), "Full delayed side-effect did not produce native win");
        }
        row.put("passed", true);
    }

    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        JsonObject declaration = JsonParser.parseString(Files.readString(output.resolve("DECLARATION.json"))).getAsJsonObject();
        require(declaration.get("seed").getAsLong() == 2026110627L, "Undeclared seed");
        MyRandom.setRandom(new Random(2026110627L));
        NativeLinkedDamagePolicyControls test = new NativeLinkedDamagePolicyControls();
        test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false);
        JsonObject old = JsonParser.parseString(Files.readString(output.resolve("OLD-DECLARATION.json"))).getAsJsonObject();
        Class<?> oldClass = Class.forName("forge.evaluation.NativeLinkedDamageLethalAudit");
        Object oldTest = oldClass.getConstructor().newInstance();
        Method oldCheck = oldClass.getDeclaredMethod("check", int.class, JsonObject.class, boolean.class, Map.class);
        oldCheck.setAccessible(true);
        List<Map<String, Object>> rows = new ArrayList<>();
        int failures = 0, errors = 0;
        for (boolean legacy : new boolean[]{true, false}) for (int seat : new int[]{0, 1}) {
            for (var item : (legacy ? old.getAsJsonArray("ai_scenes") : declaration.getAsJsonArray("new_scenes"))) {
                JsonObject scene = item.getAsJsonObject(); Map<String, Object> row = new LinkedHashMap<>();
                row.put("cohort", legacy ? "OLD12-UNMODIFIED-CHECK-METHODS" : "NEW20-PRESERVATION-CONTROLS");
                row.put("seat", seat); row.put("scene", scene.get("name").getAsString()); rows.add(row);
                try {
                    if (legacy) oldCheck.invoke(oldTest, seat, scene, false, row);
                    else test.check(seat, scene, row);
                } catch (Throwable failure) {
                    Throwable cause = failure instanceof InvocationTargetException ? failure.getCause() : failure;
                    row.put("failure", cause.toString());
                    if (cause instanceof AssertionError) failures++; else { errors++; cause.printStackTrace(); }
                    System.err.println("FAILED " + row.get("cohort") + " " + seat + " " + row.get("scene") + ": " + cause);
                }
            }
        }
        String json = new Gson().toJson(Map.of("label", declaration.get("label").getAsString(),
                "seed", 2026110627L, "passed", rows.size()-failures-errors, "failures", failures,
                "errors", errors, "production_changes", false, "cases", rows));
        Files.writeString(output.resolve("summary.private.json"), json+"\n"); System.out.println(json);
        System.exit(failures == 0 && errors == 0 ? 0 : 1);
    }
}
