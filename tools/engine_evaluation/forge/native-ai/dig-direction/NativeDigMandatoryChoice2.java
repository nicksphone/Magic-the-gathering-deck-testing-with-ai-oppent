// SPDX-License-Identifier: GPL-3.0-or-later
// Native caller-boundary diagnostic using unchanged Forge Team/Card-Forge cards.
// This tests mandatory selector admission, not full Illusions of Grandeur gameplay.
package forge.evaluation;

import com.google.gson.Gson;
import forge.ai.*;
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

public final class NativeDigMandatoryChoice2 extends AITest {
    private static byte[] rng() throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        try(ObjectOutputStream stream=new ObjectOutputStream(out)){stream.writeObject(MyRandom.getRandom());}
        return out.toByteArray();
    }
    private void check(int seat,Map<String,Object> row) throws Exception {
        List<RegisteredPlayer> players=new ArrayList<>();
        for(int i=0;i<2;i++) {
            LobbyPlayerAi lobby=new LobbyPlayerAi("mandatory-dig-seat"+i,null);lobby.setAiProfile("Default");
            players.add(new RegisteredPlayer(new Deck("INTERNAL mandatory chooser boundary")).setPlayer(lobby));
        }
        GameRules rules=new GameRules(GameType.Constructed);Game game=new Game(players,rules,new Match(rules,players,"INTERNAL mandatory selection"));
        game.setAge(GameStage.Play);Player actor=game.getPlayers().get(seat);
        Card host=addCardToZone("Expressive Iteration",actor,ZoneType.Hand);
        Card protectedCard=addCardToZone("Illusions of Grandeur",actor,ZoneType.Library);
        Card bolt=addCardToZone("Lightning Bolt",actor,ZoneType.Library);
        if(!protectedCard.hasSVar("DoNotDiscardIfAble"))throw new IllegalStateException("Canonical protected-card flag missing");
        SpellAbility sa=AbilityFactory.getAbility("DB$ Dig | DigNum$ 2 | ChangeNum$ 1 | DestinationZone$ Library | LibraryPosition$ -1",host);
        sa.setActivatingPlayer(actor);CardCollection options=new CardCollection();options.add(protectedCard);options.add(bolt);
        List<Integer> before=options.stream().map(Card::getId).toList();MyRandom.setRandom(new Random(2026110719L));byte[] beforeRng=rng();
        List<Card> chosen=actor.getController().chooseEntitiesForEffect(options,1,1,null,sa,"INTERNAL mandatory one-card bottom",actor,Map.of());
        boolean stable=before.equals(options.stream().map(Card::getId).toList())&&Arrays.equals(beforeRng,rng());
        row.put("min",1);row.put("max",1);row.put("selected_size",chosen.size());row.put("selected",chosen.stream().map(Card::getName).toList());
        row.put("canonical_DoNotDiscardIfAble",protectedCard.getSVar("DoNotDiscardIfAble"));row.put("input_and_RNG_unchanged",stable);
        row.put("status",chosen.size()==1&&chosen.get(0).getId()==bolt.getId()&&stable?"PASS":"MANDATORY_SELECTION_RED");
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=1)throw new IllegalArgumentException("Fresh output directory");Path out=Path.of(args[0]);
        NativeDigMandatoryChoice2 test=new NativeDigMandatoryChoice2();test.initializeModel();Gson json=new Gson();int pass=0,red=0,errors=0;
        for(int seat=0;seat<2;seat++) {
            Map<String,Object> row=new LinkedHashMap<>();row.put("seat",seat);
            try{test.check(seat,row);if("PASS".equals(row.get("status")))pass++;else red++;}
            catch(Throwable e){errors++;row.put("status","HARNESS_ERROR");row.put("error",String.valueOf(e));e.printStackTrace(System.err);}
            Files.writeString(out.resolve("seat"+seat+".private.json"),json.toJson(row)+"\n",StandardOpenOption.CREATE_NEW);
        }
        Map<String,Object> result=Map.of("total",2,"passed",pass,"declared_red",red,"harness_errors",errors,"natural_games",0);
        Files.writeString(out.resolve("summary.json"),json.toJson(result)+"\n",StandardOpenOption.CREATE_NEW);System.out.println(json.toJson(result));System.exit(errors>0?2:red>0?1:0);
    }
}
