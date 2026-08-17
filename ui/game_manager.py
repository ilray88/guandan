# -*- coding: utf-8 -*-
"""Game session manager for the FableDan web UI.

Wraps the FableDan engine (GuandanRound + generator interface) and provides
a JSON-serializable state for the frontend. Mirrors the danlm UI architecture
(ui/game_manager.py) so the frontend contract stays familiar.

Modes:
  single_round  — one round at a random level with random tribute.
  full_game     — a whole game from level 2 to A; tribute is derived from the
                  previous round's finish order and the winning team levels up.
"""

from __future__ import annotations

import os
import random
import uuid

from fabledan.cards import (BJ, NUM_RANKS, RANK_NAMES, SUIT_NAMES, is_wildcard,
                            order_of, rank_of)
from fabledan.combos import (PASS, ROCKET, SFLUSH, STRAIGHT, TYPE_NAMES,
                             PASS_MOVE)
from fabledan.engine import (GuandanRound, forced_tribute_card, partner,
                             random_tribute_mode)

# AI "thinking" delay between consecutive AI plays (seconds).
# Overridable via env so tests / demos can speed up play.
AI_THINK_DELAY = float(os.environ.get("FABLEDAN_AI_DELAY", "1.5"))

# Level progression for full games: 2,3,...,K then A (rank index 0 = A).
LEVEL_SEQ = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0]

# Positions of the partner in the finish-order list -> level-up steps.
_STEPS = {1: 3, 2: 2, 3: 1}

# Move type -> short key used by the frontend i18n table.
_TYPE_KEYS = {
    PASS: "pass", 1: "single", 2: "pair", 3: "triple", 4: "full",
    5: "straight", 6: "plate", 7: "tube", 8: "bomb", 9: "sflush",
    10: "rocket",
}

SUIT_SYMBOLS = {0: "\u2665", 1: "\u2666", 2: "\u2660", 3: "\u2663"}  # h d s c
POSITION_NAMES = {1: "right", 2: "top", 3: "left"}
PLAYER_LABELS = {0: "You", 1: "Next", 2: "Partner", 3: "Prev"}


def level_name(level: int) -> str:
    return RANK_NAMES[level]


# ---------------------------------------------------------------------------
# card / move serialization
# ---------------------------------------------------------------------------

def _card_info(card: int, level: int) -> dict:
    r = rank_of(card)
    s = _suit_of(card)
    if r >= 13:  # jokers
        return {
            "card_int": card,
            "rank": "sj" if r == 13 else "bj",
            "display": "小王" if r == 13 else "大王",
            "suit": "joker",
            "suit_symbol": "\U0001f0cf",
            "is_wild": False,
            "is_level": False,
        }
    return {
        "card_int": card,
        "rank": RANK_NAMES[r],
        "display": RANK_NAMES[r],
        "suit": SUIT_NAMES[s],
        "suit_symbol": SUIT_SYMBOLS[s],
        "is_wild": is_wildcard(card, level),
        "is_level": (r == level),
    }


def _suit_of(card: int) -> int:
    """0=h 1=d 2=s 3=c; jokers -> -1 (same convention as fabledan.cards)."""
    b = card % 54
    return -1 if b >= 52 else b % 4


def _claim_rank(rank: int) -> str:
    return RANK_NAMES[rank]


def _move_cards_json(move, level: int) -> list[dict]:
    """Serialize the actual cards of a move for trick display.

    For wildcards (配子) the claimed rank is what the card represents, so we
    display the claimed rank with a W badge; non-wild cards show their face.
    """
    out = []
    for c, claim in zip(move.cards, move.claim_ranks):
        info = _card_info(c, level)
        if info["is_wild"]:
            # Show the claimed rank the wild card stands for.
            info["rank"] = _claim_rank(claim)
            info["display"] = _claim_rank(claim)
        out.append(info)
    return out


