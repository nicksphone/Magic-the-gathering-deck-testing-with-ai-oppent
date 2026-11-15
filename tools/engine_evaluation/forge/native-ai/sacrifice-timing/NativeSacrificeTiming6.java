// SPDX-License-Identifier: GPL-3.0-or-later
// Constructed native fixtures using the Forge Team/Card-Forge engine and full programs.
// These are not natural games or synthetic replacements for printed card abilities.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
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
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public final class NativeSacrificeTiming6 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
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
        try (ObjectOutputStream stream = new ObjectOutputStream(bytes)) { stream.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Object> ability(SpellAbility sa) {
        if (sa == null) return Map.of("choice", "PASS");
        return Map.of("source", sa.getHostCard().getName(), "source_id", sa.getHostCard().getId(),
                "ability_id", sa.getId(), "api", String.valueOf(sa.getApi()), "is_spell", sa.isSpell());
    }
    private static Card pose(Player player, String name) {
        Card original = player.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        return player.getGame().getAction().moveToPlay(original, player, null, AbilityKey.newMap());
    }
    private static void priority(Game game, Player actor, Player enemy) {
        game.getPhaseHandler().setPriority(actor);
        actor.setHasPriority(true); enemy.setHasPriority(false);
    }
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
    private static SpellAbility activation(Card source, Player player, ApiType api) {
        SpellAbility sa = source.getSpellAbilities().stream().filter(s -> s.isActivatedAbility() && s.getApi() == api).findFirst().orElseThrow();
        sa.setActivatingPlayer(player); return sa;
    }
    private void check(long seed, int seat, String scene, Map<String, Object> row) throws Exception {
        MyRandom.setRandom(new Random(seed));
        List<RegisteredPlayer> registered = new ArrayList<>();
        String sourceName = scene.equals("TokenCostWin") ? "Witch's Oven" : scene.equals("DrawCostWin") ? "Village Rites" : "Viscera Seer";
        ApiType api = scene.equals("TokenCostWin") ? ApiType.Token : scene.equals("DrawCostWin") ? ApiType.Draw : ApiType.Scry;
        for (int i = 0; i < 2; i++) {
            Deck deck = new Deck("controlled-sacrifice-timing-seat-" + i);
            if (i == seat) { deck.getMain().add("Cauldron Familiar",1); deck.getMain().add("Blood Artist",1); deck.getMain().add(sourceName,1); deck.getMain().add("Swamp",57); }
            else deck.getMain().add("Mountain",60);
            LobbyPlayerAi lobby = new LobbyPlayerAi("sacrifice-timing-seat-" + i,null); lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered,rules,new Match(rules,registered,"CONTROLLED-SACRIFICE-TIMING6"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game,false); game.EXPERIMENTAL_RESTORE_SNAPSHOT=false;
        Player actor=game.getPlayers().get(seat), enemy=game.getPlayers().get(1-seat);
        for (Player player:game.getPlayers()) {
            for (var entry:player.getRegisteredPlayer().getDeck().getMain()) for(int i=0;i<entry.getValue();i++) addCardToZone(entry.getKey().getName(),player,ZoneType.Library);
            need(player.getAllCards().size()==60 && player.getRegisteredPlayer().getDeck().getMain().countAll()==60,"Complete registered60 originals");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1,actor); game.getPhaseHandler().onStackResolved();
        pose(actor,"Cauldron Familiar"); pose(actor,"Blood Artist"); pose(actor,"Swamp"); pose(actor,"Swamp");
        Card sourceCard;
        if (scene.equals("DrawCostWin")) {
            Card original=actor.getCardsIn(ZoneType.Library).stream().filter(c->c.getName().equals(sourceName)).findFirst().orElseThrow();
            sourceCard=game.getAction().moveToHand(original,null);
        } else sourceCard=pose(actor,sourceName);
        resolve(game); actor.setLife(2,null);enemy.setLife(1,null);game.getAction().checkStateEffects(true);priority(game,actor,enemy);
        need(!game.isGameOver()&&game.getStack().isEmpty()&&actor.getLife()==2&&enemy.getLife()==1,"Settled nonterminal frontier");
        row.put("before_actor_view",new ActorBoundary(actor).snapshot(game.getView()));row.put("rng_before_choice",rng());
        List<SpellAbility> choices=((PlayerControllerAi)actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen=choices==null||choices.isEmpty()?null:choices.get(0);
        row.put("first_choice",ability(chosen));row.put("ordinary_Default_initial_callbacks",1);row.put("rng_after_choice",rng());
        // Extra diagnostic queries are strictly AFTER the immutable ordinary first choice.
        SpellAbility expected=sourceCard.getSpellAbilities().stream().filter(s->s.getApi()==api&&(scene.equals("DrawCostWin")?s.isSpell():s.isActivatedAbility())).findFirst().orElseThrow();
        expected.setActivatingPlayer(actor);
        AiAbilityDecision diagnostic=SpellApiToAi.Converter.get(expected).canPlayWithSubs(actor,expected);
        row.put("postchoice_native_decision",diagnostic.decision().name());row.put("postchoice_native_rating",diagnostic.rating());
        row.put("postchoice_native_cost_payable",ComputerUtilCost.canPayCost(expected,actor,false));
        boolean selected=chosen!=null&&chosen.getHostCard().getId()==sourceCard.getId()&&chosen.getApi()==api;
        List<String> failed=new ArrayList<>();if(!selected)failed.add("Missed immediate native sacrifice-trigger win");
        boolean paid=ComputerUtil.playStack(selected?chosen:expected,actor,game);need(paid,"Actual selected/control source must pay");resolve(game);
        boolean won=game.isGameOver()&&actor.hasWon()&&enemy.hasLost();need(selected||won,"Post-decline paid control must actually win");
        if(!won)failed.add("Selected native line failed to win");
        row.put("actual_paid",paid);row.put("actual_native_win",won);row.put("manual_control_not_AI_success",!selected);row.put("actor_life_after",actor.getLife());row.put("enemy_life_after",enemy.getLife());
        row.put("failures",failed);row.put("status",failed.isEmpty()?"PASS":"POLICY_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private report directory argument");
        Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(2026110617L));
        NativeSacrificeTiming6 audit = new NativeSacrificeTiming6(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int pass = 0, red = 0, errors = 0, index = 0;
        for (String scene : List.of("TokenCostWin", "DrawCostWin", "ScryCostWin")) {
            long seed = 2026110617L + index++;
            for (int seat = 0; seat < 2; seat++) {
                Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", seed));
                try { audit.check(seed, seat, scene, row); if (row.get("status").equals("PASS")) pass++; else red++; }
                catch (Throwable error) { errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName()); row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err); }
                Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n");
                System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
            }
        }
        Map<String, Object> summary = Map.of("label", "CONTROLLED-NATIVE-SACRIFICE-TIMING6", "total", 6, "pass", pass,
                "policy_red", red, "harness_errors", errors, "natural_games", 0, "ordinary_Default_initial_callbacks", 6,
                "forced_AI_actions_or_winners", false, "RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n");
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
