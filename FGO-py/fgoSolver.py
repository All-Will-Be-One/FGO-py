"""Prefer native CBC on PATH; PuLP's bundled macOS binary is Intel-only."""
import shutil

import pulp


def cbc_solver(msg=False):
    path = shutil.which('cbc')
    if path:
        return pulp.COIN_CMD(path=path, msg=msg)
    return pulp.PULP_CBC_CMD(msg=msg)
