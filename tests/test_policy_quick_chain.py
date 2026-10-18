import unittest
from policy_fixture import run, case, METADATA, extract, SimpleNamespace

class PolicyRegressionTest(unittest.TestCase):

    def test_quick_chain_tuple(self):
        r = run(case('quick', colors=[1, 1, 1, 0, 2], probes=[[0, 1, 2]]), 'Turn')
        self.assertEqual(r['probes'][0]['colorChain'], 1)
        self.assertEqual(set(r['preferred_first_three']), set('123'))

if __name__=="__main__":unittest.main()
