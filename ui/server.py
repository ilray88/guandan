# -*- coding: utf-8 -*-
"""FastAPI server for the FableDan GuanDan web game UI.

Mirrors the danlm UI server (ui/server.py) endpoint contract:

  GET  /api/heartbeat          keep-alive (resets idle shutdown)
  GET  /api/agents             list selectable AI agents
  POST /api/new-game           {mode, agent} -> initial state
  GET  /api/state?game_id=     current state JSON
  POST /api/play               {game_id, action_index}
  POST /api/pass               {game_id}
  POST /api/hint               {game_id, enabled}
  POST /api/auto-play          {game_id, enabled}
  POST /api/confirm-start      {game_id}  (user acked round-start overlay)
  POST /api/reorder-hand       {game_id, card_order}
  POST /api/new-round          {game_id}  (single_round replay)
  POST /api/next-round         {game_id}  (full_game next round)

FableDan's engine resolves tribute automatically before the first decision,
so there are no interactive tribute endpoints (unlike danlm).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# Make the fabledan package importable regardless of CWD.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from game_manager import AI_THINK_DELAY, GameSession  # noqa: E402
from ui_agent import UIAgent  # noqa: E402

logger = logging.getLogger("fabledan.server")

# Idle auto-shutdown: exit if no heartbeat for this long (0 = disabled).
IDLE_TIMEOUT = int(os.environ.get("GUANDAN_IDLE_TIMEOUT", "0"))
_last_heartbeat: float = time.monotonic()

app = FastAPI(title="FableDan GuanDan")


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Disable browser caching during development."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheMiddleware)

sessions: dict[str, GameSession] = {}


def get_session(game_id: str) -> GameSession:
    if game_id not in sessions:
        raise HTTPException(status_code=404, detail="Game not found")
    return sessions[game_id]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class NewGameRequest(BaseModel):
    mode: str = "single_round"   # "single_round" | "full_game"
    agent: str = "rule"


class PlayRequest(BaseModel):
    game_id: str
    action_index: int


class GameIdRequest(BaseModel):
    game_id: str


class AutoPlayRequest(BaseModel):
    game_id: str
    enabled: bool


class HintToggleRequest(BaseModel):
    game_id: str
    enabled: bool


class ReorderRequest(BaseModel):
    game_id: str
    card_order: list[int]


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/heartbeat")
async def heartbeat():
    global _last_heartbeat
    _last_heartbeat = time.monotonic()
    return {"ok": True}


@app.get("/api/agents")
async def list_agents():
    return UIAgent.list_agents()


@app.post("/api/new-game")
async def new_game(req: NewGameRequest):
    agent = UIAgent(req.agent)
    session = GameSession(agent=agent, mode=req.mode)
    sessions[session.game_id] = session

    if req.mode == "full_game":
        state = session.new_full_game()
    else:
        state = session.new_round()

    # Wait for the user to ack the round-start overlay (confirm-start)
    # before any AI turns run — same behaviour as danlm's confirm-tribute.
    return state


@app.get("/api/state")
async def get_state(game_id: str):
    return get_session(game_id).to_state_json()


@app.post("/api/play")
async def play_action(req: PlayRequest):
    session = get_session(req.game_id)
    if session.phase != "playing":
        raise HTTPException(status_code=400, detail="Game not in playing phase")

    obs = session.current_obs
    if obs is None or obs["player"] != session.human_seat:
        raise HTTPException(status_code=400, detail="Not your turn")

    if req.action_index < 0 or req.action_index >= len(obs["legal"]):
        raise HTTPException(status_code=400, detail="Invalid action index")

    state = session.play_action(req.action_index)

    if state["phase"] == "playing" and not state["is_human_turn"]:
        asyncio.create_task(_run_ai_turns(session))
    return state


@app.post("/api/pass")
async def pass_action(req: GameIdRequest):
    session = get_session(req.game_id)
    if session.phase != "playing" or session.current_obs is None:
        raise HTTPException(status_code=400, detail="Cannot pass now")

    obs = session.current_obs
    # Find the pass move index (PASS_MOVE is always index 0 when following).
    pass_idx = None
    for i, m in enumerate(obs["legal"]):
        if m.type == 0:  # PASS
            pass_idx = i
            break
    if pass_idx is None:
        raise HTTPException(status_code=400, detail="Pass not available (you must play)")

    state = session.play_action(pass_idx)
    if state["phase"] == "playing" and not state["is_human_turn"]:
        asyncio.create_task(_run_ai_turns(session))
    return state


@app.post("/api/hint")
async def toggle_hint(req: HintToggleRequest):
    session = get_session(req.game_id)
    session.hint_enabled = req.enabled
    return session.to_state_json()


@app.post("/api/auto-play")
async def toggle_auto_play(req: AutoPlayRequest):
    session = get_session(req.game_id)
    session.auto_play = req.enabled
    state = session.to_state_json()

    if req.enabled and state["phase"] == "playing":
        asyncio.create_task(_run_ai_turns(session))
    return state


@app.post("/api/confirm-start")
async def confirm_start(req: GameIdRequest):
    """User acked the round-start overlay. Start AI turns if needed."""
    session = get_session(req.game_id)
    state = session.to_state_json()
    if state["phase"] == "playing" and not state["is_human_turn"]:
        asyncio.create_task(_run_ai_turns(session))
    return state


@app.post("/api/reorder-hand")
async def reorder_hand(req: ReorderRequest):
    session = get_session(req.game_id)
    session.hand_order = req.card_order
    return {"ok": True}


@app.post("/api/new-round")
async def new_round(req: GameIdRequest):
    """Start a new single round (replay)."""
    session = get_session(req.game_id)
    return session.new_round()


@app.post("/api/next-round")
async def next_round(req: GameIdRequest):
    """Next round of a full game."""
    session = get_session(req.game_id)
    if session.mode != "full_game":
        raise HTTPException(status_code=400, detail="Not a full game")
    return session.next_round()


# ---------------------------------------------------------------------------
# AI turn runner (async with delay)
# ---------------------------------------------------------------------------

async def _run_ai_turns(session: GameSession) -> None:
    """Run AI turns with a thinking delay until human's turn or round end."""
    try:
        while session.phase == "playing":
            obs = session.current_obs
            if obs is None:
                break
            if obs["player"] == session.human_seat and not session.auto_play:
                break
            await asyncio.sleep(AI_THINK_DELAY)
            if session.advance_one_ai() is None:
                break
    except Exception:
        logger.exception("AI turn crashed")


# ---------------------------------------------------------------------------
# Idle auto-shutdown watchdog
# ---------------------------------------------------------------------------

async def _idle_watchdog() -> None:
    while True:
        await asyncio.sleep(30)
        idle = time.monotonic() - _last_heartbeat
        if idle > IDLE_TIMEOUT:
            logger.info("No heartbeat for %.0fs, shutting down.", idle)
            os._exit(0)


@app.on_event("startup")
async def _start_watchdog():
    global _last_heartbeat
    _last_heartbeat = time.monotonic()
    if IDLE_TIMEOUT > 0:
        asyncio.create_task(_idle_watchdog())
        logger.info("Idle watchdog started (timeout=%ds)", IDLE_TIMEOUT)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


app.mount("/static", StaticFiles(directory=static_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)