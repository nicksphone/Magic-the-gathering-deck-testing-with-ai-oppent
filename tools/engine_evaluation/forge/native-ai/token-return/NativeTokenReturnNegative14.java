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
import java.nio.file.StandardOpenOption;
import java.util.*;

public final class NativeTokenReturnNegative14 extends AITest {
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
    private static Card actualCardRef(Game game, Card previous) {
        Card current = game.getCardState(previous, null);
        need(current != null && current.getId() == previous.getId(), "Actual native card reference after movement");
        return current;
    }
    private static Map<String, Object> state(Game game, Player actor, Player enemy) throws Exception {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("actor_life", actor.getLife()); value.put("enemy_life", enemy.getLife());
        value.put("native_game_over", game.isGameOver()); value.put("native_stack_empty", game.getStack().isEmpty());
        value.put("Food", food(actor).stream().map(c -> Map.of("id", c.getId(), "is_token", c.isToken(), "tapped", c.isTapped())).toList());
        value.put("Forests", actor.getCardsIn(ZoneType.Battlefield).stream().filter(c -> c.getName().equals("Forest"))
                .map(c -> Map.of("id", c.getId(), "tapped", c.isTapped())).toList());
        value.put("actor_view", new ActorBoundary(actor).snapshot(game.getView())); value.put("rng", rng());
        return value;
    }
    private static final List<String> SCENES = List.of("Nonlethal", "ForeignOwner", "GrafCage", "Hushbringer",
            "JadeMageWrongToken", "PlatinumAngel", "GooseUnfunded");
    private static Card poseOwned(Player owner, Player controller, String name) {
        Card original = owner.getCardsIn(ZoneType.Library).stream().filter(c -> c.getName().equals(name)).findFirst().orElseThrow();
        Card moved = owner.getGame().getAction().moveToPlay(original, controller, null, AbilityKey.newMap());
        // moveToPlay selects a battlefield zone; historical foreign control is a separate native field.
        if (!owner.equals(controller)) moved.setController(controller, owner.getGame().getNextTimestamp());
        return moved;
    }
    private void check(int seat, String scene, boolean requireHelper, Map<String, Object> row) throws Exception {
        row.put("rng_before_fixture_construction", rng());
        boolean foreign = scene.equals("ForeignOwner"), jade = scene.equals("JadeMageWrongToken");
        boolean unfunded = scene.equals("GooseUnfunded");
        String sourceName = jade ? "Jade Mage" : "Gilded Goose";
        String blocker = switch (scene) {
            case "GrafCage" -> "Grafdigger's Cage";
            case "Hushbringer" -> "Hushbringer";
            case "PlatinumAngel" -> "Platinum Angel";
            default -> null;
        };
        List<RegisteredPlayer> registered = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            Deck deck = new Deck("token-return-negative-seat-" + index);
            if (index == seat) {
                deck.getMain().add(sourceName, 1); deck.getMain().add("Witch's Oven", 1);
                if (!foreign) deck.getMain().add("Cauldron Familiar", 1);
                deck.getMain().add("Forest", foreign ? 58 : 57);
            } else {
                if (foreign) deck.getMain().add("Cauldron Familiar", 1);
                if (blocker != null) deck.getMain().add(blocker, 1);
                deck.getMain().add("Mountain", foreign || blocker != null ? 59 : 60);
            }
            LobbyPlayerAi lobby = new LobbyPlayerAi("token-return-negative-seat-" + index, null);
            lobby.setAiProfile("Default"); registered.add(new RegisteredPlayer(deck).setPlayer(lobby));
        }
        GameRules rules = new GameRules(GameType.Constructed); rules.setAllowCheatShuffle(false);
        Game game = new Game(registered, rules, new Match(rules, registered, "INTERNAL-PROTOCOL-TOKEN-RETURN-NEGATIVE14"));
        game.setAge(GameStage.Play); NativeNameMatchProbe.configureSearch(game, false);
        game.EXPERIMENTAL_RESTORE_SNAPSHOT = false;
        Player actor = game.getPlayers().get(seat), enemy = game.getPlayers().get(1 - seat);
        for (Player player : game.getPlayers()) {
            for (var entry : player.getRegisteredPlayer().getDeck().getMain())
                for (int count = 0; count < entry.getValue(); count++) addCardToZone(entry.getKey().getName(), player, ZoneType.Library);
            need(player.getRegisteredPlayer().getDeck().getMain().countAll() == 60 && player.getAllCards().size() == 60,
                    "Complete native registered60 originals");
        }
        game.getPhaseHandler().devModeSet(PhaseType.MAIN1, actor); game.getPhaseHandler().onStackResolved();
        List<Map<String, Object>> events = new ArrayList<>(); row.put("native_events_including_setup", events);
        game.subscribeToEvents(new Object() {
            @com.google.common.eventbus.Subscribe public void event(forge.game.event.GameEvent event) {
                Map<String, Object> value = new LinkedHashMap<>();
                value.put("index", events.size() + 1); value.put("event", event.getClass().getSimpleName());
                value.put("turn", game.getPhaseHandler().getTurn());
                if (event instanceof forge.game.event.GameEventSpellAbilityCast cast) {
                    value.put("source", cast.si().getSourceCard().getName()); value.put("source_id", cast.si().getSourceCard().getId());
                    value.put("is_spell", cast.sa().isSpell());
                }
                if (event instanceof forge.game.event.GameEventSpellAbilityCast
                        || event instanceof forge.game.event.GameEventSpellResolved) value.put("message", event.toString());
                events.add(value);
            }
        });
        row.put("registered_main_totals", List.of(60, 60)); row.put("setup_before_any_pose", state(game, actor, enemy));
        Card oven = pose(actor, "Witch's Oven");
        Card cat = poseOwned(foreign ? enemy : actor, actor, "Cauldron Familiar");
        need(cat.getOwner().equals(foreign ? enemy : actor) && cat.getController().equals(actor), "Trusted control pose does not change native owner");
        List<Card> spent = new ArrayList<>();
        for (int i = 0; i < (jade ? 2 : 4); i++) spent.add(pose(actor, "Forest"));
        resolve(game); row.put("setup_Cat_entry_before_life_assignment", state(game, actor, enemy));
        need(actor.getCreaturesInPlay().size() == 1 && food(actor).isEmpty(), "Only Cat can pay setup Oven");
        priority(game, actor, enemy);
        boolean ovenPaid = ComputerUtil.playStack(activation(actualCardRef(game, oven), actor, ApiType.Token), actor, game);
        row.put("setup_manual_Oven_paid", ovenPaid);
        need(ovenPaid && actualCardRef(game, oven).isTapped() && actualCardRef(game, cat).isInZone(ZoneType.Graveyard),
                "Real Oven tap and original Cat sacrifice");
        resolve(game);
        need(food(actor).size() == 1 && food(actor).get(0).isToken(), "Native Oven Food");
        Card source = pose(actor, sourceName); resolve(game);
        need(food(actor).size() == (jade ? 1 : 2) && food(actor).stream().allMatch(Card::isToken),
                "Only native Oven/Goose entry-generated setup Food");
        need(actualCardRef(game, source).isSick(), "Newly posed source cannot be a setup tap-mana source");
        row.put("setup_native_source_entry_before_life_assignment", state(game, actor, enemy));
        List<Card> oldFoods = new ArrayList<>(food(actor));
        for (int i = 0; i < oldFoods.size(); i++) {
            priority(game, actor, enemy); int lifeBefore = actor.getLife();
            boolean paid = ComputerUtil.playStack(activation(actualCardRef(game, oldFoods.get(i)), actor, ApiType.GainLife), actor, game);
            row.put("setup_manual_Food_" + i + "_paid", paid); need(paid, "Native Food actually pays two mana/tap/sacrifice");
            resolve(game);
            need(actor.getLife() == lifeBefore + 3 && food(actor).size() == oldFoods.size() - i - 1
                    && spent.stream().filter(c -> actualCardRef(game, c).isTapped()).count() == 2L * (i + 1), "Real Food cleanup and Forest payment");
            row.put("setup_Food_" + i + "_resolved_before_life_assignment", state(game, actor, enemy));
        }
        List<Card> fresh = new ArrayList<>();
        for (int i = 0; i < (unfunded ? 0 : jade ? 3 : 2); i++) fresh.add(pose(actor, "Forest"));
        row.put("trusted_standing_source_sickness_before", actualCardRef(game, source).isSick());
        // Explicit trusted historical READY pose, not a paid-cast or Haste qualification.
        actualCardRef(game, source).setSickness(false);
        row.put("trusted_standing_source_sickness_after", actualCardRef(game, source).isSick());
        if (blocker != null) pose(enemy, blocker);
        resolve(game);
        row.put("setup_all_outcomes_before_fixture_life_assignment", state(game, actor, enemy));
        int enemyLife = scene.equals("Nonlethal") ? 2 : 1;
        row.put("fixture_life_assignment", Map.of("actor", 2, "enemy", enemyLife));
        actor.setLife(2, null); enemy.setLife(enemyLife, null); game.getAction().checkStateEffects(true); priority(game, actor, enemy);
        need(!game.isGameOver() && game.getStack().isEmpty() && actor.getLife() == 2 && enemy.getLife() == enemyLife
                && food(actor).isEmpty() && actualCardRef(game, cat).isInZone(ZoneType.Graveyard)
                && actualCardRef(game, oven).isTapped() && !actualCardRef(game, source).isTapped() && !actualCardRef(game, source).isSick()
                && spent.stream().allMatch(c -> actualCardRef(game, c).isTapped())
                && fresh.stream().noneMatch(c -> actualCardRef(game, c).isTapped()) && actor.getCardsIn(ZoneType.Hand).isEmpty(), "Declared negative frontier");
        need(actor.getAllCards().stream().noneMatch(c -> c.getName().equals("Blood Artist")), "No Artist");
        need(actualCardRef(game, cat).getOwner().equals(foreign ? enemy : actor)
                && (foreign ? enemy : actor).getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> c.getId() == cat.getId()), "Native original Cat remains in owner's graveyard");
        need(actor.getController().getClass() == PlayerControllerAi.class
                && !((PlayerControllerAi) actor.getController()).getAi().usesSimulation(), "Default, MC off");
        row.put("before_actor_view", new ActorBoundary(actor).snapshot(game.getView())); row.put("rng_before_choice", rng());
        // First ordinary choice precedes helper and affordability diagnostics. Never play it.
        List<SpellAbility> choices = ((PlayerControllerAi) actor.getController()).chooseSpellAbilityToPlay();
        SpellAbility chosen = choices == null || choices.isEmpty() ? null : choices.get(0);
        row.put("first_choice", ability(chosen)); row.put("ordinary_Default_initial_callbacks", 1);
        row.put("first_choice_executed", false); row.put("first_choice_judged", unfunded); row.put("rng_after_choice", rng());
        row.put("after_choice_actor_view", new ActorBoundary(actor).snapshot(game.getView()));
        List<String> failed = new ArrayList<>();
        SpellAbility token = activation(actualCardRef(game, source), actor, ApiType.Token);
        if (requireHelper) {
            java.lang.reflect.Method helper = SpellAbilityAi.class.getDeclaredMethod("hasKnownWinningTokenReturn", Player.class, SpellAbility.class);
            need(helper.getReturnType() == boolean.class && java.lang.reflect.Modifier.isPrivate(helper.getModifiers())
                    && java.lang.reflect.Modifier.isStatic(helper.getModifiers()), "Exact planned private static boolean token-return helper ABI");
            helper.setAccessible(true);
            boolean result = (Boolean) helper.invoke(null, actor, token);
            row.put("postchoice_hasKnownWinningTokenReturn", result); row.put("helper_diagnostic_completed", true);
            if (result) failed.add("FALSE_TOKEN_RETURN_WIN_IN_" + scene);
        } else {
            row.put("helper_qualification", "OMITTED_CONTROLS_ONLY_NO_QUALIFICATION");
        }
        row.put("rng_after_diagnostics", rng());
        row.put("controls_are_manual_not_AI_success", true);
        priority(game, actor, enemy);
        boolean tokenPaid = ComputerUtil.playStack(activation(actualCardRef(game, source), actor, ApiType.Token), actor, game);
        row.put("manual_token_activation_paid", tokenPaid); resolve(game);
        if (unfunded) {
            need(!tokenPaid && food(actor).isEmpty() && actualCardRef(game, cat).isInZone(ZoneType.Graveyard), "Unfunded Goose must not produce Food");
            if (chosen != null) failed.add("UNFUNDED_GOOSE_FIRST_DEFAULT_MUST_PASS");
            row.put("manual_Cat_control", "NOT_ATTEMPTED_NO_FOOD");
        } else {
            need(tokenPaid && fresh.stream().allMatch(c -> actualCardRef(game, c).isTapped()), "Real native producer mana payment");
            if (jade) {
                List<Card> saprolings = actor.getCardsIn(ZoneType.Battlefield).stream()
                        .filter(c -> c.isToken() && c.getType().hasSubtype("Saproling")).toList();
                need(food(actor).isEmpty() && saprolings.size() == 1 && actualCardRef(game, cat).isInZone(ZoneType.Graveyard),
                        "Native Jade Mage creates Saproling, not Food; Cat has no payable return");
                row.put("actual_wrong_token_ids", saprolings.stream().map(Card::getId).toList());
                row.put("manual_Cat_control", "NOT_ATTEMPTED_NO_FOOD");
            } else {
                need(actualCardRef(game, source).isTapped() && food(actor).size() == 1 && food(actor).get(0).isToken(), "Native Goose creates one actual Food");
                row.put("actual_Goose_Food_id", food(actor).get(0).getId());
                if (foreign) {
                    need(actor.getCardsIn(ZoneType.Graveyard).stream().noneMatch(c -> c.getId() == cat.getId()), "No actor-owned Cat return card");
                    row.put("manual_Cat_control", "NOT_ATTEMPTED_FOREIGN_OWNER_NO_ACTOR_RETURN_CARD");
                } else {
                    priority(game, actor, enemy);
                    boolean catPaid = ComputerUtil.playStack(activation(actualCardRef(game, cat), actor, ApiType.ChangeZone), actor, game);
                    row.put("manual_Cat_return_paid", catPaid); need(catPaid, "Manual Cat return genuinely sacrifices generated Food"); resolve(game);
                    need(food(actor).isEmpty(), "Actual Cat cost consumed Food");
                    need(actualCardRef(game, cat).isInZone(scene.equals("GrafCage") ? ZoneType.Graveyard : ZoneType.Battlefield),
                            "Native Cage replacement or actual Cat battlefield return");
                }
            }
        }
        need(!game.isGameOver() && !actor.hasWon() && !enemy.hasLost() && game.getStack().isEmpty(), "Manual native negative control must be NONTERMINAL");
        int finalEnemyLife = scene.equals("PlatinumAngel") ? 0 : 1;
        int finalActorLife = scene.equals("Nonlethal") || scene.equals("PlatinumAngel") ? 3 : 2;
        need(enemy.getLife() == finalEnemyLife && actor.getLife() == finalActorLife, "Actual native negative life outcome");
        row.put("manual_native_game_over", game.isGameOver()); row.put("manual_actor_has_won", actor.hasWon());
        row.put("actor_life_after", actor.getLife()); row.put("enemy_life_after", enemy.getLife());
        row.put("after_manual_control", state(game, actor, enemy)); row.put("rng_after_native_outcome", rng());
        row.put("failures", failed); row.put("status", failed.isEmpty() ? requireHelper ? "PASS" : "CONTROL_PASS_UNQUALIFIED" : "NEGATIVE_RED");
    }
    public static void main(String[] args) throws Exception {
        need(args.length == 2, "Fresh private output directory plus explicit require-helper or controls-only mode; separate parent GO required");
        Path out = Path.of(args[0]); need(Files.isDirectory(out), "Runner-created private output directory");
        need(args[1].equals("require-helper") || args[1].equals("controls-only"), "Explicit helper qualification mode");
        boolean requireHelper = args[1].equals("require-helper");
        MyRandom.setRandom(new Random(2026110701L)); String initialRng = rng();
        NativeTokenReturnNegative14 audit = new NativeTokenReturnNegative14(); audit.initializeModel();
        FModel.getPreferences().setPref(FPref.FILTERED_HANDS, false); FModel.getPreferences().setPref(FPref.UI_RECORD_REPLAYS, false);
        int qualifiedPass = 0, controlPass = 0, red = 0, errors = 0, callbacks = 0, helperDiagnostics = 0;
        for (String scene : SCENES) for (int seat = 0; seat < 2; seat++) {
            Map<String, Object> row = new LinkedHashMap<>(Map.of("scene", scene, "seat", seat, "seed", 2026110701L,
                    "label", "INTERNAL-PROTOCOL", "mode", args[1]));
            try {
                audit.check(seat, scene, requireHelper, row);
                if (row.get("status").equals("PASS")) qualifiedPass++;
                else if (row.get("status").equals("CONTROL_PASS_UNQUALIFIED")) controlPass++;
                else red++;
            } catch (Throwable error) {
                errors++; row.put("status", "HARNESS_ERROR"); row.put("error_type", error.getClass().getName());
                row.put("error", String.valueOf(error.getMessage())); error.printStackTrace(System.err);
            }
            callbacks += ((Number) row.getOrDefault("ordinary_Default_initial_callbacks", 0)).intValue();
            if (Boolean.TRUE.equals(row.get("helper_diagnostic_completed"))) helperDiagnostics++;
            Files.writeString(out.resolve(scene + "-seat" + seat + ".private.json"), JSON.toJson(row) + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            System.out.println(JSON.toJson(Map.of("scene", scene, "seat", seat, "status", row.get("status")))); System.out.flush();
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("label", "INTERNAL-PROTOCOL-TOKEN-RETURN-NEGATIVE14"); summary.put("total", 14); summary.put("mode", args[1]);
        summary.put("qualified_pass", qualifiedPass); summary.put("control_pass_unqualified", controlPass);
        summary.put("negative_red", red); summary.put("harness_errors", errors); summary.put("ordinary_Default_initial_callbacks", callbacks);
        summary.put("helper_diagnostics_completed", helperDiagnostics); summary.put("helper_qualification_required", requireHelper);
        summary.put("helper_qualification_claimed", requireHelper && qualifiedPass == 14 && errors == 0 && red == 0);
        summary.put("seed", 2026110701L); summary.put("seed_installations", 1); summary.put("rng_after_seed_before_model", initialRng);
        summary.put("controls_are_manual_not_AI_success", true); summary.put("natural_games", 0); summary.put("expert_games", 0); summary.put("RNG_purity_asserted", false);
        Files.writeString(out.resolve("summary.private.json"), JSON.toJson(summary) + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        System.out.println(JSON.toJson(summary)); System.exit(errors > 0 ? 2 : red > 0 ? 1 : 0);
    }
}
