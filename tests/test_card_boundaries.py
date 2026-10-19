"""Five review regressions, using AST/fake frames only; never native imports."""
import ast
import contextlib
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from test_cards import ROOT, load_executor, selecting, detector_methods

def evidence_frame(text='Arts', score=0.99, brightness=0, disabled=False):
    env = dict(re=re, numpy=SimpleNamespace(mean=lambda x: x))
    nodes = [n for n in detector_methods() if n.name in ('getCardSelectionEvidence', 'isHouguReady')]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'detector_boundary_ast', 'exec'), env)

    class Frame:
        im = None
        tmpl = SimpleNamespace(HOUGUSEALED=None)

        def _crop(self, rect):
            return brightness

        def _compare(self, *a):
            return False

        def isNetworkError(self):
            return False

        def isBattleDefeated(self):
            return False

        def isBattleFinished(self):
            return False

        def isTurnBegin(self):
            return False

        def getActionDisabled(self):
            return dict(face=[False] * 5, np=[disabled] * 3)

        def isCardSealed(self):
            return [False] * 5
        def getCardLayoutEvidence(self):return dict(complete=True,slots=[])
        getCardSelectionEvidence = env['getCardSelectionEvidence']
        isHouguReady = env['isHouguReady']
    f = Frame()
    f.ocr = SimpleNamespace(detect_and_ocr=lambda *a, **k: [SimpleNamespace(text=t, score=0.99, box=[[100, y], [140, y], [140, y + 20], [100, y + 20]]) for t, y in [('Arts', 500), (text, 300)]], ocr_single_line=lambda *a: ('戻る', score))
    return f

class EvidenceBoundaryTest(unittest.TestCase):

    def test_exact_ordinal_markers_only(self):
        for text in ('Attack', '1st Attack', '2nd Attack', '3rd Attack', '1st\nAttack'):
            self.assertTrue(evidence_frame(text).getCardSelectionEvidence()['selection_marker_visible'], text)
        for text in ('4th Attack', 'Attack bonus', 'not Attack', '21st Attack', '1st Attack bonus'):
            self.assertFalse(evidence_frame(text).getCardSelectionEvidence()['selection_marker_visible'], text)

    def test_np_two_frame_or_uses_latest_disable_state(self):
        bright = evidence_frame(brightness=75)
        dark = evidence_frame(brightness=0)
        self.assertEqual(dark.getCardSelectionEvidence()['unavailable']['np'], [True] * 3)
        self.assertEqual(dark.getCardSelectionEvidence(previous=bright)['unavailable']['np'], [False] * 3)
        self.assertEqual(bright.getCardSelectionEvidence(previous=dark)['unavailable']['np'], [False] * 3)
        self.assertEqual(evidence_frame(brightness=0, disabled=True).getCardSelectionEvidence(previous=bright)['unavailable']['np'], [True] * 3)

class ExecutionBoundaryTest(unittest.TestCase):

    def run_boundary(self, phase, mode='timeout', plan='12345'):
        now = [0.0]
        cancelled = [False]
        trace = []
        captures = [0]
        presses = [0]

        def trigger(name):
            if name == phase:
                if mode == 'timeout':
                    now[0] = 31.0
                else:
                    cancelled[0] = True

        class Detector:
            region = 'JP'

            def __call__(self):
                captures[0] += 1
                trace.append(('capture', captures[0]))
                trigger('capture' + str(captures[0]))

                def save(*a, **k):
                    trace.append(('save', captures[0]))
                    trigger('save' + str(captures[0]))
                    return True

                def evidence(previous=None):
                    trace.append(('evidence', captures[0]))
                    return selecting()
                return SimpleNamespace(save=save, getCardSelectionEvidence=evidence)

        def press(key):
            presses[0] += 1
            trace.append(('press', key))
            trigger('press' + str(presses[0]))

        def sleep(seconds):
            trace.append(('sleep', seconds))
            now[0] += seconds
            trigger('sleep')
        env, events, Cancel = load_executor(Detector(), press, lambda: now[0], sleep, lambda: None)

        def stop():
            if cancelled[0]:
                raise Cancel('cancelled')
        env['schedule'].checkStop = stop
        with self.assertRaises((Cancel, env['CardSelectionHandoff'])) as caught:
            env['executeCardSelection'](plan)
        if mode == 'timeout':
            self.assertEqual(caught.exception.reason, 'card_selection_timeout')
        else:
            self.assertIsInstance(caught.exception, Cancel)
        return trace

    def test_capture_save_press_returns_check_before_next_blocking_step(self):
        for mode in ('timeout', 'cancel'):
            for phase, last in [('capture1', ('capture', 1)), ('save1', ('save', 1)), ('press3', ('press', '3'))]:
                trace = self.run_boundary(phase, mode)
                self.assertEqual(trace[-1], last, (mode, phase, trace))

    def test_executor_passes_previous_np_frame_and_blocks_existing_marker(self):
        for marked in (False, True):
            frames = [evidence_frame(text='1st Attack' if marked else 'Arts', brightness=75), evidence_frame(brightness=0)]
            for frame in frames:
                frame.save = lambda *a, **k: True
            frames.append(SimpleNamespace(save=lambda *a, **k: True, getCardSelectionEvidence=lambda **k: dict(kind='advanced', scene='turn')))
            captures = []
            keys = []
            now = [0.0]

            class Detector:
                region = 'JP'

                def __call__(self):
                    captures.append(True)
                    return frames[len(captures) - 1]
            env, events, Cancel = load_executor(Detector(), keys.append, lambda: now[0], lambda seconds: now.__setitem__(0, now[0] + seconds), lambda: None)
            if marked:
                with self.assertRaises(env['CardSelectionHandoff']) as caught:
                    env['executeCardSelection']('678')
                self.assertEqual(caught.exception.reason, 'card_selection_already_partial')
                self.assertEqual(keys, [])
                self.assertEqual(len(captures), 1)
            else:
                env['executeCardSelection']('678')
                self.assertEqual(keys, list('678'))
                self.assertEqual(len(captures), 3)

    def test_second_np_capture_and_preflight_wait_obey_budget(self):
        for mode in ('timeout', 'cancel'):
            trace = self.run_boundary('capture2', mode, plan='678')
            self.assertEqual(trace[-1], ('capture', 2))
            self.assertFalse(any((item[0] == 'press' for item in trace)))
            trace = self.run_boundary('sleep', mode, plan='678')
            self.assertEqual(trace[-1], ('sleep', 0.15))

