"""Shared series provenance and starting-player choice, independent of storage."""


def next_play_draw_chooser(winner: int, previous_chooser: int) -> int:
    if previous_chooser not in (1, 2) or winner not in (0, 1, 2):
        raise ValueError("A resolved two-player game and valid prior chooser are required")
    return previous_chooser if winner == 0 else 3 - winner


def game_seed(root_seed: int | None, game_number: int) -> int | None:
    if game_number < 1:
        raise ValueError("Game numbers are one-based")
    return root_seed + game_number - 1 if root_seed is not None else None
