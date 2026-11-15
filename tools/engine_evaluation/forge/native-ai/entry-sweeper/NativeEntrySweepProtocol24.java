// SPDX-License-Identifier: GPL-3.0-or-later
// INTERNAL PROTOCOL ONLY. Canonical baseline versus explicitly labelled metadata mutations/spies.
// No ordinary AI-choice/game-win certificate; no payment, resolver or chooser is invoked by this audit.
package forge.evaluation;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import forge.ai.*;
import forge.deck.Deck;
import forge.game.*;
import forge.game.ability.AbilityFactory;
import forge.game.ability.AbilityKey;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.SpellAbilityCondition;
import forge.game.spellability.SpellAbilityVariables;
import forge.game.staticability.StaticAbility;
import forge.game.staticability.StaticAbilityMode;
import forge.game.trigger.Trigger;
import forge.game.trigger.TriggerType;
import forge.game.zone.ZoneType;
import forge.localinstance.properties.ForgePreferences.FPref;
import forge.model.FModel;
import forge.util.MyRandom;
import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeEntrySweepProtocol24 extends AITest {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final long SEED = 2026110743L;
    private static final List<String> SCENES = List.of("CANONICAL_ORIGINAL", "TYPED_UPKEEP_ONLY",
            "SELF_CREATURE_MISMATCH", "OVERRIDE_GAINLIFE", "OVERRIDE_API_MISMATCH", "OVERRIDE_TYPED_KICKED",
            "UNKNOWN_CHAIN_SVAR_SPY", "NON_NATIVE_X_DECLARATION", "PUBLIC_DISABLE_TRIGGERS",
            "PUBLIC_HUMILITY_CONSERVATIVE", "HIDDEN_CONTEXT_BODY_SPY", "SELF_SELECTOR_COMMA_UNION");
    private static void need(boolean ok, String message) {
        if (!ok) throw new IllegalStateException("HARNESS: " + message);
    }
    @Override protected Card createCard(String name, Player p) {
        Card c = super.createCard(name, p); c.setCollectible(true); return c;
    }
    private static Card library(Player p, String name) {
        return p.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
    }
    private static Card pose(Player p, String name) {
        return p.getGame().getAction().moveToPlay(library(p, name), p, null, AbilityKey.newMap());
    }
    private static String rng() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) { out.writeObject(MyRandom.getRandom()); }
        return Base64.getEncoder().encodeToString(bytes.toByteArray());
    }
    private static Map<String, Integer> counters() throws Exception {
        Map<String, Integer> result = new TreeMap<>();
        for (Class<?> c : List.of(SpellAbility.class, Trigger.class, StaticAbility.class)) {
            Field f = c.getDeclaredField("maxId"); f.setAccessible(true); result.put(c.getName(), f.getInt(null));
        }
        return result;
    }
    private static final class BodySpyStatic extends StaticAbility {
        boolean armed; int bodyReads;
        BodySpyStatic(Card host) {
            super("Mode$ Continuous | Affected$ Creature | AddPower$ 0 | AddToughness$ 0", host, host.getCurrentState());
        }
        @Override public Set<StaticAbilityMode> getMode() {
            if (armed) { bodyReads++; throw new IllegalStateException("INTERNAL_PROTOCOL_HIDDEN_BODY_READ"); }
            return super.getMode();
        }
    }
    private static final class VarsSpy implements IHasSVars {
        int reads;
        @Override public String getSVar(String key) { reads++; throw new IllegalStateException("INTERNAL_PROTOCOL_UNKNOWN_SVAR_READ"); }
        @Override public boolean hasSVar(String key) { reads++; throw new IllegalStateException("INTERNAL_PROTOCOL_UNKNOWN_SVAR_READ"); }
        @Override public Map<String, String> getSVars() { reads++; throw new IllegalStateException("INTERNAL_PROTOCOL_UNKNOWN_SVAR_READ"); }
        @Override public void setSVar(String key, String value) { throw new UnsupportedOperationException(); }
        @Override public void setSVars(Map<String, String> values) { throw new UnsupportedOperationException(); }
        @Override public void removeSVar(String key) { throw new UnsupportedOperationException(); }
    }
    private void check(String scene, int seat, Method classify, Method bodyCheck, Map<String, Object> row) throws Exception {
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Deck d = new Deck("internal-entry-sweep-" + i);
            if (i == seat) {
                d.getMain().add("The Meathook Massacre", 1); d.getMain().add("Nissa, Who Shakes the World", 1);
                d.getMain().add("Swamp", 58);
            } else {
                d.getMain().add("Elesh Norn, Mother of Machines", 1); d.getMain().add("Humility", 1);
                d.getMain().add("Forest", 58);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("internal-entry-sweep-" + i, null); lobby.setAiProfile("Default");
            registered.add(new RegisteredPlayer(d).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-ENTRY-SWEEP-PROTOCOL24"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player p : game.getPlayers()) {
            for (var entry : p.getRegisteredPlayer().getDeck().getMain())
                for (int i = 0; i < entry.getValue(); i++) addCardToZone(entry.getKey().getName(), p, ZoneType.Library);
            need(p.getAllCards().size() == 60 && p.getRegisteredPlayer().getDeck().getMain().countAll() == 60,
                    "Full declared registered60 originals per seat");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN2, actor, 8);
        game.getPhaseHandler().onStackResolved();
        for (int i = 0; i < 5; i++) pose(actor, "Swamp");
        Card hook = game.getAction().moveToHand(library(actor, "The Meathook Massacre"), null);
        Card nissa = game.getAction().moveToHand(library(actor, "Nissa, Who Shakes the World"), null);
        if (scene.equals("PUBLIC_DISABLE_TRIGGERS")) pose(enemy, "Elesh Norn, Mother of Machines");
        if (scene.equals("PUBLIC_HUMILITY_CONSERVATIVE")) pose(enemy, "Humility");
        game.getAction().checkStateEffects(true);
        game.getTriggerHandler().runWaitingTriggers(); game.getStack().addAllTriggeredAbilitiesToStack();
        need(game.getStack().isEmpty() && !game.isGameOver(), "Canonical setup has no pending rules action");
        SpellAbility root = hook.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
        SpellAbility rival = nissa.getSpellAbilities().stream().filter(SpellAbility::isSpell).findFirst().orElseThrow();
        root.setActivatingPlayer(actor); rival.setActivatingPlayer(actor);
        Trigger trigger = hook.getTriggers().stream().filter(t -> t.getMode() == TriggerType.ChangesZone
                && "Battlefield".equals(t.getParam("Destination"))).findFirst().orElseThrow();
        BodySpyStatic hiddenSpy = null; VarsSpy varsSpy = null;
        String originalExecute = trigger.getParam("Execute");
        if (scene.equals("TYPED_UPKEEP_ONLY")) trigger.setTriggerPhases(EnumSet.of(PhaseType.UPKEEP));
        if (scene.equals("SELF_CREATURE_MISMATCH")) trigger.getMapParams().put("ValidCard", "Creature.Self");
        if (scene.equals("SELF_SELECTOR_COMMA_UNION")) trigger.getMapParams().put("ValidCard", "Card.Self,Artifact.Other");
        if (scene.startsWith("OVERRIDE_")) {
            SpellAbility effective = AbilityFactory.getAbility(trigger.getSVar(originalExecute), hook);
            effective.setActivatingPlayer(actor);
            if (scene.equals("OVERRIDE_GAINLIFE")) effective = AbilityFactory.getAbility("DB$ GainLife | Defined$ You | LifeAmount$ 2", hook);
            if (scene.equals("OVERRIDE_API_MISMATCH")) effective.setApi(ApiType.GainLife);
            if (scene.equals("OVERRIDE_TYPED_KICKED")) {
                Field f = SpellAbilityVariables.class.getDeclaredField("kicked"); f.setAccessible(true);
                f.setBoolean(effective.getConditions(), true);
                need(!effective.getMapParams().containsKey("Condition"), "Typed kicked mutation intentionally absent from map");
            }
            trigger.setOverridingAbility(effective);
        }
        if (scene.equals("UNKNOWN_CHAIN_SVAR_SPY")) {
            Field overrideField = forge.game.TriggerReplacementBase.class.getDeclaredField("overridingAbility"); overrideField.setAccessible(true); overrideField.set(trigger, null);
            need(trigger.getOverridingAbility() == null, "Explicit test-only printed-path metadata reset"); trigger.getMapParams().put("Execute", "ProtocolChain");
            trigger.setSVar("ProtocolChain", "DB$ PumpAll | ValidCards$ Creature | NumAtt$ -X | NumDef$ -X | IsCurse$ True | SubAbility$ OpaqueBody");
            varsSpy = new VarsSpy();
        }
        if (scene.equals("NON_NATIVE_X_DECLARATION")) {
            Field overrideField = forge.game.TriggerReplacementBase.class.getDeclaredField("overridingAbility"); overrideField.setAccessible(true); overrideField.set(trigger, null);
            need(trigger.getOverridingAbility() == null, "Explicit test-only printed-path metadata reset"); trigger.setSVar("X", "Count$Valid Creature");
        }
        if (scene.equals("HIDDEN_CONTEXT_BODY_SPY")) {
            Card hidden = pose(enemy, "Forest"); need(hidden.turnFaceDown(true), "Labelled test-only face-down context setup");
            hiddenSpy = new BodySpyStatic(hidden); hidden.addStaticAbility(hiddenSpy);
            need(!hidden.getView().canFaceDownBeShownTo(actor.getView()), "Context really hidden from observer");
            hiddenSpy.armed = true;
        }
        row.put("label", "INTERNAL_PROTOCOL_NOT_CANONICAL_GAME_OR_POLICY_CERTIFICATE");
        row.put("canonical_original_programs_loaded", true); row.put("registered_totals", List.of(60, 60));
        row.put("metadata_mutated_for_protocol", !scene.equals("CANONICAL_ORIGINAL"));
        row.put("native_source_matches_trigger_filter", trigger.matchesValidParam("ValidCard", hook));
        row.put("native_trigger_phase_allowed", trigger.phasesCheck(game));
        row.put("map_has_Phase", trigger.getMapParams().containsKey("Phase"));
        SpellAbility overrideBefore = trigger.getOverridingAbility(); Integer xBefore = root.getXManaCostPaid();
        Map<String, Integer> idsBefore = counters(); String rngBefore = rng();
        boolean actual = (Boolean) classify.invoke(null, root);
        boolean expected = scene.equals("CANONICAL_ORIGINAL");
        boolean comparatorOk = true;
        if (expected) {
            int ab = ComputerUtilAbility.saEvaluator.compare(root, rival);
            int ba = ComputerUtilAbility.saEvaluator.compare(rival, root);
            int repeat = ComputerUtilAbility.saEvaluator.compare(root, rival);
            comparatorOk = ab < 0 && ba > 0 && Integer.signum(ab) == Integer.signum(repeat)
                    && ComputerUtilAbility.saEvaluator.compare(root, root) == 0;
            row.put("canonical_comparator_sign", Integer.signum(ab));
        }
        if (varsSpy != null) {
            Map<String, String> bad = new LinkedHashMap<>(AbilityFactory.getMapParams(trigger.getSVar("ProtocolChain")));
            need(!(Boolean) bodyCheck.invoke(null, bad, varsSpy, root), "Unknown chained body rejected by direct guard");
            need(varsSpy.reads == 0, "Unknown SVar spy never dereferenced");
        }
        boolean stable = rngBefore.equals(rng()) && idsBefore.equals(counters())
                && trigger.getOverridingAbility() == overrideBefore && Objects.equals(xBefore, root.getXManaCostPaid())
                && actor.getCardsIn(ZoneType.Hand).size() == 2 && actor.getLandsInPlay().size() == 5
                && actor.getLandsInPlay().stream().noneMatch(Card::isTapped) && actor.getManaPool().isEmpty()
                && game.getStack().isEmpty() && actor.getAllCards().size() == 60 && enemy.getAllCards().size() == 60;
        int spyReads = hiddenSpy == null ? 0 : hiddenSpy.bodyReads;
        need(stable && spyReads == 0, "Classifier/comparator purity or hidden-body fence failed");
        row.put("expected_classifier", expected); row.put("actual_classifier", actual);
        row.put("RNG_object_counters_override_X_and_physical_state_unchanged", stable);
        row.put("hidden_static_body_reads", spyReads); row.put("unknown_svar_reads", varsSpy == null ? 0 : varsSpy.reads);
        row.put("ordinary_AI_callbacks", 0); row.put("native_game_over", game.isGameOver());
        row.put("status", actual == expected && comparatorOk ? "PASS" : "PROTOCOL_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 1, "Fresh private output directory"); Path out = Path.of(args[0]);
        MyRandom.setRandom(new Random(SEED));
        NativeEntrySweepProtocol24 audit = new NativeEntrySweepProtocol24(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        Class<?> sortKey = Class.forName("forge.ai.ComputerUtilAbility$SortKey");
        Method classify = sortKey.getDeclaredMethod("hasKnownEntryCreatureSweep", SpellAbility.class); classify.setAccessible(true);
        Method bodyCheck = sortKey.getDeclaredMethod("isSupportedEntrySweep", Map.class, IHasSVars.class, SpellAbility.class); bodyCheck.setAccessible(true);
        int pass = 0, red = 0, errors = 0;
        for (String scene : SCENES) for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>(); row.put("scene", scene); row.put("seat", seat); row.put("seed", SEED);
            try {
                audit.check(scene, seat, classify, bodyCheck, row);
                if (row.get("status").equals("PASS")) pass++; else red++;
            } catch (Throwable e) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", e.getClass().getName());
                row.put("error", String.valueOf(e.getMessage())); e.printStackTrace(System.err);
            }
            Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW);
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = new LinkedHashMap<>(); summary.put("label", "INTERNAL-ENTRY-SWEEP-PROTOCOL24");
        summary.put("total", 24); summary.put("pass", pass); summary.put("protocol_red", red); summary.put("harness_errors", errors);
        summary.put("ordinary_AI_callbacks", 0); summary.put("natural_games", 0); summary.put("seed", SEED); summary.put("seed_installations", 1);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