def _move_to_json(move, index: int, level: int) -> dict:
    if move.type == PASS:
        return {"index": index, "type": "pass", "type_name": "pass",
                "cards": [], "rank": None}
    cards = _move_cards_json(move, level)
    # Human-readable main rank (e.g. straight "3-7", bomb "5").
    rank = _rank_display(move)
    return {
        "index": index,
        "type": _TYPE_KEYS.get(move.type, TYPE_NAMES[move.type].lower()),
        "type_name": TYPE_NAMES[move.type].lower(),
        "cards": cards,
        "rank": rank,
    }


def _rank_display(move) -> str | None:
    if move.type == PASS:
        return None
    if move.type == ROCKET:
        return "火箭"
    if move.type in (STRAIGHT, SFLUSH):
        lows = [rank for rank in move.claim_ranks]
        return "%s-%s" % (RANK_NAMES[min(lows)], RANK_NAMES[max(lows)])
    if move.type == 6:  # plate (三连对): 3 consecutive pairs
        ranks = sorted(set(move.claim_ranks))
        return "%s-%s" % (RANK_NAMES[ranks[0]], RANK_NAMES[ranks[-1]])
    if move.type == 7:  # tube (钢板): 2 consecutive triples
        ranks = sorted(set(move.claim_ranks))
        return "%s-%s" % (RANK_NAMES[ranks[0]], RANK_NAMES[ranks[-1]])
    return RANK_NAMES[move.claim_ranks[0]]


def _sort_key(card: int, level: int):
    r = rank_of(card)
    if r == BJ:
        return (0, 0, 0)
    if r == 13:  # small joker
        return (0, 1, 0)
    return (1, -order_of(r, level), card)


