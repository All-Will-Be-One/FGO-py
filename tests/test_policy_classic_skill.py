import unittest
from policy_fixture import run, case, METADATA, extract, SimpleNamespace

class PolicyRegressionTest(unittest.TestCase):

    def test_failed_classic_skill_keeps_counter_shape_at_every_slot(self):
        for pos in range(3):
            for skill in range(3):
                countdown = [[[0] * 3 for _ in range(3)], [8, 9, 10]]
                calls = []
                detector = SimpleNamespace(isSkillNone=lambda: False, isSkillCastFailed=lambda: True)
                env = dict(Detect=lambda *args: detector, logger=SimpleNamespace(warning=lambda *a: None), fgoDevice=SimpleNamespace(device=SimpleNamespace(press=calls.append)))
                fn = extract('ClassicTurn', 'castServantSkill', env)
                fn(SimpleNamespace(countDown=countdown), pos, skill)
                expected = [[[0] * 3 for _ in range(3)], [8, 9, 10]]
                expected[0][pos][skill] = 1
                self.assertEqual(countdown, expected)
                self.assertEqual(calls[-1], 'J')

if __name__=="__main__":unittest.main()
