#!/usr/bin/env python3
"""RS-Uninstaller 启动脚本。

用法：
    python run.py           # 启动桌面窗口
    python -m rsu           # 等价方式
"""

import multiprocessing
import os
import sys

# PyInstaller 打包后必须尽早调用，避免子进程重复启动界面
multiprocessing.freeze_support()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rsu.app import main  # noqa: E402

if __name__ == "__main__":
    main()
