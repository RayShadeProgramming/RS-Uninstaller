#!/usr/bin/env python3
"""RS-Uninstaller 启动脚本。

用法：
    python run.py           # 双击或命令行启动
    python -m rsu           # 等价的模块方式
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rsu.app import main  # noqa: E402

if __name__ == "__main__":
    main()
