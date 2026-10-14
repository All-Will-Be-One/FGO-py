from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'FGO-py'))
import pulp
from fgoSolver import cbc_solver


class SolverTest(unittest.TestCase):
    def test_native_cbc_is_preferred(self):
        with patch('fgoSolver.shutil.which', return_value='/opt/homebrew/bin/cbc'):
            solver = cbc_solver()
        self.assertIsInstance(solver, pulp.COIN_CMD)
        self.assertEqual(solver.path, '/opt/homebrew/bin/cbc')

    def test_existing_platforms_keep_bundled_fallback(self):
        with patch('fgoSolver.shutil.which', return_value=None):
            self.assertIsInstance(cbc_solver(), pulp.PULP_CBC_CMD)


if __name__ == '__main__':
    unittest.main()