def _sorted_hand(cards, level: int) -> list[dict]:
    return [_card_info(c, level) for c in sorted(cards, key=lambda c: _sort_key(c, level))]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class GameSession:
    """One interactive session (single round or full game) against the AI."""

    def __init__(self, agent, mode: str = "single_round") -> None:
        self.game_id = str(uuid.uuid4())
        self.mode = mode
        self.agent = agent          # UIAgent instance
        self.human_seat = 0
        self.auto_play = False
        self.hint_enabled = False

        # Engine state
        self.rnd: GuandanRound | None = None
        self._gen = None            # play_steps generator
        self.current_obs = None

        # UI state
        self.phase = "idle"         # idle | playing | round_over | game_over
        self.trick_plays: list[dict] = []
        self.result = None
        self.round_start_info = None
        self.hand_order: list[int] | None = None

        # Full-game state
        self.team_levels: list[int] = [1, 1]   # rank index, team 0 seats (0,2)
        self.round_number = 0

    # ------------------------------------------------------------------
    # Round / game creation
    # ------------------------------------------------------------------

    def new_round(self, seed: int | None = None) -> dict:
        """Start a new single round: random level + random tribute."""
        rng = random.Random(seed)
        level = rng.randrange(13)
        tribute = random_tribute_mode(rng)
        self.team_levels = [level, level]
        self.round_number = 1
        return self._start(level, tribute, rng, tribute_for=None)

    def new_full_game(self) -> dict:
        """Start a new full game (levels 2..A)."""
        self.mode = "full_game"
        self.team_levels = [1, 1]
        self.round_number = 1
        rng = random.Random()
        # First round: no tribute, human leads.
        return self._start(level=1, tribute=None, rng=rng, tribute_for=None)

    def next_round(self) -> dict:
        """Start the next round of a full game (level-up + tribute)."""
        if self.mode != "full_game" or self.result is None:
            return self.to_state_json()
        rng = random.Random()
        # Winner team advances based on finish order.
        fo = self.result["finish_order"]
        first = fo[0]
        wteam = 0 if first % 2 == 0 else 1
        pos_partner = fo.index(partner(first))
        steps = _STEPS[pos_partner]

        # If already at A and won again -> game over.
        level = self.team_levels[wteam]
        if level == 0:  # A
            self.phase = "game_over"
            self.result = {**self.result, "game_over": True}
            return self.to_state_json()

        idx = LEVEL_SEQ.index(level)
        new_level = LEVEL_SEQ[min(len(LEVEL_SEQ) - 1, idx + steps)]
        self.team_levels[wteam] = new_level
        self.round_number += 1

        # Tribute: double if 1st & 2nd are partners (双下), else single.
        if partner(fo[0]) == fo[1]:
            tribute = ("double", fo[3], fo[0])
        else:
            tribute = ("single", fo[3], fo[0])
        return self._start(new_level, tribute, rng, tribute_for=self.result)

    def _start(self, level: int, tribute, rng, tribute_for=None) -> dict:
        """Create the GuandanRound, run tribute, and enter playing phase."""
        self.result = None
        self.trick_plays = []
        self.hand_order = None

        self.rnd = GuandanRound(level, rng=rng, tribute_mode=tribute)
        self._gen = self.rnd.play_steps()
        try:
            self.current_obs = next(self._gen)
        except StopIteration:
            # Edge case: a round with a single legal move for everyone.
            self.current_obs = None
            self._finish_round()
            return self.to_state_json()

        self.phase = "playing"
        self.round_start_info = self._build_start_info(tribute)
        return self.to_state_json()

    # ------------------------------------------------------------------
    # Tribute info for the frontend
    # ------------------------------------------------------------------

    def _build_start_info(self, tribute) -> dict:
        assert self.rnd is not None
        info = {"level": self.rnd.lv, "level_name": level_name(self.rnd.lv),
                "first_player": self.rnd.lead_player, "tribute_type": "none",
                "givers": [], "receivers": [], "anti_holders": []}
        if not tribute:
            return info

        kind, last, first = tribute
        # Two big jokers among the payers -> anti-tribute (抗贡).
        payers = [last] if kind == "single" else [last, partner(last)]
        n_bj = sum(1 for p in payers
                   for c in self.rnd.hands[p] if rank_of(c) == BJ)
        if n_bj >= 2:
            info["tribute_type"] = "anti"
            info["anti_holders"] = payers
            return info

        info["tribute_type"] = kind
        info["givers"] = payers
        info["receivers"] = ([first] if kind == "single"
                             else [first, partner(first)])
        return info

    # ------------------------------------------------------------------
    # Playing
    # ------------------------------------------------------------------

    def play_action(self, action_index: int) -> dict:
        """Execute a move (human or AI). Returns updated state."""
        if self.phase != "playing" or self.current_obs is None:
            return self.to_state_json()

        obs = self.current_obs
        if obs["player"] != self.human_seat and not self.auto_play:
            return self.to_state_json()

        move = obs["legal"][action_index]
        self._record_play(obs, move)
        return self._advance(action_index)

    def advance_one_ai(self) -> dict | None:
        """Advance one AI turn. Returns state, or None if not AI's turn."""
        if self.phase != "playing" or self.current_obs is None:
            return None
        obs = self.current_obs
        if obs["player"] == self.human_seat and not self.auto_play:
            return None
        idx = self.agent.act(obs)
        move = obs["legal"][idx]
        self._record_play(obs, move)
        return self._advance(idx)

    def _record_play(self, obs, move) -> None:
        entry = {
            "player": obs["player"],
            "is_pass": move.type == PASS,
            "cards": _move_cards_json(move, obs["level"]),
            "type": _TYPE_KEYS.get(move.type, "unknown"),
            "rank": _rank_display(move),
        }
        self.trick_plays.append(entry)

    def _advance(self, action_index: int) -> dict:
        assert self._gen is not None
        try:
            new_obs = self._gen.send(action_index)
        except StopIteration:
            new_obs = None

        if new_obs is None:
            self._finish_round()
            return self.to_state_json()

        # New trick starts when the next obs has no lead (someone won).
        if new_obs["lead"] is None:
            self.trick_plays = []

        self.current_obs = new_obs
        return self.to_state_json()

    def _finish_round(self) -> None:
        assert self.rnd is not None
        ranking = self._ranking()
        rewards = self.rnd._rewards(ranking)
        first = ranking[0]
        human_won = self.human_seat in {first, partner(first)}
        self.result = {
            "finish_order": ranking,
            "rewards": {str(p): rewards[p] for p in range(4)},
            "human_won": human_won,
            "team_levels": [level_name(self.team_levels[0]),
                            level_name(self.team_levels[1])],
            "level": self.rnd.lv,
            "level_name": level_name(self.rnd.lv),
        }
        if self.mode == "full_game":
            first = ranking[0]
            wteam = 0 if first % 2 == 0 else 1
            at_a = self.team_levels[wteam] == 0
            self.result["game_over"] = at_a
            self.phase = "game_over" if at_a else "round_over"
        else:
            self.phase = "round_over"
        self.current_obs = None
        self._gen = None

    def _ranking(self) -> list[int]:
        """Final finish order (first .. last)."""
        assert self.rnd is not None
        fo = list(self.rnd.done_order)
        rest = [p for p in range(4) if p not in fo]
        return fo + rest

    # ------------------------------------------------------------------
    # Hints
    # ------------------------------------------------------------------

    def get_hints(self, k: int = 3) -> list[dict]:
        if self.current_obs is None:
            return []
        obs = self.current_obs
        top = self.agent.top_k(obs, k=k)
        out = []
        for idx, q in top:
            entry = _move_to_json(obs["legal"][idx], idx, obs["level"])
            entry["q_value"] = None if q is None else round(q, 4)
            out.append(entry)
        return out

    # ------------------------------------------------------------------
    # State serialization
    # ------------------------------------------------------------------

    def to_state_json(self) -> dict:
        if self.rnd is None:
            return {"game_id": self.game_id, "phase": self.phase,
                    "mode": self.mode}

        level = self.rnd.lv
        obs = self.current_obs
        hand_ids = sorted(self.rnd.hands[self.human_seat],
                          key=lambda c: _sort_key(c, level))
        hand = [_card_info(c, level) for c in hand_ids]

        opponents = []
        for seat in (1, 2, 3):
            finished = seat in self.rnd.done_order
            count = 0 if finished else len(self.rnd.hands[seat])
            opponents.append({
                "seat": seat,
                "position": POSITION_NAMES[seat],
                "label": PLAYER_LABELS[seat],
                "card_count": count,
                "is_teammate": seat == 2,
                "finished": finished,
                "finish_rank": (self.rnd.done_order.index(seat) + 1
                                if finished else None),
                "warn_low": 0 < count <= 10,
            })

        # Legal plays only when it's the human's turn (and not auto-play).
        legal_plays = []
        if (obs is not None and obs["player"] == self.human_seat
                and not self.auto_play):
            legal_plays = [_move_to_json(m, i, level)
                           for i, m in enumerate(obs["legal"])]

        # Current trick display: per-player latest play (passes included).
        trick = []
        latest = {}
        for e in self.trick_plays:
            latest[e["player"]] = e
        lead_owner = obs["lead_owner"] if obs else None
        for p in range(4):
            entry = latest.get(p)
            if entry is None:
                continue
            trick.append({**entry, "is_lead": (lead_owner == p)})

        hints = (self.get_hints() if self.hint_enabled and obs is not None
                 and obs["player"] == self.human_seat else [])

        return {
            "game_id": self.game_id,
            "phase": self.phase,
            "mode": self.mode,
            "round_level": level,
            "level_name": level_name(level),
            "team_levels": [level_name(self.team_levels[0]),
                            level_name(self.team_levels[1])],
            "round_number": self.round_number,
            "current_player": obs["player"] if obs else None,
            "lead_player": self.rnd.lead_player,
            "is_human_turn": (obs is not None
                              and obs["player"] == self.human_seat
                              and not self.auto_play),
            "hand": hand,
            "hand_count": len(hand),
            "opponents": opponents,
            "legal_plays": legal_plays,
            "trick_plays": trick,
            "finish_order": self.rnd.done_order,
            "auto_play": self.auto_play,
            "hint_enabled": self.hint_enabled,
            "hints": hints,
            "round_start_info": self.round_start_info,
            "result": self.result,
        }