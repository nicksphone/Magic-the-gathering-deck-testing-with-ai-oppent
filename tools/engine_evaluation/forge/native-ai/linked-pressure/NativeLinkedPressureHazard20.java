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

public final class NativeLinkedPressureHazard20 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110752L;
    private static final List<String> SCENES = List.of("BRASH_ONLY","STUFFY_ONLY","VINDICATOR_ONLY","GEAR_WITH_BRASH","TERROR_WARD_UNFUNDED","BOGLE_HEXPROOF","FIREWALKER_PRO_RED","MAIN1_HOLD","BEST_SAFE_ELIGIBLE","GEAR_ONLY_POSITIVE");
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

    private Card extraPose(Player player, String name, List<Card> extras) {
        addCardToZone(name,player,ZoneType.Library);
        Card card=pose(player,name);extras.add(card);return card;
    }
    private void check(int seat,String scene,Map<String,Object> row) throws Exception {
        boolean main1=scene.equals("MAIN1_HOLD"),ward=scene.equals("TERROR_WARD_UNFUNDED");
        boolean positive=List.of("GEAR_WITH_BRASH","BEST_SAFE_ELIGIBLE","GEAR_ONLY_POSITIVE").contains(scene);
        List<RegisteredPlayer> registered=new ArrayList<>();
        for(int i=0;i<2;i++){
            LobbyPlayerAi lobby=new LobbyPlayerAi((i==seat?"Burn":"Dimir Control")+"-hazard-seat"+i,null);
            lobby.setAiProfile("Default");registered.add(new RegisteredPlayer(deck(i==seat)).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);rules.setAllowCheatShuffle(false);
        Game game=new Game(registered,rules,new Match(rules,registered,"TRUSTED-CANONICAL-HAZARDS-NOT-REGISTERED120"));
        game.setAge(GameStage.Play);NativeNameMatchProbe.configureSearch(game,false);game.EXPERIMENTAL_RESTORE_SNAPSHOT=false;
        Player actor=game.getPlayers().get(seat),enemy=game.getPlayers().get(1-seat);
        for(Player player:game.getPlayers()){
            for(var entry:player.getRegisteredPlayer().getDeck().getMain())
                for(int n=0;n<entry.getValue();n++)addCardToZone(entry.getKey().getName(),player,ZoneType.Library);
            need(player.getAllCards().size()==60,"Registered base deck before added canonical poses");
        }
        game.getPhaseHandler().devModeSet(main1?PhaseType.MAIN1:PhaseType.MAIN2,actor,21);
        game.getPhaseHandler().onStackResolved();
        List<Map<String,Object>> events=new ArrayList<>();row.put("native_events",events);
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

        List<Card> extras=new ArrayList<>(),safe=new ArrayList<>();
        Card stuffy=null;
        if(scene.equals("BRASH_ONLY"))extraPose(enemy,"Brash Taunter",extras);
        else if(scene.equals("STUFFY_ONLY"))stuffy=extraPose(enemy,"Stuffy Doll",extras);
        else if(scene.equals("VINDICATOR_ONLY"))extraPose(enemy,"Phyrexian Vindicator",extras);
        else if(ward)extraPose(enemy,"Tolarian Terror",extras);
        else if(scene.equals("BOGLE_HEXPROOF"))extraPose(enemy,"Slippery Bogle",extras);
        else if(scene.equals("FIREWALKER_PRO_RED"))extraPose(enemy,"Kor Firewalker",extras);
        else {
            if(scene.equals("GEAR_WITH_BRASH")||scene.equals("BEST_SAFE_ELIGIBLE"))extraPose(enemy,"Brash Taunter",extras);
            safe.add(pose(enemy,"Torrential Gearhulk"));
            if(scene.equals("BEST_SAFE_ELIGIBLE"))safe.add(extraPose(enemy,"Shivan Dragon",extras));
        }
        List<Card> mana=new ArrayList<>();
        mana.add(pose(actor,"Mountain"));
        if(ward)mana.add(pose(actor,"Mountain"));else mana.add(pose(actor,"Plains"));
        resolve(game);
        if(stuffy!=null)need(stuffy.getChosenPlayer()==actor,"Native Stuffy ETB chose the actor; armed reflection control");
        Card blaze=hand(actor,"Searing Blaze");Card newLand=hand(actor,ward?"Plains":"Plateau");
        PlayerControllerAi controller=(PlayerControllerAi)actor.getController();
        need(actor.getController().getClass()==PlayerControllerAi.class&&!controller.getAi().usesSimulation(),"Ordinary Default, MC off");
        priority(game,actor,enemy);
        SpellAbility land=null;
        for(SpellAbility option:newLand.getAllPossibleAbilities(actor,true))if(option.isLandAbility()){land=option;break;}
        need(land!=null,"Native setup land option");land.setActivatingPlayer(actor);
        need(land.canPlay()&&actor.canPlayLand(newLand,false,land),"Checked native land action available");
        controller.playChosenSpellAbility(land);resolve(game);mana.add(newLand);
        need(in(actor,ZoneType.Battlefield,newLand.getId())&&actor.getLandsPlayedThisTurn()==1&&actor.hasLandfall(),"Actual native landfall");
        actor.setLife(10,null);enemy.setLife(9,null);game.getAction().checkStateEffects(true);priority(game,actor,enemy);
        need(!game.isGameOver()&&game.getStack().isEmpty()&&actor.getManaPool().isEmpty()
                &&actor.getCardsIn(ZoneType.Hand).size()==1&&mana.stream().allMatch(c->!c.isTapped()),"Settled trusted frontier");
        row.put("fixture_kind","TRUSTED_CANONICAL_POSES_NOT_REGISTERED120");row.put("registered_base_main_totals",List.of(60,60));
        row.put("added_canonical_card_names",extras.stream().map(Card::getName).toList());
        row.put("actual_owned_totals_before",List.of(actor.getAllCards().size(),enemy.getAllCards().size()));
        row.put("phase",main1?"MAIN1":"MAIN2");row.put("native_landfall",actor.hasLandfall());
        row.put("land_play_id",newLand.getId());row.put("ward_funding_exact_RR_plus_W",ward);
        row.put("mana_sources",mana.stream().map(c->Map.of("id",c.getId(),"name",c.getName(),"tapped",c.isTapped())).toList());
        row.put("public_enemy_creatures",enemy.getCreaturesInPlay().stream().map(c->Map.of("id",c.getId(),"name",c.getName(),"power",c.getNetPower(),"toughness",c.getNetToughness())).toList());
        row.put("Stuffy_chosen_player_id",stuffy==null?null:stuffy.getChosenPlayer().getId());
        row.put("before_first_root_actor_view",new ActorBoundary(actor).snapshot(game.getView()));
        // No damage/target/value/cost diagnostic or target repair before this ordinary first Root.
        SpellAbility selected=choose(controller);
        row.put("ordinary_root_callbacks",1);row.put("first_choice",choice(selected));
        row.put("manual_substitution",false);row.put("root_before_diagnostics",true);
        Card expected=safe.isEmpty()?null:ComputerUtilCard.getBestRemovalTargetAI(actor,new forge.game.card.CardCollection(safe));
        row.put("post_root_native_best_safe_target_id",expected==null?null:expected.getId());
        row.put("post_root_native_best_safe_target_name",expected==null?null:expected.getName());
        row.put("eligible_safe_ids",safe.stream().map(Card::getId).toList());
        boolean targets=selected!=null&&expected!=null&&linkedTargets(selected,enemy,expected.getId());
        boolean paid=false;
        if(selected!=null){
            need(selected.isSpell()&&selected.getHostCard().getId()==blaze.getId(),"Unexpected non-Blaze ordinary action in one-card pose");
            // Execute the actual selected ability without changing any target or payment.
            paid=ComputerUtil.playStack(selected,actor,game);resolve(game);
        }
        boolean rr=paid&&realRR(cast(events,blaze.getId()));
        boolean body=expected!=null&&in(enemy,ZoneType.Battlefield,expected.getId())&&expected.getDamage()==3;
        boolean pass=positive?targets&&paid&&rr&&body&&actor.getLife()==10&&enemy.getLife()==6&&!game.isGameOver()
                :selected==null&&!paid&&actor.getLife()==10&&enemy.getLife()==9&&!game.isGameOver();
        row.put("expect_decline",!positive);row.put("actual_payment",paid);row.put("actual_real_RR",rr);
        row.put("actual_native_best_safe_target_selected",targets);row.put("actual_three_body",body);
        row.put("actual_cast_event",cast(events,blaze.getId()));row.put("actor_life_after",actor.getLife());row.put("enemy_life_after",enemy.getLife());
        row.put("native_game_over",game.isGameOver());row.put("actor_lost",actor.hasLost());
        row.put("after_actor_view",new ActorBoundary(actor).snapshot(game.getView()));
        row.put("policy_red",!pass);row.put("status",pass?"DECLARED_PASS":"DECLARED_HAZARD_OR_TARGET_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length==1,"Fresh reports directory");Path out=Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED));NativeLinkedPressureHazard20 audit=new NativeLinkedPressureHazard20();audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS,false);
        int errors=0,red=0;
        for(String scene:SCENES)for(int seat=0;seat<2;seat++){
            Map<String,Object> row=new LinkedHashMap<>();row.put("scene",scene);row.put("seat",seat);row.put("seed",SEED);
            try{audit.check(seat,scene,row);if(Boolean.TRUE.equals(row.get("policy_red")))red++;}
            catch(Throwable error){errors++;row.put("status","HARNESS_ERROR");row.put("error_type",error.getClass().getName());row.put("error",String.valueOf(error.getMessage()));error.printStackTrace(System.err);}
            Files.writeString(out.resolve(scene+"-seat"+seat+".private.json"),JSON.toJson(row)+"\n",StandardOpenOption.CREATE_NEW);
            System.out.println(JSON.toJson(Map.of("scene",scene,"seat",seat,"status",row.get("status"))));
        }
        Map<String,Object> summary=Map.of("total",20,"harness_errors",errors,"policy_red",red,"passed",20-errors-red,
                "seed",SEED,"seed_installations",1,"natural_games",0,"manual_substitutions",0);
        Files.writeString(out.resolve("summary.private.json"),JSON.toJson(summary)+"\n",StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary));System.exit(errors>0?2:red>0?1:0);
    }
}
