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
import forge.card.CardStateName;
import forge.game.trigger.TriggerHandler;
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

public final class NativeObserverDelayed10 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final List<String> SCENES = List.of(
            "Empty", "Visible", "HiddenLand", "HiddenCreature", "FaceDownExile");
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
    private void check(int seat, String scene, Map<String,Object> row) throws Exception {
        List<RegisteredPlayer> registered=new ArrayList<>();
        for(int n=0;n<2;n++) {
            Deck deck=new Deck("INTERNAL-PROTOCOL-DELAYED-VISIBILITY");
            deck.getMain().add("Grizzly Bears",1);deck.getMain().add("Island",59);
            LobbyPlayerAi lobby=new LobbyPlayerAi("observer-seat-"+n,null);lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);rules.setAllowCheatShuffle(false);
        Game game=new Game(registered,rules,new Match(rules,registered,"INTERNAL-PROTOCOL-ONLY"));game.setAge(GameStage.Play);
        Player actor=game.getPlayers().get(seat),other=game.getPlayers().get(1-seat);
        for(Player player:game.getPlayers()) for(var e:player.getRegisteredPlayer().getDeck().getMain())
            for(int i=0;i<e.getValue();i++)addCardToZone(e.getKey().getName(),player,ZoneType.Library);
        Card source;
        if(scene.equals("Empty")||scene.equals("Visible")) source=pose(actor,"Island");
        else {
            String name=scene.equals("HiddenLand")?"Island":"Grizzly Bears";
            source=other.getCardsIn(ZoneType.Library).stream().filter(c->c.getName().equals(name)).findFirst().orElseThrow();
            if(scene.equals("FaceDownExile")) {source=game.getAction().moveTo(other.getZone(ZoneType.Exile),source,null,forge.game.ability.AbilityKey.newMap());source.turnFaceDown(true);}
            else source=game.getAction().moveToHand(source,null);
        }
        boolean visible=source.getView().canBeShownTo(actor.getView())&&source.getView().canFaceDownBeShownTo(actor.getView());
        need(visible==(scene.equals("Visible")||scene.equals("Empty")),"Actual declared native source visibility");
        if(!scene.equals("Empty")) {
            // Internal metadata protocol, NOT a printed card trigger or a gameplay episode.
            var trigger=TriggerHandler.parseTrigger("Mode$ Phase | Phase$ End of Turn | TriggerZones$ Battlefield",source,true);
            game.getTriggerHandler().registerDelayedTrigger(trigger);
        }
        String before=rng();var ids=SpellAbility.class.getDeclaredField("maxId");ids.setAccessible(true);int id=ids.getInt(null);
        boolean answer=false,missing=false;
        try {Method query=TriggerHandler.class.getDeclaredMethod("hasObserverVisibleDelayedTrigger",Player.class);
            need(Modifier.isPublic(query.getModifiers())&&query.getReturnType()==boolean.class,"Public read-only query ABI");
            answer=(Boolean)query.invoke(game.getTriggerHandler(),actor);
        } catch(NoSuchMethodException absent){missing=true;}
        need(before.equals(rng())&&id==ids.getInt(null),"Inspection does not consume native RNG or ability IDs");
        row.put("observer_sees_source",visible);row.put("query_missing",missing);row.put("actual",answer);row.put("expected",scene.equals("Visible"));
        row.put("ordinary_AI_callbacks",0);row.put("fake_gameplay_claim",false);
        row.put("status",!missing&&answer==scene.equals("Visible")?"PASS":"PROTOCOL_RED");
    }
    public static void main(String[] args)throws Exception {
        Path out=Path.of(args[0]);MyRandom.setRandom(new Random(2026110702L));NativeObserverDelayed10 a=new NativeObserverDelayed10();a.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS,false);FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS,false);
        int pass=0,red=0,errors=0;for(String scene:SCENES)for(int seat=0;seat<2;seat++) {
            Map<String,Object> row=new LinkedHashMap<>(Map.of("scene",scene,"seat",seat,"label","INTERNAL-PROTOCOL-NOT-GAMEPLAY"));
            try{a.check(seat,scene,row);if(row.get("status").equals("PASS"))pass++;else red++;}
            catch(Throwable error){errors++;row.put("status","HARNESS_ERROR");row.put("error",String.valueOf(error));error.printStackTrace();}
            Files.writeString(out.resolve(scene+"-seat"+seat+".private.json"),JSON.toJson(row)+"\n",StandardOpenOption.CREATE_NEW);
        }
        var summary=Map.of("total",10,"pass",pass,"protocol_red",red,"harness_errors",errors,"ordinary_AI_callbacks",0,"natural_games",0);
        Files.writeString(out.resolve("summary.private.json"),JSON.toJson(summary)+"\n",StandardOpenOption.CREATE_NEW);System.out.println(JSON.toJson(summary));System.exit(errors>0?2:red>0?1:0);
    }
}
