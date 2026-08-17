# -*- coding: utf-8 -*-
"""UI Agent — manages AI agents for the FableDan web game UI.

Wraps FableDan agents (Random / Rule / NumPy-model / Torch-model) behind a
unified interface for GameSession. Model agents also expose Q-values so the
frontend can show AI hints, mirroring the danlm UI.
"""

from __future__ import annotations

import os
import sys

# Make the fabledan package importable regardless of CWD.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np  # noqa: E402

from fabledan.agents import RandomAgent, RuleAgent  # noqa: E402
from fabledan.combos import PASS  # noqa: E402


def _find_ckpts():
    """Scan ckpts/ for .npz / .pt weights to offer as selectable agents."""
    ckpt_dir = os.path.join(_PROJECT_ROOT, "ckpts")
    found = []
    if os.path.isdir(ckpt_dir):
        for root, _dirs, files in os.walk(ckpt_dir):
            for f in sorted(files):
                if f.endswith((".npz", ".pt")):
                    found.append(os.path.join(root, f))
    return found


def _build_registry():
    """Dynamically build the agent registry.

    Always offers 'rule' and 'random'; additionally offers every checkpoint
    found under ckpts/ (or pointed to by FABLEDAN_CKPT env var), and any
    torch checkpoint if torch is importable.
    """
    reg = {
        "rule": {
            "name": "FableDan Rule",
            "description": "Greedy heuristic baseline (default)",
            "kind": "rule",
            "path": None,
        },
        "random": {
            "name": "Random",
            "description": "Plays uniformly at random",
            "kind": "random",
            "path": None,
        },
    }
    env_ckpt = os.environ.get("FABLEDAN_CKPT")
    ckpts = [env_ckpt] if env_ckpt else _find_ckpts()
    for i, path in enumerate(ckpts):
        if not path or not os.path.exists(path):
            continue
        base = os.path.basename(path)
        if path.endswith(".npz"):
            reg["model_%d" % i] = {
                "name": "Model %s" % base,
                "description": "NumPy checkpoint (%s)" % base,
                "kind": "numpy",
                "path": path,
            }
        elif path.endswith(".pt"):
            reg["model_%d" % i] = {
                "name": "Torch %s" % base,
                "description": "PyTorch checkpoint (%s)" % base,
                "kind": "torch",
                "path": path,
            }
    return reg


AGENT_REGISTRY = _build_registry()


class _AgentSlot:
    """One seat's agent. Decouples the engine's act() from Q-value access."""

    def __init__(self, config: dict):
        self.kind = config["kind"]
        self.path = config["path"]
        self._agent = None
        self._model = None

    def _ensure(self):
        if self._agent is not None:
            return self._agent
        if self.kind == "rule":
            self._agent = RuleAgent()
        elif self.kind == "random":
            self._agent = RandomAgent()
        elif self.kind == "numpy":
            from fabledan.model_np import NumpyModel
            self._model = NumpyModel(self.path)
            self._agent = _ModelAgent(self._model)
        elif self.kind == "torch":
            from fabledan.model_torch import load_ckpt
            from fabledan.agents import TorchAgent
            model, _ = load_ckpt(self.path)
            self._agent = TorchAgent(model)
        else:
            raise ValueError("unknown agent kind: %s" % self.kind)
        return self._agent

    def act(self, obs):
        return self._ensure().act(obs)

    def q_values(self, obs):
        """Q-values for every legal move, or None if not model-driven."""
        agent = self._ensure()
        if isinstance(agent, _ModelAgent):
            return agent.q_values(obs)
        return None


class _ModelAgent:
    """Adapter so NumpyAgent can expose Q-values for hints."""

    def __init__(self, model):
        from fabledan.agents import NumpyAgent
        self._inner = NumpyAgent(model)

    def act(self, obs):
        return self._inner.act(obs)

    def q_values(self, obs):
        from fabledan.encode import encode_decision
        toks, feats = encode_decision(obs)
        q = self._inner.model.q_values(toks, feats)
        return np.asarray(q, dtype=np.float64)


class UIAgent:
    """Manages 4 per-seat agents sharing one configuration."""

    def __init__(self, agent_key: str = "rule") -> None:
        if agent_key not in AGENT_REGISTRY:
            raise ValueError(
                "Unknown agent: %s. Available: %s"
                % (agent_key, list(AGENT_REGISTRY.keys()))
            )
        self.agent_key = agent_key
        config = AGENT_REGISTRY[agent_key]
        self.agent_name = config["name"]
        self._slots = [_AgentSlot(config) for _ in range(4)]

    def act(self, obs):
        return self._slots[obs["player"]].act(obs)

    def q_values(self, obs):
        """Q per legal move for the current player (None if not model)."""
        return self._slots[obs["player"]].q_values(obs)

    def top_k(self, obs, k: int = 3):
        """Top-k (index, q) moves by Q-value; falls back to the rule agent's
        choice when the agent is not model-driven."""
        q = self.q_values(obs)
        legal = obs["legal"]
        n = len(legal)
        if q is not None:
            k = min(k, n)
            order = np.argsort(q)[::-1][:k]
            return [(int(i), float(q[i])) for i in order]
        # Non-model agent: recommend the agent's own pick as a single hint.
        idx = self.act(obs)
        return [(idx, None)]

    @staticmethod
    def list_agents():
        return [
            {"key": k, "name": v["name"], "description": v["description"]}
            for k, v in AGENT_REGISTRY.items()
        ]