export type DeckItem = { quantity: number; card_name: string };

export type DeckRecord = {
  id: number;
  name: string;
  source: string;
  archetype_guess: string;
  mainboard: DeckItem[];
  sideboard: DeckItem[];
};

export type CardView = {
  id: string;
  name: string;
  mana_cost?: string;
  oracle_text?: string;
  image_uri?: string;
  card_faces?: {
    name?: string;
    mana_cost?: string;
    oracle_text?: string;
    type_line?: string;
    image_uri?: string;
  }[];
  tapped: boolean;
  summoning_sick: boolean;
  power: number | null;
  toughness: number | null;
  loyalty?: number | null;
  types: string[];
};

export type PlayerView = {
  id: number;
  name: string;
  life: number;
  library_count: number;
  hand_count: number;
  battlefield: CardView[];
  hand: { id: string; name: string; mana_cost?: string; oracle_text?: string; image_uri?: string; types: string[]; card_faces?: CardView["card_faces"] }[];
  graveyard_count: number;
  exile_count: number;
  mana_pool: Record<string, number>;
};

export type MatchState = {
  id: string;
  mode?: "player_vs_ai" | "ai_vs_ai" | "human_vs_human";
  controllers?: Record<string, "human" | "ai">;
  turn: number;
  active_player: number;
  priority_player: number;
  step: string;
  winner: number | null;
  score: Record<string, number>;
  pregame_pending?: boolean;
  mulligan_count?: Record<string, number>;
  kept_hands?: number[];
  priority_stops?: Record<string, string[]>;
  players: Record<string, PlayerView>;
  stack: { id: string; label: string; controller: number; effect_key: string }[];
  attackers?: string[];
  attack_targets?: Record<string, string>;
  blocks?: Record<string, string>;
  game_number?: number;
  best_of?: number;
  games_needed?: number;
  match_complete?: boolean;
  sideboard_sizes?: Record<string, number>;
  log: string[];
};

export type LegalMove = {
  type: string;
  card_id?: string;
  card_name?: string;
  mana_cost?: string;
  x_value?: number;
  cost_options?: {
    id: string;
    label: string;
    mana_cost: string;
    pay_life: number;
    discard_cards: number;
    sacrifice_creatures: number;
  }[];
  options?: string[];
  attackers?: { id: string; name: string }[];
  defenders?: { id: string; label: string; kind: string }[];
  blockers?: { id: string; name: string }[];
  targets?: { id: string; name: string }[];
  ability_index?: number;
  ability_label?: string;
  ability_delta?: number;
  reason?: string;
  target_hints?: {
    player_targets?: { id: number; name: string }[];
    creature_targets?: { id: string; name: string }[];
    planeswalker_targets?: { id: string; name: string }[];
    stack_targets?: { id: string; label: string }[];
    face_names?: string[];
    modes?: string[];
    choose_two_modes?: boolean;
    requires_x_value?: boolean;
    up_to_target_count?: number;
    supports_divide?: boolean;
  };
};
