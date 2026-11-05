// SPDX-License-Identifier: GPL-3.0-or-later
// Original integration prototype extending the Forge Team/Card-Forge AI.
// https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
// Retain upstream notices and the accompanying Forge GPL license.
package forge.evaluation;

import com.google.common.eventbus.Subscribe;
import forge.LobbyPlayer;
import forge.ai.NamedDiscard;
import forge.ai.PlayerControllerAi;
import forge.card.ICardFace;
import forge.game.Game;
import forge.game.ability.ApiType;
import forge.game.card.Card;
import forge.game.card.CardCollectionView;
import forge.game.card.CardView;
import forge.game.event.EventValueChangeType;
import forge.game.event.GameEventCardChangeZone;
import forge.game.event.GameEventZone;
import forge.game.player.Player;
import forge.game.player.PlayerView;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.model.FModel;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Predicate;

public final class PublicNameController extends PlayerControllerAi {
    private final Map<Integer, Map<String, Integer>> publicDecks;
    private final Map<Integer, Map<String, Integer>> knownHands = new HashMap<>();

    public PublicNameController(Game game, Player player, LobbyPlayer lobby,
                                Map<Integer, Map<String, Integer>> disclosedDecks) {
        super(game, player, lobby);
        Map<Integer, Map<String, Integer>> decks = new HashMap<>();
        disclosedDecks.forEach((id,cards) -> {
            if (cards.values().stream().anyMatch(n -> n == null || n <= 0)) {
                throw new IllegalArgumentException("Invalid disclosed card quantity");
            }
            decks.put(id,Map.copyOf(cards));
        });
        publicDecks = Map.copyOf(decks);
        game.subscribeToEvents(this);
    }

    // Only the host may supply disclosed lists. Never derive them from live hidden zones.
    private Map<String,Integer> publicPool(Player target) {
        return publicDecks.getOrDefault(target.getId(),Map.of());
    }

    private synchronized void remember(PlayerView owner, List<CardView> cards) {
        Map<String,Integer> names = new HashMap<>();
        for (CardView card : cards) names.merge(card.getCurrentState().getName(),1,Integer::sum);
        Map<String,Integer> prior=knownHands.computeIfAbsent(owner.getId(),id -> new HashMap<>());
        names.forEach((name,count) -> prior.merge(name,count,Math::max));
    }

    @Override
    public void reveal(CardCollectionView cards, ZoneType zone, Player owner, String message, boolean suffix) {
        super.reveal(cards,zone,owner,message,suffix);
        if (zone == ZoneType.Hand) remember(owner.getView(),cards.stream().map(Card::getView).toList());
    }

    @Override
    public void reveal(List<CardView> cards, ZoneType zone, PlayerView owner, String message, boolean suffix) {
        super.reveal(cards,zone,owner,message,suffix);
        if (zone == ZoneType.Hand) remember(owner,cards);
    }

    @Subscribe
    public synchronized void onZone(GameEventZone event) {
        if (event.zoneType() != ZoneType.Hand || event.player() == null) return;
        Map<String,Integer> known = knownHands.get(event.player().getId());
        if (known == null) return;
        if (event.mode() == EventValueChangeType.Cleared || event.mode() == EventValueChangeType.ComplexUpdate) {
            knownHands.remove(event.player().getId());
        }
    }

    @Subscribe
    public synchronized void onCommittedMove(GameEventCardChangeZone event) {
        if (event.from() == null || event.from().zoneType() != ZoneType.Hand || event.from().player() == null) return;
        if (event.to() != null && event.to().zoneType() == ZoneType.Hand &&
                event.from().player().equals(event.to().player())) return;
        Map<String,Integer> known=knownHands.get(event.from().player().getId());
        if (known == null) return;
        // Zone.Removed fires before destination assignment; classify only the completed move.
        Card current=event.card()==null ? null : getPlayer().getGame().findByView(event.card());
        CardView card=current==null ? null : current.getView();
        if (card != null && event.to() != null && card.getZone() == event.to().zoneType() &&
                card.canBeShownTo(getPlayer().getView()) && !card.isFaceDown()) {
            known.computeIfPresent(card.getCurrentState().getName(),(name,count) -> count-1);
        } else {
            // A concealed removal could be any known name: retain only guaranteed lower bounds.
            known.replaceAll((name,count) -> count-1);
        }
        known.values().removeIf(n -> n <= 0);
    }

