// SPDX-License-Identifier: GPL-3.0-or-later
// Internal native selector protocol controls, not new canonical card programs.
// Engine/card helpers are Forge Team/Card-Forge contributors' work.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.*;
import forge.ai.ability.DigAi;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.AbilityFactory;
import forge.game.card.*;
import forge.game.player.*;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.util.MyRandom;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class NativeDigDirectionControls extends AITest {
    private static final Gson JSON=new Gson();
    private static final List<String> SCENES=List.of("HAND_DEFAULT","HAND_EXPLICIT","TOP_EXPLICIT",
            "BOTTOM_DEFAULT","BOTTOM_EXPLICIT","OPPONENT_LIBRARY","OPPONENT_CHOOSES",
            "EXPLICIT_HINT","NULL_RELATED","UNKNOWN_HINT");
    private static byte[] rng() throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        try(ObjectOutputStream stream=new ObjectOutputStream(out)){stream.writeObject(MyRandom.getRandom());}
        return out.toByteArray();
    }
    private void check(int seat,String scene,Map<String,Object> row) throws Exception {
        List<RegisteredPlayer> players=new ArrayList<>();
        for(int i=0;i<2;i++) {
            LobbyPlayerAi lobby=new LobbyPlayerAi("internal-dig-seat"+i,null);lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck("INTERNAL selector fixture")).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);Game game=new Game(players,rules,new Match(rules,players,"INTERNAL chooser control"));
        game.setAge(GameStage.Play);Player actor=game.getPlayers().get(seat),enemy=game.getPlayers().get(1-seat);
        Card host=addCardToZone("Expressive Iteration",actor,ZoneType.Hand);
        Card land=addCardToZone("Island",actor,ZoneType.Library),bolt=addCardToZone("Lightning Bolt",actor,ZoneType.Library);
        String params="DB$ Dig | DigNum$ 2 | ChangeNum$ 1";
        if(!scene.equals("HAND_DEFAULT"))params+=" | DestinationZone$ "+(scene.equals("HAND_EXPLICIT")?"Hand":"Library");
        if(scene.equals("TOP_EXPLICIT"))params+=" | LibraryPosition$ 0";
        if(scene.equals("BOTTOM_EXPLICIT"))params+=" | LibraryPosition$ -1";
        if(scene.equals("EXPLICIT_HINT"))params+=" | AILogic$ ChooseBestForOpponent";
        if(scene.equals("UNKNOWN_HINT"))params+=" | AILogic$ InternalUnknownHint";
        SpellAbility sa=AbilityFactory.getAbility(params,host);
        sa.setActivatingPlayer(scene.equals("OPPONENT_CHOOSES")?enemy:actor);
        Player owner=scene.equals("NULL_RELATED")?null:(scene.startsWith("OPPONENT")?enemy:actor);
        CardCollection choices=new CardCollection();choices.add(land);choices.add(bolt);
        List<Integer> beforeIds=choices.stream().map(Card::getId).toList();String beforeParams=sa.getMapParams().toString();
        MyRandom.setRandom(new Random(2026110718L));byte[] beforeRng=rng();
        Card selected=new DigAi().chooseSingleCard(actor,sa,choices,false,owner,Map.of());
        boolean immutable=beforeIds.equals(choices.stream().map(Card::getId).toList())
                &&beforeParams.equals(sa.getMapParams().toString())&&Arrays.equals(beforeRng,rng())
                &&actor.getCardsIn(ZoneType.Library).size()==2&&actor.getCardsIn(ZoneType.Hand).size()==1;
        String expected=scene.startsWith("BOTTOM")||scene.equals("OPPONENT_CHOOSES")?"Island":"Lightning Bolt";
        row.put("script_is_labelled_internal_protocol",params);row.put("expected",expected);
        row.put("actual",selected==null?null:selected.getName());row.put("input_and_RNG_unchanged",immutable);
        row.put("status",selected!=null&&selected.getName().equals(expected)&&immutable?"PASS":"DECLARED_RED");
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=1)throw new IllegalArgumentException("Fresh output directory");
        Path out=Path.of(args[0]);NativeDigDirectionControls test=new NativeDigDirectionControls();test.initializeModel();
        int passed=0,red=0,errors=0;
        for(String scene:SCENES)for(int seat=0;seat<2;seat++) {
            Map<String,Object> row=new LinkedHashMap<>();row.put("scene",scene);row.put("seat",seat);
            try{test.check(seat,scene,row);if("PASS".equals(row.get("status")))passed++;else red++;}
            catch(Throwable error){errors++;row.put("status","HARNESS_ERROR");row.put("error",String.valueOf(error));error.printStackTrace(System.err);}
            Files.writeString(out.resolve(scene+"-seat"+seat+".private.json"),JSON.toJson(row)+"\n",StandardOpenOption.CREATE_NEW);
        }
        Map<String,Object> summary=Map.of("total",20,"passed",passed,"declared_red",red,"harness_errors",errors,"natural_games",0,"label","INTERNAL_PROTOCOL_NOT_CARD_SEMANTICS");
        Files.writeString(out.resolve("summary.json"),JSON.toJson(summary)+"\n",StandardOpenOption.CREATE_NEW);System.out.println(JSON.toJson(summary));System.exit(errors>0?2:red>0?1:0);
    }
}
