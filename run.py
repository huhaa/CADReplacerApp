"""CADReplacerApp V2 启动脚本 — 可直接运行 python run.py"""
import sys
import os

# 确保项目根在 sys.path 中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.main import main

if __name__ == "__main__":
    main()
