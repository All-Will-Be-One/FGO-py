"""Run the actual pinned Main class with fake detectors/inputs, never import the engine."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

class FlowBranchesTest(unittest.TestCase):

    def run_main(self, scenes, target, input_error=False, hook=None, allow_quest=True):
        source = Path(__file__).resolve().parents[1] / 'FGO-py/fgoKernel.py'
        tree = ast.parse(source.read_text())
        main = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Main'))
        events, inputs = ([], [])
        self.last_inputs = inputs

        class Detection:

            def __init__(self, scene):
                self.scene = scene

            def __getattr__(self, name):
                mapping = {'isMainInterface': 'quest', 'isBattleContinue': 'repeat', 'isApEmpty': 'ap_empty', 'isTurnBegin': 'turn', 'isBattleFormation': 'formation'}
                return lambda: mapping.get(name) == self.scene

        class Detector:

            def __call__(self, *args):
                if not scenes:
                    raise AssertionError('unexpected detection: navigation changed or failed to stop')
                self.cache = Detection(scenes.pop(0))
                return self.cache

        def press(key):
            inputs.append(key)
            if input_error and key == 'K':
                raise OSError('delivery unknown')

        def info(message, **kwargs):
            if 'extra' in kwargs:
                events.append(kwargs['extra']['flow_event'])

        class Battle:
            result = dict(turn=1, time=1, material={})

            def __call__(self):
                return True
        namespace = dict(ScriptStop=RuntimeError, serialize=lambda lock: lambda fn: fn, mutex=object(), Battle=Battle, Detect=Detector(), time=SimpleNamespace(time=lambda: 0), logger=Mock(info=info), fgoDevice=SimpleNamespace(device=SimpleNamespace(press=press, perform=lambda keys, waits: inputs.append(keys))), schedule=Mock(), logit=lambda *args: lambda fn: fn, logging=SimpleNamespace(INFO=20))
        exec(compile(ast.Module(body=[main], type_ignores=[]), str(source), 'exec'), namespace)
        work = namespace['Main'](appleTotal=0)
        work.chooseFriend = lambda: None
        if input_error:
            with self.assertRaises(OSError):
                work(battleTotal=target, storyHook=hook, allowQuest=allow_quest)
        else:
            work(battleTotal=target, storyHook=hook, allowQuest=allow_quest)
        return (events, inputs)

    def test_continue_repeat_then_ap_empty_preserves_inputs(self):
        for target, reason in ((None, 'until_ap_empty'), (2, 'target_not_reached')):
            with self.subTest(target=target):
                events, inputs = self.run_main(['repeat', 'ap_empty'], target)
                self.assertEqual(inputs, ['K', 'Z'])
                self.assertEqual([e['event'] for e in events], ['confirmation_button_matched', 'confirmation_action', 'confirmation_action', 'ap_empty_detected', 'farm_exit'])
                self.assertEqual(events[1]['reason'], reason)
                self.assertEqual(events[2]['stage'], 'input_returned')
                self.assertEqual(events[2]['game_effect'], 'unverified')
                self.assertEqual(events[-1]['reason'], 'ap_empty')

    def test_decline_when_finite_target_reached(self):
        events, inputs = self.run_main(['turn', 'repeat'], 1)
        self.assertEqual(inputs, [' ' * 10, 'F'])
        actions = [e for e in events if e['event'] == 'confirmation_action']
        self.assertEqual([e['stage'] for e in actions], ['input_dispatch', 'input_returned'])
        self.assertTrue(all((e['choice'] == 'decline' and e['reason'] == 'target_reached' for e in actions)))
        self.assertEqual(events[-1]['event'], 'farm_exit')
        self.assertEqual(events[-1]['battle_count'], 1)
        self.assertFalse(any((e.get('game_effect') == 'confirmed' for e in events)))

    def test_list_entry_repeat_branch_is_also_logged(self):
        events, inputs = self.run_main(['quest', 'repeat', 'ap_empty'], None)
        self.assertEqual(inputs, ['8', 'K', 'Z'])
        self.assertEqual(events[0]['event'], 'confirmation_button_matched')
        self.assertEqual(events[0]['branch'], 'quest_entry')
        self.assertEqual(events[0]['recognizer'], 'isBattleContinue')
        self.assertFalse(events[0]['semantic_verified'])
        self.assertEqual(events[-1]['reason'], 'ap_empty')

    def test_formation_is_reported_only_after_detection(self):
        events, inputs = self.run_main(['quest', 'other', 'other', 'formation', 'quest'], 1)
        self.assertEqual(inputs, ['8', ' M ', ' ' * 10])
        self.assertEqual(events[0]['event'], 'screen_observed')
        self.assertEqual(events[0]['scene'], 'formation')
        self.assertEqual(events[-1]['reason'], 'target_reached')

    def test_input_error_does_not_claim_return_or_screen_confirmation(self):
        events, inputs = self.run_main(['repeat'], None, input_error=True)
        self.assertEqual(inputs, ['K'])
        self.assertEqual(events[-1]['stage'], 'delivery_unknown')
        self.assertFalse(any((e['event'] == 'screen_observed' for e in events)))

    def test_integrated_every_battle_boundaries_and_no_extra_selection(self):
        calls = []

        def hook(phase, battle):
            calls.append((phase, battle))
            return 'turn' if phase == 'pre' else 'quest'
        events, inputs = self.run_main(['quest', 'other', 'quest', 'other'], 2, hook=hook)
        self.assertEqual(calls, [('pre', 1), ('post', 1), ('pre', 2), ('post', 2)])
        self.assertEqual(inputs, ['8', '8'])
        self.assertEqual(events[-1]['reason'], 'target_reached')

    def test_integrated_support_and_formation_reuse_existing_start(self):
        for landing in ('support', 'formation'):
            calls = []

            def hook(phase, battle):
                calls.append((phase, battle))
                return landing if phase == 'pre' else 'quest'
            _, inputs = self.run_main(['other', 'formation'], 1, hook=hook, allow_quest=False)
            self.assertEqual(inputs, [' M '])
            self.assertEqual(calls, [('pre', 1), ('post', 1)])

    def test_integrated_does_not_press_shared_confirmation_before_pre(self):

        def hook(phase, battle):
            raise RuntimeError('needs_agent')
        with self.assertRaisesRegex(RuntimeError, 'needs_agent'):
            self.run_main(['quest', 'repeat'], 1, hook=hook)
        self.assertEqual(self.last_inputs, ['8'])
        with self.assertRaisesRegex(RuntimeError, 'unsupported_story_battle_entry'):
            self.run_main(['quest'], 1, hook=hook, allow_quest=False)
        self.assertEqual(self.last_inputs, [])

    def test_post_failure_stops_before_next_battle(self):

        def hook(phase, battle):
            if phase == 'post':
                raise RuntimeError('needs_agent')
            return 'turn'
        with self.assertRaisesRegex(RuntimeError, 'needs_agent'):
            self.run_main(['turn'], 2, hook=hook)
        self.assertEqual(self.last_inputs, [])
