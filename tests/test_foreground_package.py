import os
from pathlib import Path
import sys
import unittest

os.chdir(Path(__file__).resolve().parents[1] / 'FGO-py')
sys.path.insert(0, str(Path.cwd()))
from fgoAndroid import foreground_package


class ForegroundPackageTest(unittest.TestCase):
    def test_resumed_game_wins_over_background_calculator(self):
        dump = '''mResumedActivity: ActivityRecord{123 u0 com.miui.calculator/.Calculator t1}
topResumedActivity=ActivityRecord{456 u0 com.aniplex.fategrandorder/jp.delightworks.Fgo.player.AndroidPlugin t130}
ACTIVITY com.miui.calculator/.Calculator abc pid=999'''
        self.assertEqual(foreground_package(dump), 'com.aniplex.fategrandorder')

    def test_legacy_resumed_marker(self):
        self.assertEqual(foreground_package('mResumedActivity: ActivityRecord{x u0 com.bilibili.fatego/.Main t1}'), 'com.bilibili.fatego')

    def test_missing_resumed_marker_allows_legacy_fallback(self):
        self.assertIsNone(foreground_package('ACTIVITY com.miui.calculator/.Calculator'))


if __name__ == '__main__':
    unittest.main()
