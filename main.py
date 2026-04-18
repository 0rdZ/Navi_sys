"""
main.py
项目统一入口文件。

作用：
1. 启动 PyQt 应用；
2. 创建并显示主窗口；
3. 统一作为项目运行入口。
"""

from __future__ import annotations

import sys
from PyQt5.QtWidgets import QApplication

from main_window import MainWindow


def main() -> int:
    """程序主入口。"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
