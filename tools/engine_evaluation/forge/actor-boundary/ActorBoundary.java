// SPDX-License-Identifier: GPL-3.0-or-later
// Original prototype using the Forge Team/Card-Forge contributors' native APIs.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Preserve upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import forge.game.GameView;
import forge.game.card.CardView;
import forge.game.card.CardView.CardStateView;
import forge.game.player.Player;
import forge.game.player.PlayerView;
import forge.game.spellability.SpellAbilityView;
import forge.game.spellability.StackItemView;
import forge.game.zone.ZoneType;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

public final class ActorBoundary {
    private static final List<ZoneType> PHYSICAL_ZONES = List.of(ZoneType.Hand, ZoneType.Library,
            ZoneType.Graveyard, ZoneType.Battlefield, ZoneType.Exile, ZoneType.Command, ZoneType.Sideboard);
    private final Player actor;
    private Pending pending;

    private record Pending(String id, int min, int max, Map<String, Object> values) { }

    public ActorBoundary(Player actor) { this.actor = Objects.requireNonNull(actor); }

    // The host must call this on timeout, disconnect, input replacement and game end.
    public synchronized void invalidate() { pending = null; }

    // Called by the trusted receiver while the game is parked or on its mutator thread.
    // Copy scalars now: native reveal permissions may expire after the callback returns.
    public Map<String, Object> snapshot(GameView game) {
        if (game == null || game.getGame() != actor.getGame()) {
            throw new IllegalArgumentException("Foreign game");
        }
        List<Map<String, Object>> players = new ArrayList<>();
        for (PlayerView player : game.getPlayers()) {
            Map<String, Object> zones = new LinkedHashMap<>();
            // Flashback is a private virtual availability list, not a physical-zone count.
            // Variant decks need their own disclosure rules; never enumerate them implicitly.
            for (ZoneType zone : PHYSICAL_ZONES) {
                List<Map<String, Object>> visible = new ArrayList<>();
                for (CardView card : player.getCards(zone)) {
                    if (card.getZone() != null && card.canBeShownTo(actor.getView())) visible.add(card(card));
                }
                zones.put(zone.name(), Map.of("count", player.getZoneSize(zone), "visible_cards", visible));
            }
            players.add(Map.of("player_id", player.getId(), "name", player.getName(),
                               "life", player.getLife(), "zones", zones));
        }
        List<Map<String, Object>> stack = new ArrayList<>();
        for (StackItemView item : game.getStack()) {
            stack.add(Map.of("stack_id", item.getId(), "source", card(item.getSourceCard())));
        }
        return Map.of("actor_id", actor.getId(), "turn", game.getTurn(),
                      "phase", game.getPhase() == null ? "" : game.getPhase().name(),
                      "players", players, "stack", stack);
    }

    private Map<String, Object> face(CardStateView state) {
        return Map.of("name", state.getName(), "type", state.getType().toString(),
                      "mana_cost", state.getManaCost().toString(),
                      "oracle_text", Objects.requireNonNullElse(state.getOracleText(), ""),
                      "power", state.getPower(), "toughness", state.getToughness());
    }

    private Map<String, Object> card(CardView card) {
        if (card == null || card.getZone() == null) throw new IllegalArgumentException("Unclassified card");
        if (!card.canBeShownTo(actor.getView())) return Map.of("hidden", true);
        Map<String, Object> visible = new LinkedHashMap<>();
        visible.put("card_id", card.getId());
        visible.put("controller_id", card.getController().getId());
        visible.put("owner_id", card.getOwner().getId());
        visible.put("tapped", card.isTapped());
        visible.put("face_down", card.isFaceDown());
        visible.put("face", face(card.getCurrentState()));
        if (card.isFaceDown() && card.canFaceDownBeShownTo(actor.getView()) && card.hasAlternateState()) {
            visible.put("known_face", face(card.getAlternateState()));
        }
        return visible;
    }

    void requireCurrentStackItem(StackItemView item) {
        for (var entry : actor.getGame().getStack()) {
            if (entry.getView() == item && entry.getId() == item.getId()) return;
        }
        throw new IllegalArgumentException("Foreign, removed or aliased stack item");
    }

    Object describe(Object value) {
        if (value instanceof StackItemView item) {
            requireCurrentStackItem(item);
            return Map.of("stack_id",item.getId(),"source",card(item.getSourceCard()));
        }
        if (value instanceof CardView card) return card(card);
        if (value instanceof PlayerView player) return Map.of("player_id", player.getId(), "name", player.getName());
        if (value instanceof SpellAbilityView ability) {
            CardView host = ability.getHostCard();
            if (host == null || host.getZone() == null || !host.canBeShownTo(actor.getView()) ||
                    (host.isFaceDown() && !host.canFaceDownBeShownTo(actor.getView()))) {
                throw new IllegalArgumentException("Hidden ability description");
            }
            return Map.of("ability_id", ability.getId(), "description", ability.getDescription(), "source", card(host));
        }
        if (value instanceof String || value instanceof Boolean || value instanceof Integer) return value;
        if (value instanceof Enum<?> item) return item.name();
        throw new IllegalArgumentException("Unsupported native choice type");
    }

    public synchronized Map<String, Object> offer(String kind, List<?> choices, int min, int max) {
        if (kind == null || kind.isBlank() || choices == null || min < 0 || max < min || max > choices.size()) {
            throw new IllegalArgumentException("Invalid native choice bounds");
        }
        String id = UUID.randomUUID().toString();
        Map<String, Object> values = new LinkedHashMap<>();
        List<Map<String, Object>> offered = new ArrayList<>();
        for (Object value : choices) {
            Object description = describe(value);
            String token = UUID.randomUUID().toString();
            values.put(token, value);
            offered.add(Map.of("token", token, "display", description));
        }
        pending = new Pending(id, min, max, Map.copyOf(values));
        return Map.of("actor_id", actor.getId(), "request_id", id, "kind", kind,
                      "min", min, "max", max, "choices", offered);
    }

    // The host supplies caller from its authenticated session, never a client-chosen player id.
    public synchronized List<Object> answer(Player caller, String request, List<String> choices) {
        Pending p = pending;
        if (p == null || caller != actor || !p.id().equals(request) || choices == null ||
                choices.size() < p.min() || choices.size() > p.max() ||
                new HashSet<>(choices).size() != choices.size()) {
            throw new IllegalArgumentException("Invalid or stale answer");
        }
        List<Object> result = new ArrayList<>();
        for (String token : choices) {
            if (token == null || !p.values().containsKey(token)) throw new IllegalArgumentException("Unoffered choice");
            Object value = p.values().get(token);
            if (value instanceof StackItemView item) requireCurrentStackItem(item);
            result.add(value);
        }
        pending = null;
        return List.copyOf(result);
    }
}
