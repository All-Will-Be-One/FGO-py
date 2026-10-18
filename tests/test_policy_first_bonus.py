import unittest
from policy_fixture import run, case, METADATA, extract, SimpleNamespace

class PolicyRegressionTest(unittest.TestCase):

    def test_first_bonus_tracks_selected_card_not_leftmost(self):
        scores = []
        for left in (0, 1, 2):
            r = run(case('first', colors=[left, 2, 2, 2, 0], sealed=[True, False, False, False, True], owners=[0, 0, 1, 2, 1], probes=[[1, 2, 3]]), 'Turn')
            self.assertEqual(r['probes'][0]['firstBonus'], 4)
            scores.append(r['probes'][0]['score'])
        self.assertEqual(len(set(scores)), 1)

    def test_first_bonus_includes_np_prefix(self):
        for ids in ([1, 2, 7], [7, 2, 1]):
            r = run(case('np', colors=[2] * 5, field_ids=ids, ready=[True, False, False], stage=3, probes=[[5, 1, 2]]), 'Turn')
            self.assertEqual(r['probes'][0]['firstBonus'], 1 << METADATA[ids[0]][4][1])

if __name__=="__main__":unittest.main()
