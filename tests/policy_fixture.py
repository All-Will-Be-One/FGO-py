"""AST-only native policy fixtures; no device/kernel imports. Based on 2026-10-17 audit."""
from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "FGO-py"
KERNEL = SOURCE / "fgoKernel.py"


def methods(path):
    tree = ast.parse(path.read_text())
    return {
        (cls.name, fn.name): fn
        for cls in tree.body if isinstance(cls, ast.ClassDef)
        for fn in cls.body if isinstance(fn, ast.FunctionDef)
    }


NODES = methods(KERNEL)
metadata_tree = ast.parse((SOURCE / "fgoMetadata.py").read_text())
METADATA = next(ast.literal_eval(node.value) for node in metadata_tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "servantData"
                        for t in node.targets))


def body_hash(node):
    return hashlib.sha256(ast.dump(ast.Module(body=node.body, type_ignores=[]),
                                   include_attributes=False).encode()).hexdigest()


def extract(class_name, method_name, env):
    node = copy.deepcopy(NODES[class_name, method_name])
    node.decorator_list = []  # No logger decorators executed; exact body retained.
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(KERNEL), "exec"), env)
    return env[method_name]


def case(name, **overrides):
    c = dict(name=name, colors=[0, 1, 2, 0, 1], sealed=[False] * 5,
             ready=[False] * 3, gauges=[0, 0, 0],
             resist_codes=[0] * 8, critical_tenths=[0] * 5,
             field_ids=[1, 2, 7], owners=[0, 1, 2, 0, 1],
             enemies=[50000, 0, 0, 0, 0, 0], target=0,
             stage=1, stage_total=3, stage_turn=2,
             classic_np_priority=[7, 7, 7], probes=[])
    c.update(overrides)
    return c


class Detector:
    def __init__(self, c):
        self.c = c

    def getCardColor(self): return self.c["colors"].copy()
    def isCardSealed(self): return self.c["sealed"].copy()
    def isHouguReady(self): return self.c["ready"].copy()
    def getFieldServantNp(self, i): return self.c["gauges"][i]
    def getCardResist(self): return self.c["resist_codes"].copy()
    def getCardCriticalRate(self): return self.c["critical_tenths"].copy()
    def getCardGroup(self): return self.c["owners"].copy()
    def getCardServant(self, hint):
        ids = [self.c["field_ids"][i] for i in self.c["owners"]]
        assert all(i in hint for i in ids)
        return ids
    def getEnemyHp(self, i): return self.c["enemies"][i]


def run(c, class_name):
    detector = Detector(c)
    calls = c.get("calls_sink", [])
    # Callable snapshot factory with .cache, just like the method's dependency.
    class Detect:
        cache = detector
        def __new__(cls, *args, **kwargs): return detector

    def perform(pos, wait):
        calls.append({"keys": pos, "wait_ms": list(wait), "mock_only": True})

    env = {"Detect": Detect, "permutations": itertools.permutations,
           "fgoDevice": SimpleNamespace(device=SimpleNamespace(perform=perform)),
           "numpy": SimpleNamespace(
               argmax=lambda xs: max(range(len(xs)), key=lambda i: xs[i]),
               diff=lambda xs: [b - a for a, b in zip(xs, xs[1:])]),
           "logger": SimpleNamespace(debug=lambda *a, **k: None), "ScriptStop": RuntimeError}
    fn = extract(class_name, "selectCard", env)
    state = SimpleNamespace(stage=c["stage"], stageTotal=c["stage_total"],
                            stageTurn=c["stage_turn"],
                            enemy=c["enemies"].copy(), target=c["target"])
    if class_name == "Turn":
        state.servant = [(i,) + METADATA[i] for i in c["field_ids"]]
    else:
        state.servant = [0, 1, 2]
        state.friend = [False] * 3
        state.friendInfo = [[], [-1, -1]]
        state.orderChange = list(range(6))
        state.houguInfo = [[1, p] for p in c["classic_np_priority"]] + [[1, 7]] * 3
        info_fn = extract("ClassicTurn", "getHouguInfo", env)
        state.getHouguInfo = lambda pos, arg: info_fn(state, pos, arg)

    traces = {}
    counts = {"evaluate_returns": 0, "classic_score_returns": 0}
    locals_after = {}

    def trace(frame, event, arg):
        if frame.f_code.co_filename != str(KERNEL):
            return None
        if event != "return":
            return trace
        loc = frame.f_locals
        if frame.f_code.co_name == "selectCard":
            locals_after.update(loc)
        if "card" not in loc or not isinstance(loc["card"], (list, tuple)):
            return trace
        key = tuple(loc["card"])
        if frame.f_code.co_name == "evaluate":
            counts["evaluate_returns"] += 1
            traces.setdefault(key, {})["score"] = arg
        if frame.f_code.co_name == "<lambda>" and "firstBonus" in loc:
            entry = traces.setdefault(key, {})
            for name in ("firstBonus", "colorChain", "chainError"):
                if name in loc:
                    entry[name] = loc[name]
        if frame.f_code.co_name == "<lambda>" and "firstCardBonus" in loc:
            counts["classic_score_returns"] += 1
            entry = traces.setdefault(key, {})
            entry.update(score=arg, colorChain=loc.get("colorChain"),
                         firstCardBonus=loc["firstCardBonus"])
        return trace

    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        output = fn(state)
        # Named probes use the original nested evaluate closure retained by trace.
        if class_name == "Turn":
            evaluator = locals_after["evaluate"]
            for probe in c["probes"]:
                evaluator(probe)
    finally:
        sys.settrace(previous_trace)

    def compact(cards):
        return {"zero_based_card_indices": list(cards), **traces.get(tuple(cards), {})}

    ranked = sorted(((k, v) for k, v in traces.items() if "score" in v),
                    key=lambda kv: -kv[1]["score"])
    result = {"returned_keys": output, "preferred_first_three": output[:3],
              "turn_call_five_input_envelope": output[:5],
              "selection_target_calls": calls, "counts": counts,
              "distinct_scored_candidates_including_probes": len(ranked),
              "top_five": [compact(k) for k, _ in ranked[:5]],
              "probes": [compact(p) for p in c["probes"] if tuple(p) in traces]}
    if class_name == "Turn":
        result.update(
            effective_group=locals_after["group"],
            np_below_100_before_selection=locals_after["np"],
            selected_np_zero_based_indices=locals_after["hougu"],
            chosen_score=compact([int(ch) - 1 for ch in output[:3]]),
            post_np_forecast_enemy=state.enemy,
            post_np_forecast_target=state.target)
    return result