class NativeRainbowBoundaryTest(unittest.TestCase):

    def run_battle(self, confirmation, stop_on_drop):
        kinds = ['turn'] + (['selecting'] if confirmation else []) + ['rainbow', 'rainbow', 'result', 'result', 'result']
        frames = iter(kinds)
        now = [0.0]
        keys = []
        special = []
        messages = []

        class Frame:

            def __init__(self, kind):
                self.kind = kind

            def isTurnBegin(self):
                return self.kind == 'turn'

            def isSpecialDropSuspended(self):
                return False

            def isSpecialDropRainbowBox(self):
                return self.kind == 'rainbow'

            def isBattleFinished(self):
                return self.kind == 'result'

            def isBattleDefeated(self):
                return False

            def getMaterial(self):
                return {}

            def save(self, *a, **k):
                return True

            def getCardSelectionEvidence(self, previous=None):
                if self.kind == 'selecting':
                    return selecting()
                if self.kind == 'result':
                    return dict(kind='advanced', scene='result')
                return dict(kind='unknown')

        class Factory:
            region = 'JP'
            cache = None

            def __call__(self, *a):
                self.cache = Frame(next(frames))
                return self.cache
        factory = Factory()

        def sleep(s):
            now[0] += s
        env, events, Cancel = load_executor(factory, keys.append, lambda: now[0], sleep, lambda: None)

        def check_drop():
            special.append(True)
            if stop_on_drop:
                raise Cancel('Special Drop')
        env.update(Detect=factory, Turn=object)
        env['time'].time = lambda: now[0]
        env['schedule'].checkSpecialDrop = check_drop
        env['schedule'].checkKizunaReisou = lambda: None
        env['schedule'].checkDefeated = lambda: None
        env['fgoDevice'].device.perform = lambda *a: None
        env['logger'] = SimpleNamespace(info=lambda msg, extra=None: events.append(extra['flow_event']) if extra else messages.append(msg), warning=messages.append)
        tree = ast.parse((ROOT / 'FGO-py/fgoKernel.py').read_text())
        node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Battle'))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'battle_ast', 'exec'), env)

        class Turn:

            def __call__(self, turn):
                if confirmation:
                    env['executeCardSelection']('123', self.cardSelectionObserver)
        battle = env['Battle'](Turn)
        try:
            outcome = battle()
        except Cancel as error:
            outcome = str(error)
        return (outcome, battle.rainbowBox, len(special), messages.count('Battle Finished'), keys)

    def test_confirmation_preserves_native_drop_once_without_extra_inputs(self):
        for stop in (True, False):
            baseline = self.run_battle(False, stop)
            confirmed = self.run_battle(True, stop)
            self.assertEqual(confirmed[:4], baseline[:4])
            self.assertEqual(confirmed[:4], ('Special Drop' if stop else True, True, 1, 1))
            self.assertEqual(confirmed[4], list('123'))
