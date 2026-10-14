"""Verify OCR and FGO connection without taps, farming, or resolution changes."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys

os.chdir(Path(__file__).resolve().parent.parent / 'FGO-py')
sys.path.insert(0, str(Path.cwd()))
os.environ.setdefault('FGO_CAP_METHOD', 'ADBCAP')
os.environ['NO_COLOR'] = '1'


def main():
    with contextlib.redirect_stdout(sys.stderr):
        from fgoConfig import Config
        from fgoConst import PACKAGE_TO_REGION
        from fgoAndroid import foreground_package
        from fgoOcr import Ocr
        from fgoSolver import cbc_solver
        import pulp
        import cv2
        import numpy as np

        serial = sys.argv[1] if len(sys.argv) > 1 else Config().device
        if not serial:
            raise SystemExit('Configure a device serial first')
        activities = subprocess.check_output(
            ['adb', '-s', serial, 'shell', 'dumpsys', 'activity', 'activities'], text=True, timeout=15)
        package = foreground_package(activities)
        sample = np.full((80, 320, 3), 255, np.uint8)
        cv2.putText(sample, '12345', (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
        result = Ocr('ja')(sample)
        problem = pulp.LpProblem('macos_check', pulp.LpMinimize)
        value = pulp.LpVariable('value', lowBound=2, cat=pulp.LpInteger)
        problem += value
        problem.solve(cbc_solver())
        if pulp.value(value) != 2 or pulp.LpStatus[problem.status] != 'Optimal':
            raise RuntimeError('CBC solver self-test failed')
        report = dict(serial=serial, foreground_package=package, ocr_text=result,
                      game_foreground=package in PACKAGE_TO_REGION, solver='Optimal')
        if package in PACKAGE_TO_REGION:
            from fgoDevice import Device
            from fgoDetect import XDetect
            device = Device(serial)
            if not device.name or device.package != package:
                raise RuntimeError('Foreground game changed during connection')
            image = device.screenshot()
            report.update(region=XDetect.region, screenshot_shape=list(image.shape),
                          input_service_ready=device.available, capture_method=os.environ['FGO_CAP_METHOD'],
                          render_bounds=device.render)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.strip() == '12345' else 1


if __name__ == '__main__':
    raise SystemExit(main())
