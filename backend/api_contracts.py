"""Public input contracts. Effect payload parameters are never client choices."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

CardID = Annotated[str, Field(min_length=1, max_length=100)]
CardIDs = Annotated[list[CardID], Field(max_length=250)]
Nonnegative = Annotated[StrictInt, Field(ge=0, le=100000)]
PlayerID = Annotated[StrictInt, Field(ge=1, le=2)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeckEntry(InputModel):
    quantity: Annotated[StrictInt, Field(ge=1, le=250)]
    card_name: Annotated[str, Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def trim_name(self):
        self.card_name = self.card_name.strip()
        if not self.card_name:
            raise ValueError("Card name cannot be blank")
        return self


class DeckPairInput(InputModel):
    deck_a: Annotated[list[DeckEntry], Field(min_length=1, max_length=250)]
    deck_b: Annotated[list[DeckEntry], Field(min_length=1, max_length=250)]
    sandbox: StrictBool = False

    @model_validator(mode="after")
    def deck_sizes(self):
        for deck in (self.deck_a, self.deck_b):
            count = sum(entry.quantity for entry in deck)
            if count > 250 or (not self.sandbox and count < 60):
                raise ValueError("Mainboards require 60-250 cards; sandbox permits 1-250")
        return self


class Targets(InputModel):
    target_player: PlayerID | None = None
    target_card_id: CardID | None = None
    target_card_ids: CardIDs | None = None
    target_stack_id: CardID | None = None
    target_distribution: Annotated[dict[CardID, Nonnegative], Field(max_length=250)] | None = None
    x_value: Nonnegative | None = None
    selected_face_index: Annotated[StrictInt, Field(ge=0, le=20)] | None = None
    mode_text: Annotated[str, Field(max_length=4000)] | None = None
    mode_texts: Annotated[list[Annotated[str, Field(max_length=4000)]], Field(max_length=10)] | None = None
    search_card_ids: CardIDs | None = None
    topdeck_card_ids: CardIDs | None = None
    top_choice_hand_id: CardID | None = None
    top_choice_exile_id: CardID | None = None
    top_choice_bottom_ids: CardIDs | None = None
    pay_unless_counter: StrictBool | None = None
    replacement_source_id: CardID | None = None


class PassAction(InputModel):
    type: Literal["pass_priority"]


class MulliganAction(InputModel):
    type: Literal["mulligan"]


class KeepAction(InputModel):
    type: Literal["keep_hand"]
    bottom_card_ids: CardIDs = Field(default_factory=list)


class CardAction(InputModel):
    card_id: CardID


class LandAction(CardAction):
    type: Literal["play_land"]
    from_exile: StrictBool = False
    selected_face_index: Annotated[StrictInt, Field(ge=0, le=20)] | None = None
    entry_choice: Literal["tapped", "pay_two_life"] | None = None


class CostChoice(InputModel):
    id: Annotated[str, Field(min_length=1, max_length=100)]


class CastAction(CardAction):
    type: Literal["cast_spell"]
    targets: Targets = Field(default_factory=Targets)
    cost_choice: CostChoice | None = None
    selected_face_index: Annotated[StrictInt, Field(ge=0, le=20)] | None = None
    from_exile: StrictBool = False
    from_library: StrictBool = False
    from_graveyard: StrictBool = False
    escape_exile_ids: CardIDs | None = None


class CycleAction(CardAction):
    type: Literal["cycle_card"]
    x_value: Nonnegative = 0


class AbilityAction(CardAction):
    type: Literal["activate_ability", "activate_loyalty"]
    ability_index: Annotated[StrictInt, Field(ge=0, le=100)]
    targets: Targets = Field(default_factory=Targets)


class CrewAction(CardAction):
    type: Literal["crew"]
    crew_card_ids: CardIDs


class NinjutsuAction(CardAction):
    type: Literal["ninjutsu"]
    return_card_id: CardID


class EquipAction(CardAction):
    type: Literal["equip"]
    target_card_id: CardID


class TapAction(CardAction):
    type: Literal["tap_land_for_mana"]
    color: Literal["W", "U", "B", "R", "G", "C"] | None = None


class NonlandManaAction(CardAction):
    type: Literal["tap_nonland_for_mana"]
    color: Literal["W", "U", "B", "R", "G", "C"]


class BulkTapAction(InputModel):
    type: Literal["tap_lands_bulk"]
    land_name: Annotated[str, Field(min_length=1, max_length=200)]
    count: Annotated[StrictInt, Field(ge=1, le=250)]
    color: Literal["W", "U", "B", "R", "G", "C"] | None = None


class AttackAction(InputModel):
    type: Literal["attack"]
    attackers: CardIDs
    attack_targets: dict[CardID, CardID] = Field(default_factory=dict, max_length=250)
    bands: list[CardIDs] = Field(default_factory=list, max_length=125)


class BlockAction(InputModel):
    type: Literal["block"]
    blocks: dict[CardID, CardIDs] = Field(max_length=250)


class MechanicChoice(InputModel):
    type: Literal["choose_mechanic"]
    card_ids: CardIDs | None = None
    choice_id: CardID | None = None
    damage_assignment: Annotated[dict[CardID, Nonnegative], Field(max_length=250)] | None = None

    @model_validator(mode="after")
    def selection(self):
        if sum(value is not None for value in (self.card_ids, self.choice_id, self.damage_assignment)) != 1:
            raise ValueError("Supply exactly one mechanic choice payload")
        return self


class ReplacementChoice(InputModel):
    type: Literal["choose_replacement"]
    replacement_source_id: CardID


class TriggerChoice(InputModel):
    type: Literal["choose_trigger_order"]
    trigger_order: CardIDs


class TriggerTargetChoice(InputModel):
    type: Literal["choose_trigger_target"]
    stack_id: CardID
    target_card_id: CardID


class OptionalEffectChoice(InputModel):
    type: Literal["choose_optional_effect"]
    stack_id: CardID
    accept: StrictBool


Action = Annotated[PassAction | MulliganAction | KeepAction | LandAction | CastAction | CycleAction | AbilityAction | CrewAction | NinjutsuAction | EquipAction | TapAction | NonlandManaAction | BulkTapAction | AttackAction | BlockAction | MechanicChoice | ReplacementChoice | TriggerChoice | TriggerTargetChoice | OptionalEffectChoice, Field(discriminator="type")]


class ActionRequest(InputModel):
    player_id: PlayerID
    action: Action
