"""Execute only extracted pure methods/functions; never import native device/kernel."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
ROOT = Path(__file__).resolve().parents[1]

def load_executor(detector, press, clock, sleep, stop):
    tree = ast.parse((ROOT / 'FGO-py/fgoKernel.py').read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in {'CardSelectionHandoff', 'executeCardSelection'}]
    events = []

    class Cancel(Exception):
        pass
    env = dict(XDetect=detector, ScriptStop=Cancel, fgoDevice=SimpleNamespace(device=SimpleNamespace(press=press)), schedule=SimpleNamespace(checkStop=stop, sleep=sleep), time=SimpleNamespace(monotonic=clock), logger=Mock(info=lambda message, extra: events.append(extra['flow_event'])))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'card_ast', 'exec'), env)
    return (env, events, Cancel)

def selecting(partial=False, disabled=()):
    face = [str(i + 1) in disabled for i in range(5)]
    np = [str(i + 6) in disabled for i in range(3)]
    return dict(kind='selecting', selection_marker_visible=partial, action_disabled=dict(face=face, np=np), unavailable=dict(face=face, np=np))

class CardExecutionTest(unittest.TestCase):

    def run_case(self, frames, plan='813245', failure=None, cancel_after=None, slow_observation=False):
        if any((k in '678' for k in plan[:3])):
            frames = [frames[0]] + frames
        now = [0]
        inputs = []
        index = [0]
        last = [None]

        class Detector:
            region = 'JP'

            def __call__(self):
                i = index[0]
                index[0] += 1
                state = frames[min(i, len(frames) - 1)]

                def evidence(previous=None):
                    if slow_observation:
                        now[0] = 31
                    return state
                last[0] = state
                return SimpleNamespace(save=lambda *a, **k: True, getCardSelectionEvidence=evidence)

        def press(k):
            inputs.append(k)
            if failure and len(inputs) == failure:
                raise OSError('lost delivery')

        def sleep(t):
            now[0] += t
        env, events, Cancel = load_executor(Detector(), press, lambda: now[0], sleep, lambda: None)
        if cancel_after is not None:

            def stop():
                if len(inputs) >= cancel_after:
                    raise Cancel('cancelled')
            env['schedule'].checkStop = stop
        error = None
        try:
            env['executeCardSelection'](plan)
        except (env['CardSelectionHandoff'], Cancel) as e:
            error = e
        return (error, events, inputs, index[0])

    def test_normal_and_multiple_np_progress_without_fallback(self):
        for plan in ('813245', '67812345', '12345'):
            error, events, keys, count = self.run_case([selecting(), dict(kind='advanced', scene='turn')], plan)
            self.assertIsNone(error)
            self.assertEqual(keys, list(plan[:3]))
            self.assertEqual(events[-1]['event'], 'card_selection_confirmed')
            self.assertFalse(events[-1]['individual_cards_verified'])
            self.assertTrue(all((e['game_effect'] == 'unverified' for e in events if e['event'] == 'card_selection_dispatch')))

    def test_partial_lost_click_never_refills_or_replays(self):
        error, events, keys, count = self.run_case([selecting(), selecting(partial=True)])
        self.assertEqual(error.reason, 'card_selection_incomplete')
        self.assertEqual(keys, list('813'))
        self.assertEqual(count, 14)
        self.assertFalse(any((e['event'] == 'card_selection_confirmed' for e in events)))
        self.assertIn('screenshot', error.observation['observation'])

    def test_delivery_unknown_stops_chain(self):
        error, events, keys, count = self.run_case([selecting(), selecting(partial=True)], failure=2)
        self.assertEqual(error.reason, 'card_selection_delivery_unknown')
        self.assertEqual(keys, list('81'))
        self.assertEqual(count, 3)

    def test_disabled_or_preselected_plan_has_no_inputs(self):
        for state, reason in [(selecting(disabled=('1',)), 'card_selection_disabled_plan'), (selecting(disabled=('8',)), 'card_selection_disabled_plan'), (selecting(partial=True), 'card_selection_already_partial'), (dict(kind='unknown'), 'card_selection_not_ready')]:
            error, events, keys, _ = self.run_case([state])
            self.assertEqual(error.reason, reason)
            self.assertEqual(keys, [])

    def test_ambiguous_disabled_text_is_not_treated_as_available(self):
        state = selecting()
        state['action_disabled']['face'][0] = None
        error, events, keys, _ = self.run_case([state])
        self.assertEqual(error.reason, 'card_selection_disabled_uncertain')
        self.assertEqual(keys, [])

    def test_cancel_and_late_capture_never_add_inputs(self):
        error, events, keys, _ = self.run_case([selecting()], cancel_after=1)
        self.assertEqual(str(error), 'cancelled')
        self.assertEqual(keys, ['8'])
        error, events, keys, _ = self.run_case([selecting()], slow_observation=True)
        self.assertEqual(error.reason, 'card_selection_timeout')
        self.assertEqual(keys, [])

    def test_unknown_or_defeat_is_not_acceptance(self):
        for kind, reason in [('unknown', 'card_selection_unconfirmed'), ('defeated', 'card_selection_defeated_screen')]:
            error, events, keys, _ = self.run_case([selecting(), dict(kind=kind)])
            self.assertEqual(error.reason, reason)
            self.assertEqual(keys, list('813'))

    def test_both_native_turns_call_confirmation(self):
        tree = ast.parse((ROOT / 'FGO-py/fgoKernel.py').read_text())
        for name in ('Turn', 'ClassicTurn'):
            node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name))
            call = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == '__call__'))
            self.assertTrue(any((isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and (n.func.id == 'executeCardSelection') for n in ast.walk(call))))

def detector_methods():
    tree = ast.parse((ROOT / 'FGO-py/fgoDetect.py').read_text())
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'XDetectJP'))
    return [n for n in node.body if isinstance(n, ast.FunctionDef)]

class CardRecognitionTest(unittest.TestCase):

    def test_exact_ocr_evidence_and_selected_card_negative(self):
        import re
        env = dict(re=re)
        method = next((n for n in detector_methods() if n.name == '_jpActionDisabled'))
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'jp_ast', 'exec'), env)
        for text, score, want in [('行動不能', 0.99, True), ('行動不能', 0.85, None), ('2nd Attack', 0.99, False), ('无法行动', 0.99, False), ('行動不', 0.99, None), ('行動不能ではない', 0.99, None)]:
            obj = SimpleNamespace(_crop=lambda r: None, ocr=SimpleNamespace(detect_and_ocr=lambda *a, **k: [SimpleNamespace(text=text, score=score)]))
            self.assertEqual(env['_jpActionDisabled'](obj, (0, 0, 1, 1)), want)
