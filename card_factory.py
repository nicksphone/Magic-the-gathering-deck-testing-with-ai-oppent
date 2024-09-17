# card_factory.py

from creature_card import CreatureCard
from land_card import LandCard
from instant_card import InstantCard
from sorcery_card import SorceryCard
from activated_ability import ActivatedAbility
from triggered_ability import TriggeredAbility

class CardFactory:
    """
    Factory class to create card instances by name.
    """
    def __init__(self):
        self.card_creators = {
            "Mountain": self.create_mountain,
            "Plains": self.create_plains,
            "Forest": self.create_forest,
            "Island": self.create_island,
            "Swamp": self.create_swamp,
            "Savannah Lions": self.create_savannah_lions,
            "Silvercoat Lion": self.create_silvercoat_lion,
            "Serra Angel": self.create_serra_angel,
            "Shivan Dragon": self.create_shivan_dragon,
            "Goblin Electromancer": self.create_goblin_electromancer,
            "Deadly Recluse": self.create_deadly_recluse,
            "Vampire Nighthawk": self.create_vampire_nighthawk,
            "Ascended Lawmage": self.create_ascended_lawmage,
            "Darksteel Golem": self.create_darksteel_golem,
            "Grapeshot": self.create_grapeshot,
            "Bloodbraid Elf": self.create_bloodbraid_elf,
            "Counterspell": self.create_counterspell,
            "Terror": self.create_terror,
            "Lightning Bolt": self.create_lightning_bolt,
            # Add more mappings as needed
        }

    def create_card(self, card_name):
        creator = self.card_creators.get(card_name)
        if creator:
            card = creator()
            return card
        else:
            return None

    # Card creation methods
    def create_mountain(self):
        return LandCard(name="Mountain", mana_type="Red")

    def create_plains(self):
        return LandCard(name="Plains", mana_type="White")

    def create_forest(self):
        return LandCard(name="Forest", mana_type="Green")

    def create_island(self):
        return LandCard(name="Island", mana_type="Blue")

    def create_swamp(self):
        return LandCard(name="Swamp", mana_type="Black")

    def create_savannah_lions(self):
        return CreatureCard(
            name="Savannah Lions",
            mana_cost={'White': 1},
            power=2,
            toughness=1,
            description="A quick and aggressive creature.",
            abilities=[]
        )

    def create_silvercoat_lion(self):
        return CreatureCard(
            name="Silvercoat Lion",
            mana_cost={'White': 1, 'Colorless': 1},
            power=2,
            toughness=2,
            description="A common creature.",
            abilities=[]
        )

    def create_serra_angel(self):
        return CreatureCard(
            name="Serra Angel",
            mana_cost={'White': 2, 'Colorless': 3},
            power=4,
            toughness=4,
            description="Flying, Vigilance",
            abilities=["Flying", "Vigilance"]
        )

    def create_shivan_dragon(self):
        activated_ability = ActivatedAbility(
            cost_function=lambda source_card: source_card.owner.pay_mana({'Red': 1}),
            effect=lambda game, player, source_card: self.boost_power(source_card),
            description="{Red}: Shivan Dragon gets +1/+0 until end of turn."
        )
        return CreatureCard(
            name="Shivan Dragon",
            mana_cost={'Red': 2, 'Colorless': 4},
            power=5,
            toughness=5,
            description="Flying",
            abilities=["Flying"],
            activated_abilities=[activated_ability]
        )

    def boost_power(self, source_card):
        source_card.power += 1
        # Reset power at end of turn (simplified)
        source_card.owner.game.add_end_of_turn_effect(lambda: setattr(source_card, 'power', source_card.base_power))

    def create_deadly_recluse(self):
        return CreatureCard(
            name="Deadly Recluse",
            mana_cost={'Green': 1, 'Colorless': 1},
            power=1,
            toughness=2,
            description="Deathtouch, Reach",
            abilities=["Deathtouch", "Reach"]
        )

    def create_vampire_nighthawk(self):
        return CreatureCard(
            name="Vampire Nighthawk",
            mana_cost={'Black': 1, 'Colorless': 2},
            power=2,
            toughness=3,
            description="Flying, Deathtouch, Lifelink",
            abilities=["Flying", "Deathtouch", "Lifelink"]
        )

    def create_ascended_lawmage(self):
        return CreatureCard(
            name="Ascended Lawmage",
            mana_cost={'White': 1, 'Blue': 1, 'Colorless': 2},
            power=3,
            toughness=2,
            description="Flying, Hexproof",
            abilities=["Flying", "Hexproof"]
        )

    def create_darksteel_golem(self):
        return CreatureCard(
            name="Darksteel Golem",
            mana_cost={'Colorless': 3},
            power=1,
            toughness=1,
            description="Indestructible",
            abilities=["Indestructible"]
        )

    def create_goblin_electromancer(self):
        return CreatureCard(
            name="Goblin Electromancer",
            mana_cost={'Red': 1, 'Blue': 1},
            power=2,
            toughness=2,
            description="Instant and sorcery spells you cast cost {1} less to cast.",
            abilities=[]  # Implement cost reduction in the game logic
        )

    def create_bloodbraid_elf(self):
        return CreatureCard(
            name="Bloodbraid Elf",
            mana_cost={'Red': 1, 'Green': 1, 'Colorless': 2},
            power=3,
            toughness=2,
            description="Haste, Cascade",
            abilities=["Haste"],
            keywords=["Cascade"]
        )

    def create_grapeshot(self):
        def effect(game, player, target):
            opponent = game.get_opponent(player)
            opponent.life_total -= 1
            game.logger.record(f"{player.name} deals 1 damage to {opponent.name} with Grapeshot")
            game.check_state_based_actions()

        return SorceryCard(
            name="Grapeshot",
            mana_cost={'Red': 1, 'Colorless': 1},
            effect=effect,
            description="Grapeshot deals 1 damage to any target. Storm (When you cast this spell, copy it for each spell cast before it this turn.)",
            keywords=["Storm"],
            target_required=False
        )

    def create_counterspell(self):
        def effect(game, player, target):
            if target in game.stack:
                game.stack.remove(target)
                game.logger.record(f"{target.name} is countered by {player.name}'s Counterspell")
            else:
                game.logger.record(f"{target.name} is no longer on the stack")

        return InstantCard(
            name="Counterspell",
            mana_cost={'Blue': 2},
            effect=effect,
            description="Counter target spell.",
            target_required=True
        )

    def create_terror(self):
        def effect(game, player, target):
            if target.zone == 'battlefield' and isinstance(target, CreatureCard):
                if 'Artifact' not in target.abilities and 'Black' not in target.abilities:
                    target.owner.battlefield.remove(target)
                    target.owner.graveyard.append(target)
                    game.logger.record(f"{target.name} is destroyed by {player.name}'s Terror")
                    game.check_state_based_actions()
                else:
                    game.logger.record(f"{target.name} cannot be targeted by Terror")
            else:
                game.logger.record(f"{target.name} is not a valid target for Terror")

        return InstantCard(
            name="Terror",
            mana_cost={'Black': 1, 'Colorless': 1},
            effect=effect,
            description="Destroy target nonartifact, nonblack creature. It can't be regenerated.",
            target_required=True
        )

    def create_lightning_bolt(self):
        def effect(game, player, target):
            if isinstance(target, CreatureCard):
                target.toughness -= 3
                game.logger.record(f"{target.name} takes 3 damage from Lightning Bolt")
                game.check_state_based_actions()
            else:
                target.life_total -= 3
                game.logger.record(f"{player.name} deals 3 damage to {target.name} with Lightning Bolt")
                game.check_state_based_actions()

        return InstantCard(
            name="Lightning Bolt",
            mana_cost={'Red': 1},
            effect=effect,
            description="Lightning Bolt deals 3 damage to any target.",
            target_required=True
        )
