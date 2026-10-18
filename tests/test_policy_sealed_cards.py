import unittest
from policy_fixture import run, case, METADATA, extract, SimpleNamespace

class PolicyRegressionTest(unittest.TestCase):

    def test_sealed_cards_cannot_collect_owner_switch_bonus(self):
        r = run(case('seal', colors=[0] * 5, owners=[0, 0, 0, 1, 2], sealed=[False, False, False, True, True], gauges=[100] * 3, enemies=[15000, 10000, 0, 0, 0, 0], probes=[[3, 4, 0]]), 'Turn')
        self.assertEqual(set(r['preferred_first_three']), set('123'))
        self.assertEqual(r['returned_keys'], r['preferred_first_three'])
        self.assertEqual(r['probes'][0]['score'], float('-inf'))

    def test_insufficient_cards_stop_and_np_prefix_supplies_slots(self):
        calls=[]
        with self.assertRaisesRegex(RuntimeError, 'Insufficient Unsealed Cards'):
            run(case('few', calls_sink=calls, stage_turn=1, sealed=[True, True, True, False, False]), 'Turn')
        self.assertEqual(calls, [])
        r = run(case('np', sealed=[True] * 5, ready=[True] * 3, stage=3), 'Turn')
        self.assertEqual(len(r['returned_keys']), 3)
        self.assertEqual(set(r['returned_keys']), set('678'))

if __name__=="__main__":unittest.main()