    private synchronized Map<String,Integer> knownHand(Player target) {
        Map<String,Integer> result = new HashMap<>(knownHands.getOrDefault(target.getId(),Map.of()));
        Map<String,Integer> visible = new HashMap<>();
        for (Card card : target.getCardsIn(ZoneType.Hand)) {
            if (card.getView().canBeShownTo(getPlayer().getView()) && !card.isFaceDown()) {
                visible.merge(card.getName(),1,Integer::sum);
            }
        }
        visible.forEach((name,count) -> result.merge(name,count,Math::max));
        return result;
    }

    private String best(Map<String,Integer> candidates, Predicate<ICardFace> allowed) {
        String selected = "";
        long score = Long.MIN_VALUE;
        for (Map.Entry<String,Integer> item : new TreeMap<>(candidates).entrySet()) {
            ICardFace face = FModel.getMagicDb().getCommonCards().getFaceByName(item.getKey());
            if (face == null || !allowed.test(face)) continue;
            long value = item.getValue()*10000L + face.getManaCost().getCMC();
            if (value > score) { score=value; selected=face.getName(); }
        }
        return selected;
    }

    private Player millTarget(SpellAbility sa) {
        for (SpellAbility part=sa;part!=null;part=part.getSubAbility()) {
            if (part.getApi() == ApiType.Mill && part.usesTargeting() && !part.hasParam("FromBottom")) {
                for (var target : part.getTargets().getTargetEntities()) {
                    if (target instanceof Player player) return player;
                }
            }
        }
        return null;
    }

    private String fallback(Predicate<ICardFace> allowed) {
        Map<String,Integer> names = new HashMap<>();
        publicDecks.values().forEach(pool -> pool.forEach((name,count) -> names.merge(name,count,Integer::sum)));
        String known = best(names,allowed);
        if (!known.isEmpty()) return known;
        // With no relevant public deck information, make a legal uninformed guess, not a hidden-state read.
        return FModel.getMagicDb().getCommonCards().streamAllFaces().filter(allowed)
                .map(ICardFace::getName).sorted().findFirst().orElse("");
    }

    @Override
    public String chooseCardName(SpellAbility sa, Predicate<ICardFace> allowed, String valid, String message) {
        Player target;
        if (sa.hasParam("AILogic") && sa.getParam("AILogic").equals(NamedDiscard.LOGIC)) {
            target = NamedDiscard.discardTarget(sa);
            if (target == getPlayer()) return super.chooseCardName(sa,allowed,valid,message);
            if (target != null) {
                String known = best(knownHand(target),allowed);
                if (!known.isEmpty()) return known;
                String guess = best(publicPool(target),allowed);
                return guess.isEmpty() ? fallback(allowed) : guess;
            }
            return fallback(allowed);
        }
        if (sa.hasParam("AILogic") && !sa.getParam("AILogic").equals("MostProminentInHumanDeck")) {
            // Unchanged dedicated heuristics are outside this scoped correction, not certified information-fenced.
            return super.chooseCardName(sa,allowed,valid,message);
        }
        target = millTarget(sa);
        if (target != null && !target.getCardsIn(ZoneType.Library).isEmpty()) {
            Card top = target.getCardsIn(ZoneType.Library).get(0);
            if (top.getView().canBeShownTo(getPlayer().getView()) && !top.isFaceDown()) {
                String known = best(Map.of(top.getName(),1),allowed);
                if (!known.isEmpty()) return known;
            }
        }
        if (target == null && !getPlayer().getOpponents().isEmpty()) target=getPlayer().getOpponents().get(0);
        String guess = target == null ? "" : best(publicPool(target),allowed);
        return guess.isEmpty() ? fallback(allowed) : guess;
    }
}
