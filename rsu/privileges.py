"""管理员权限检测与自我提权。"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def relaunch_as_admin() -> bool:
    """以管理员身份重新启动自身；成功发起返回 True。"""
    try:
        shell32 = ctypes.windll.shell32
        shell32.ShellExecuteW.restype = ctypes.c_void_p

        if getattr(sys, "frozen", False):
            exe = sys.executable
            args = sys.argv[1:]
        else:
            exe = sys.executable
            args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]

        params = subprocess.list2cmdline(args)
        result = shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return result is not None and int(result) > 32
    except Exception:  # noqa: BLE001
        return False
