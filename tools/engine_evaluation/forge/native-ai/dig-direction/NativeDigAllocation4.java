// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled native diagnostics using Forge Team/Card-Forge's engine and cards.
// Manual allocation rows are rules controls, not AI success or natural games.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.LobbyPlayer;
import forge.ai.*;
import forge.card.MagicColor;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.*;
import forge.game.ability.AbilityKey;
import forge.game.ability.ApiType;
import forge.game.card.*;
import forge.game.phase.PhaseType;
import forge.game.player.*;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import forge.util.collect.FCollectionView;
import java.nio.file.*;
import java.util.*;

public final class NativeDigAllocation4 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static void need(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player player) {
        Card card=super.createCard(name,player); card.setCollectible(true); return card;
    }
    private static final class ObservedController extends PlayerControllerAi {
        private final boolean manual;
        private final List<Map<String,Object>> choices;
        ObservedController(Game game, Player player, LobbyPlayer lobby, boolean manual,
                           List<Map<String,Object>> choices) {
            super(game,player,lobby); this.manual=manual; this.choices=choices;
            getAi().setUseSimulation(null);
        }
        @Override public <T extends GameEntity> T chooseSingleEntityForEffect(
                FCollectionView<T> options, DelayedReveal reveal, SpellAbility sa,
                String title, boolean optional, Player target, Map<String,Object> params) {
            if (sa.getApi()!=ApiType.Dig) return super.chooseSingleEntityForEffect(options,reveal,sa,title,optional,target,params);
            String destination=sa.getParamOrDefault("DestinationZone","Hand");
            T selected;
            if (manual) {
                if (reveal!=null) reveal(reveal);
                String wanted=destination.equals("Hand")?"Spell Pierce":"Island";
                selected=options.stream().filter(c->c.getName().equals(wanted)).findFirst().orElseThrow();
            } else selected=super.chooseSingleEntityForEffect(options,reveal,sa,title,optional,target,params);
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("destination",destination); row.put("library_position",sa.getParamOrDefault("LibraryPosition","-1"));
            row.put("options",options.stream().map(c->Map.of("id",c.getId(),"name",c.getName())).toList());
            row.put("selected",selected==null?null:selected.getName()); row.put("manual",manual);
            choices.add(row); return selected;
        }
    }
    private static Card library(Player player,String name) {
        return player.getCardsIn(ZoneType.Library).stream().filter(c->c.getName().equals(name)).findFirst().orElseThrow();
    }
    private static Card hand(Player p,String name) { return p.getGame().getAction().moveToHand(library(p,name),null); }
    private static Card battlefield(Player p,String name) {
        return p.getGame().getAction().moveToPlay(library(p,name),p,null,AbilityKey.newMap());
    }
    private static boolean in(Player p,ZoneType zone,int id) {
        return p.getCardsIn(zone).stream().anyMatch(c->c.getId()==id);
    }
    private static void priority(Game game,Player actor,Player enemy) {
        game.getPhaseHandler().setPriority(actor);actor.setHasPriority(true);enemy.setHasPriority(false);
    }
    private static void resolve(Game game) {
        for(int i=0;i<30;i++) {
            game.getAction().checkStateEffects(true);
            game.getTriggerHandler().runWaitingTriggers();game.getStack().addAllTriggeredAbilitiesToStack();
            if(game.getStack().isEmpty())return;
            need(!game.isGameOver(),"No injected game outcome");game.getStack().resolveStack();
        }
        need(false,"Native stack did not drain in30 resolutions");
    }
    private static List<Map<String,Object>> pool(Player player,ZoneType zone) {
        return player.getCardsIn(zone).stream().map(c->{Map<String,Object> m=new LinkedHashMap<>();m.put("id",c.getId());m.put("name",c.getName());return m;}).toList();
    }
    private static SpellAbility choose(PlayerControllerAi controller) {
        List<SpellAbility> result=controller.chooseSpellAbilityToPlay();
        need(result==null||result.size()<=1,"Single ordinary root expected");
        return result==null||result.isEmpty()?null:result.get(0);
    }
    private static List<Integer> colors(Map<String,Object> event) {
        if(event==null)return List.of();
        return ((List<?>)event.get("mana")).stream().map(x->((Number)((Map<?,?>)x).get("color")).intValue()).toList();
    }
    private static Map<String,Object> cast(List<Map<String,Object>> events,int id) {
        return events.stream().filter(e->Integer.valueOf(id).equals(e.get("source_id"))).findFirst().orElse(null);
    }
    private void check(Path inputs,int seat,boolean manual,Map<String,Object> row) throws Exception {
        List<Map<String,Object>> choices=new ArrayList<>();row.put("dig_choices",choices);
        List<RegisteredPlayer> registered=new ArrayList<>();
        for(int i=0;i<2;i++) {
            boolean actorSeat=i==seat;
            Deck deck=DeckSerializer.fromFile(inputs.resolve(actorSeat?"Tempo.dck":"Burn.dck").toFile());
            need(deck.getMain().countAll()==60,"Unchanged registered60 recipe");
            LobbyPlayerAi lobby=actorSeat?new LobbyPlayerAi("Tempo-seat"+i,null) {
                @Override public Player createIngamePlayer(Game game,int id) {
                    Player p=new Player(getName(),game,id);
                    p.setFirstController(new ObservedController(game,p,this,manual,choices));return p;
                }
            }:new LobbyPlayerAi("Burn-seat"+i,null);
            lobby.setAiProfile("Default");registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);rules.setAllowCheatShuffle(false);
        Game game=new Game(registered,rules,new Match(rules,registered,"TRUSTED dig allocation4"));
        game.setAge(GameStage.Play);game.AI_FLAT_MONTE_CARLO=false;game.AI_FLAT_MONTE_CARLO_MAX=false;
        game.AI_FLAT_MONTE_CARLO_LITE=false;game.EXPERIMENTAL_RESTORE_SNAPSHOT=false;
        Player actor=game.getPlayers().get(seat),enemy=game.getPlayers().get(1-seat);
        for(Player p:game.getPlayers()) {
            for(var item:p.getRegisteredPlayer().getDeck().getMain())for(int i=0;i<item.getValue();i++)addCardToZone(item.getKey().getName(),p,ZoneType.Library);
            need(p.getAllCards().size()==60,"Only original registered cards before poses");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2,actor,13);game.getPhaseHandler().onStackResolved();
        battlefield(actor,"Mountain");battlefield(actor,"Mountain");
        Card setupLand=hand(actor,"Island"),iteration=hand(actor,"Expressive Iteration");
        actor.setLife(20,null);enemy.setLife(20,null);resolve(game);priority(game,actor,enemy);
        PlayerControllerAi controller=(PlayerControllerAi)actor.getController();
        need(!controller.getAi().usesSimulation(),"Default, Monte Carlo disabled");
        SpellAbility land=setupLand.getAllPossibleAbilities(actor,true).stream().filter(SpellAbility::isLandAbility).findFirst().orElseThrow();
        land.setActivatingPlayer(actor);need(land.canPlay()&&actor.canPlayLand(setupLand,false,land),"Setup land genuinely legal");
        controller.playChosenSpellAbility(land);resolve(game);
        need(in(actor,ZoneType.Battlefield,setupLand.getId())&&actor.getLandsPlayedThisTurn()==1,"Genuine landplay used budget");
        Card bolt=library(actor,"Lightning Bolt"),pierce=library(actor,"Spell Pierce"),topLand=library(actor,"Island");
        game.getAction().moveToLibrary(topLand,0,null);game.getAction().moveToLibrary(pierce,0,null);game.getAction().moveToLibrary(bolt,0,null);
        need(actor.getCardsIn(ZoneType.Library).subList(0,3).stream().map(Card::getName).toList().equals(List.of("Lightning Bolt","Spell Pierce","Island")),"Declared owned top3");
        List<Map<String,Object>> events=new ArrayList<>();row.put("paid_casts",events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                if(event instanceof forge.game.event.GameEventSpellAbilityCast played) {
                    for(var item:game.getStack())if(item.getId()==played.si().getId()) {
                        Map<String,Object> e=new LinkedHashMap<>();e.put("source_id",played.si().getSourceCard().getId());e.put("name",played.si().getSourceCard().getName());
                        e.put("mana",item.getSpellAbility().getPayingMana().stream().map(m->Map.of("color",(int)m.getColor(),"source_id",m.getSourceCard().getId())).toList());events.add(e);break;
                    }
                }
            }
        });
        priority(game,actor,enemy);
        SpellAbility root=choose(controller);row.put("ordinary_root",root==null?null:root.getHostCard().getName());
        need(root!=null&&root.getHostCard().getId()==iteration.getId()&&root.canPlay(),"Actual ordinary chooser selects legal Iteration");
        need(ComputerUtil.playStack(root,actor,game),"Actual Iteration payment");resolve(game);priority(game,actor,enemy);
        List<Integer> iterationMana=colors(cast(events,iteration.getId()));
        need(iterationMana.size()==2&&iterationMana.contains((int)MagicColor.RED)&&iterationMana.contains((int)MagicColor.BLUE),"Actual UR paid");
        need(actor.getCardsIn(ZoneType.Battlefield).stream().filter(c->!c.isTapped()&&c.getName().equals("Mountain")).count()==1,"One real untappedR remains");
        row.put("hand_after_dig",pool(actor,ZoneType.Hand));row.put("exile_after_dig",pool(actor,ZoneType.Exile));
        row.put("land_drop_used",actor.getLandsPlayedThisTurn());row.put("bolt_id",bolt.getId());row.put("pierce_id",pierce.getId());
        boolean retained=in(actor,ZoneType.Hand,pierce.getId()),exiled=in(actor,ZoneType.Exile,bolt.getId());
        row.put("retained_pierce",retained);row.put("exiled_bolt",exiled);
        if(manual||exiled) {
            need(retained&&exiled,"Manual native allocation used only offered cards");
            Card exiledBolt=actor.getCardsIn(ZoneType.Exile).stream().filter(c->c.getId()==bolt.getId()).findFirst().orElseThrow();
            SpellAbility blast;
            if(manual) {
                blast=exiledBolt.getAllPossibleAbilities(actor,true).stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
                blast.setActivatingPlayer(actor);blast.resetTargets();need(blast.canTarget(enemy),"Actual Bolt target legal");blast.getTargets().add(enemy);
            } else {
                blast=choose(controller);
                row.put("ordinary_followup",blast==null?null:blast.getHostCard().getName());
                if(blast==null||blast.getHostCard().getId()!=bolt.getId()) {
                    row.put("status","AI_PAID_BOLT_RED");return;
                }
            }
            row.put("native_may_play_permission",blast.getMayPlayOption()!=null);
            need(blast.getMayPlayOption()!=null&&blast.canPlay(),"Actual granted exile permission, not patched restrictions");
            need(ComputerUtil.playStack(blast,actor,game),"RealR payment from exile");resolve(game);
            need(colors(cast(events,bolt.getId())).equals(List.of((int)MagicColor.RED)),"Exactly one actualR paid");
            need(enemy.getLife()==17&&actor.getLife()==20&&in(actor,ZoneType.Graveyard,bolt.getId())&&in(actor,ZoneType.Hand,pierce.getId()),"Paid native swap preserves counter and same3damage");
            need(!game.isGameOver(),"No winner manufactured");row.put("status",manual?"MANUAL_PAID_NATIVE_CONTROL_PASS":"AI_PAID_ALLOCATION_PASS");
        } else row.put("status",retained&&exiled?"AI_DECLARED_PASS":"AI_ALLOCATION_RED");
        row.put("enemy_life_after",enemy.getLife());row.put("native_game_over",game.isGameOver());
    }
    public static void main(String[] args) throws Exception {
        need(args.length==2,"Inputs and fresh output directory required");Path inputs=Path.of(args[0]),out=Path.of(args[1]);
        NativeDigAllocation4 test=new NativeDigAllocation4();MyRandom.setRandom(new Random(2026110717L));test.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS,false);
        int errors=0,red=0,passed=0;
        for(boolean manual:new boolean[]{true,false})for(int seat=0;seat<2;seat++) {
            Map<String,Object> row=new LinkedHashMap<>();row.put("seat",seat);row.put("manual_rules_control",manual);
            try {test.check(inputs,seat,manual,row);if(String.valueOf(row.get("status")).endsWith("_RED"))red++;else passed++;}
            catch(Throwable e){errors++;row.put("status","HARNESS_ERROR");row.put("error",String.valueOf(e));e.printStackTrace(System.err);}
            Files.writeString(out.resolve((manual?"manual":"ai")+"-seat"+seat+".private.json"),JSON.toJson(row)+"\n",StandardOpenOption.CREATE_NEW);
            System.out.println(JSON.toJson(Map.of("seat",seat,"manual",manual,"status",row.get("status"))));
        }
        Map<String,Object> summary=Map.of("total",4,"passed",passed,"allocation_red",red,"harness_errors",errors,"natural_games",0,"shared_production_edits",false);
        Files.writeString(out.resolve("summary.json"),JSON.toJson(summary)+"\n",StandardOpenOption.CREATE_NEW);System.out.println(JSON.toJson(summary));System.exit(errors>0?2:red>0?1:0);
    }
}
