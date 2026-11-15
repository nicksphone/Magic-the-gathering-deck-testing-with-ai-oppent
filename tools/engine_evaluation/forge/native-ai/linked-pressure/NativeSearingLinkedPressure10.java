// SPDX-License-Identifier: GPL-3.0-or-later
// Trusted Main2 poses and separate paid rules controls, not natural games or expert labels.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.card.MagicColor;
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeSearingLinkedPressure10 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110752L;
    private static final List<String> SCENES = List.of("PAIRED_FUNDED", "SINGLE_FUNDED", "UNFUNDED_RW", "OWN_EIDOLON_LIFE2", "MANUAL_PAID_PAIR");
    private static void need(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card = super.createCard(name, player);
        card.setCollectible(true);
        return card;
    }
    private static Deck deck(boolean burn) {
        Deck result = new Deck(burn ? "Burn" : "Dimir Control");
        String[] names = burn ? new String[]{"Goblin Guide", "Eidolon of the Great Revel", "Monastery Swiftspear", "Lightning Bolt", "Lava Spike", "Rift Bolt", "Boros Charm", "Skullcrack", "Searing Blaze", "Mountain", "Plains", "Plateau"}
                : new String[]{"Consider", "Fatal Push", "Drown in the Loch", "Go for the Throat", "Memory Deluge", "Sheoldred, the Apocalypse", "The Meathook Massacre", "Counterspell", "Torrential Gearhulk", "Island", "Swamp", "Underground Sea"};
        int[] counts = burn ? new int[]{4,4,4,4,4,4,4,4,4,16,4,4} : new int[]{4,4,4,4,4,3,3,4,2,16,8,4};
        for (int i = 0; i < names.length; i++) result.getMain().add(names[i], counts[i]);
        need(result.getMain().countAll() == 60, "Original public registered60 deck");
        return result;
    }
    private static Card library(Player player, String name) {
        return player.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
    }
    private static Card hand(Player player, String name) {
        return player.getGame().getAction().moveToHand(library(player, name), null);
    }
    private static Card pose(Player player, String name) {
        return player.getGame().getAction().moveToPlay(library(player, name), player, null, AbilityKey.newMap());
    }
    private static boolean in(Player player, ZoneType zone, int id) {
        return player.getCardsIn(zone).stream().anyMatch(c -> c.getId() == id);
    }
    private static void priority(Game game, Player actor, Player enemy) {
        game.getPhaseHandler().setPriority(actor); actor.setHasPriority(true); enemy.setHasPriority(false);
    }
    private static void resolve(Game game) {
        for (int n = 0; n < 40; n++) {
            if (game.isGameOver()) return;
            game.getAction().checkStateEffects(true);
            if (game.isGameOver()) return;
            game.getTriggerHandler().runWaitingTriggers(); game.getStack().addAllTriggeredAbilitiesToStack();
            if (game.getStack().isEmpty()) return;
            game.getStack().resolveStack();
        }
        need(game.getStack().isEmpty() || game.isGameOver(), "Bounded native stack resolution");
    }
    private static List<Integer> playerTargetIds(SpellAbility root) {
        List<Integer> ids = new ArrayList<>();
        for (Player player : root.getTargets().getTargetPlayers()) ids.add(player.getId());
        return ids;
    }
    private static Map<String,Object> choice(SpellAbility root) {
        Map<String,Object> result = new LinkedHashMap<>();
        if (root == null) { result.put("choice", "PASS"); return result; }
        result.put("source", root.getHostCard().getName()); result.put("source_id", root.getHostCard().getId());
        result.put("api", String.valueOf(root.getApi())); result.put("is_spell", root.isSpell());
        result.put("player_target_ids", playerTargetIds(root));
        SpellAbility child = root.getSubAbility();
        result.put("child_api", child == null ? null : String.valueOf(child.getApi()));
        result.put("creature_target_ids", child == null ? List.of() : child.getTargets().getTargetCards().stream().map(Card::getId).toList());
        return result;
    }
    private static SpellAbility choose(PlayerControllerAi controller) {
        List<SpellAbility> options = controller.chooseSpellAbilityToPlay();
        need(options == null || options.size() <= 1, "Declared ordinary single-root return shape");
        return options == null || options.isEmpty() ? null : options.get(0);
    }
    private static boolean linkedTargets(SpellAbility root, Player enemy, int gearId) {
        if (root == null || !root.isSpell() || root.getApi() != ApiType.DealDamage) return false;
        SpellAbility child = root.getSubAbility();
        return playerTargetIds(root).equals(List.of(enemy.getId()))
                && child != null && child.getApi() == ApiType.DealDamage
                && child.getTargets().getTargetCards().stream().map(Card::getId).toList().equals(List.of(gearId));
    }
    private static SpellAbility manualBlaze(Card card, Player actor, Player enemy, Card gear) {
        SpellAbility root = card.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
        root.setActivatingPlayer(actor); root.resetTargets();
        need(root.getApi() == ApiType.DealDamage && root.canTarget(enemy), "Manual native player target legal");
        root.getTargets().add(enemy);
        SpellAbility child = root.getSubAbility();
        need(child != null && child.getApi() == ApiType.DealDamage, "Full native linked child");
        child.setActivatingPlayer(actor); child.resetTargets();
        need(child.canTarget(gear), "Manual native controller-linked creature target legal");
        child.getTargets().add(gear);
        need(child.getSubAbility() != null && child.getSubAbility().getApi() == ApiType.DamageResolve,
                "Full native DamageMap resolution tail, not a rewritten card");
        return root;
    }
    private static Map<String,Object> cast(List<Map<String,Object>> events, int id) {
        return events.stream().filter(e -> "GameEventSpellAbilityCast".equals(e.get("event"))
                && Integer.valueOf(id).equals(e.get("source_id"))).findFirst().orElse(null);
    }
    private static boolean realRR(Map<String,Object> event) {
        if (event == null || !(event.get("paid_mana") instanceof List<?> mana) || mana.size() != 2) return false;
        return mana.stream().allMatch(x -> ((Number)((Map<?,?>)x).get("color")).intValue() == MagicColor.RED)
                && mana.stream().map(x -> ((Number)((Map<?,?>)x).get("source_id")).intValue()).distinct().count() == 2;
    }
    private void check(int seat, String scene, Map<String,Object> row) throws Exception {
        boolean manual = scene.equals("MANUAL_PAID_PAIR"), pair = manual || scene.equals("PAIRED_FUNDED");
        boolean unfunded = scene.equals("UNFUNDED_RW"), eidolon = scene.equals("OWN_EIDOLON_LIFE2");
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            LobbyPlayerAi lobby = new LobbyPlayerAi((i == seat ? "Burn" : "Dimir Control") + "-seat" + i, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck(i == seat)).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "TRUSTED-SEARING-LINKED-PRESSURE10"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false); game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1-seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int n = 0; n < entry.getValue(); n++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getAllCards().size() == 60, "120 registered originals before trusted poses");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor, 21); game.getPhaseHandler().onStackResolved();
        List<Map<String,Object>> events = new ArrayList<>(); row.put("native_events", events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String,Object> e = new LinkedHashMap<>(); e.put("index", events.size()+1); e.put("event", event.getClass().getSimpleName());
                e.put("actor_life", actor.getLife()); e.put("enemy_life", enemy.getLife());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast played) {
                    e.put("source_id", played.si().getSourceCard().getId()); e.put("source", played.si().getSourceCard().getName());
                    e.put("targets", played.targetDescription());
                    for (var item : game.getStack()) if (item.getId() == played.si().getId()) {
                        e.put("paid_mana", item.getSpellAbility().getPayingMana().stream().map(m -> Map.of(
                                "color", (int)m.getColor(), "source_id", m.getSourceCard() == null ? -1 : m.getSourceCard().getId())).toList()); break;
                    }
                }
                if (event instanceof forge.game.event.GameEventLandPlayed || event instanceof forge.game.event.GameEventSpellResolved)
                    e.put("message", event.toString());
                events.add(e);
            }
        });
        List<Card> mana = new ArrayList<>();
        mana.add(pose(actor, "Mountain"));
        if (pair) { mana.add(pose(actor, "Mountain")); mana.add(pose(actor, "Mountain")); }
        if (!unfunded) mana.add(pose(actor, "Plains"));
        Card gear = pose(enemy, "Torrential Gearhulk");
        if (eidolon) pose(actor, "Eidolon of the Great Revel");
        resolve(game);
        Card first = hand(actor, "Searing Blaze"), second = pair ? hand(actor, "Searing Blaze") : null;
        Card newLand = hand(actor, unfunded ? "Plains" : "Plateau");
        PlayerControllerAi controller = (PlayerControllerAi)actor.getController();
        need(actor.getController().getClass() == PlayerControllerAi.class && !controller.getAi().usesSimulation(), "Ordinary native Default, MC off");
        priority(game, actor, enemy);
        // A genuine checked setup land action; not an AI land decision or fabricated payment history.
        SpellAbility land = null;
        for (SpellAbility option : newLand.getAllPossibleAbilities(actor, true)) {
            if (option.isLandAbility()) { land = option; break; }
        }
        need(land != null, "Native land ability exists");
        land.setActivatingPlayer(actor);
        need(land.canPlay() && actor.canPlayLand(newLand, false, land), "Native setup land option available");
        controller.playChosenSpellAbility(land); resolve(game);
        need(in(actor, ZoneType.Battlefield, newLand.getId()) && actor.getLandsPlayedThisTurn() == 1 && actor.hasLandfall(), "Actual checked land entry and landfall");
        mana.add(newLand);
        actor.setLife(eidolon ? 2 : 10, null); enemy.setLife(9, null); game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(game.getStack().isEmpty() && !game.isGameOver() && actor.getManaPool().isEmpty()
                && mana.stream().allMatch(c -> !c.isTapped()) && gear.getNetPower() == 5 && gear.getNetToughness() == 6
                && gear.getDamage() == 0 && enemy.getCreaturesInPlay().size() == 1 && actor.getCardsIn(ZoneType.Hand).size() == (pair ? 2 : 1), "Settled public Main2 frontier");
        row.put("registered_original_totals", List.of(60,60)); row.put("phase", "MAIN2"); row.put("turn", 21);
        row.put("native_landfall", actor.hasLandfall()); row.put("checked_land_play_id", newLand.getId()); row.put("checked_land_play_not_AI_choice", true);
        row.put("mana_source_ids", mana.stream().map(Card::getId).toList()); row.put("blaze_ids", second == null ? List.of(first.getId()) : List.of(first.getId(),second.getId()));
        row.put("gearhulk_id", gear.getId()); row.put("initial_actor_life", actor.getLife()); row.put("initial_enemy_life", enemy.getLife());
        row.put("before_first_root_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        row.put("manual_rules_control_not_AI", manual); row.put("manual_substitution", false); row.put("root_before_diagnostics", true);
        int callbacks = 0, casts = 0; Set<Integer> paidSpellIds = new HashSet<>(); Set<Integer> paidRedSourceIds = new HashSet<>();
        List<Map<String,Object>> choices = new ArrayList<>(); row.put("ordinary_choices", choices);
        boolean firstOutcome = false, secondOutcome = false;
        for (int action = 0; action < (pair ? 2 : 1); action++) {
            SpellAbility selected;
            if (manual) selected = manualBlaze(action == 0 ? first : second, actor, enemy, gear);
            else { selected = choose(controller); callbacks++; choices.add(choice(selected)); }
            if (selected == null) break;
            int id = selected.getHostCard().getId();
            boolean originalBlaze = id == first.getId() || (second != null && id == second.getId());
            boolean correctTargets = originalBlaze && linkedTargets(selected, enemy, gear.getId());
            row.put("action" + action + "_targets_correct", correctTargets);
            boolean paid = ComputerUtil.playStack(selected, actor, game);
            row.put("action" + action + "_actual_payment", paid);
            if (!paid) break;
            casts++;
            paidSpellIds.add(id);
            resolve(game);
            Map<String,Object> castEvent = cast(events,id);
            boolean rr = realRR(castEvent); row.put("action" + action + "_real_RR", rr);
            if (rr) for (Object paidMana : (List<?>)castEvent.get("paid_mana"))
                paidRedSourceIds.add(((Number)((Map<?,?>)paidMana).get("source_id")).intValue());
            boolean outcome = correctTargets && rr && enemy.getLife() == 9 - 3 * (action+1);
            if (action == 0) {
                firstOutcome = outcome && in(enemy,ZoneType.Battlefield,gear.getId()) && gear.getDamage() == 3 && actor.getLife() == (eidolon ? 0 : 10);
                row.put("after_first_gear_damage", gear.getDamage()); row.put("after_first_enemy_life", enemy.getLife());
            } else secondOutcome = outcome && in(enemy,ZoneType.Graveyard,gear.getId()) && enemy.getCreaturesInPlay().isEmpty();
            if (game.isGameOver()) break;
            if (action == 0 && pair && !firstOutcome) break;
            priority(game,actor,enemy);
        }
        row.put("ordinary_root_callbacks",callbacks); row.put("paid_casts",casts); row.put("first_actual_3_face_3_body",firstOutcome);
        row.put("distinct_paid_spell_ids",paidSpellIds); row.put("distinct_paid_R_source_ids",paidRedSourceIds);
        row.put("pair_actual_6_face_6_body_Gearhulk_death",secondOutcome);
        row.put("actor_life_after",actor.getLife()); row.put("enemy_life_after",enemy.getLife()); row.put("native_game_over",game.isGameOver());
        row.put("gearhulk_in_graveyard",in(enemy,ZoneType.Graveyard,gear.getId())); row.put("after_actor_view",new ActorBoundary(actor).snapshot(game.getView()));
        boolean pass;
        if (manual) { need(casts == 2 && paidSpellIds.size() == 2 && paidRedSourceIds.size() == 4 && firstOutcome && secondOutcome && enemy.getLife() == 3 && actor.getLife() == 10 && !game.isGameOver(), "Separate native paid RR4 pair control outcome"); pass = true; }
        else if (unfunded || eidolon) pass = choices.size() == 1 && "PASS".equals(choices.get(0).get("choice")) && casts == 0 && actor.getLife() == (eidolon ? 2 : 10) && enemy.getLife() == 9 && !game.isGameOver();
        else pass = firstOutcome && (!pair || secondOutcome) && casts == (pair ? 2 : 1) && paidSpellIds.size() == casts
                && paidRedSourceIds.size() == casts * 2 && actor.getLife() == 10 && !game.isGameOver();
        row.put("policy_red",!manual && !pass); row.put("status",manual ? "MANUAL_PAID_RULES_CONTROL_PASS" : pass ? "AI_DECLARED_PASS" : "AI_DECLARED_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1,"Fresh private reports directory"); Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED)); NativeSearingLinkedPressure10 audit = new NativeSearingLinkedPressure10(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS,false);
        int errors=0, red=0, aiPass=0, manualPass=0;
        for (String scene : SCENES) for (int seat=0;seat<2;seat++) {
            Map<String,Object> row=new LinkedHashMap<>();row.put("scene",scene);row.put("seat",seat);row.put("seed",SEED);
            try { audit.check(seat,scene,row); if (Boolean.TRUE.equals(row.get("policy_red"))) red++;
                else if (scene.equals("MANUAL_PAID_PAIR")) manualPass++; else aiPass++;
            } catch(Throwable error) { errors++;row.put("status","HARNESS_ERROR");row.put("error_type",error.getClass().getName());row.put("error",String.valueOf(error.getMessage()));error.printStackTrace(System.err); }
            Files.writeString(out.resolve(scene+"-seat"+seat+".private.json"),JSON.toJson(row)+"\n",StandardOpenOption.CREATE_NEW);
            System.out.println(JSON.toJson(Map.of("scene",scene,"seat",seat,"status",row.get("status"))));
        }
        Map<String,Object> summary=new LinkedHashMap<>();summary.put("label","TRUSTED_LINKED_PRESSURE_NOT_EXPERT_OR_NATURAL");summary.put("total",10);
        summary.put("harness_errors",errors);summary.put("policy_red",red);summary.put("AI_declared_pass",aiPass);summary.put("manual_paid_controls",manualPass);
        summary.put("seed",SEED);summary.put("seed_installations",1);summary.put("natural_games",0);summary.put("manual_substitutions",0);
        Files.writeString(out.resolve("summary.private.json"),JSON.toJson(summary)+"\n",StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary));System.exit(errors>0?2:red>0?1:0);
    }
}
