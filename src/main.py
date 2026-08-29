"""CADReplacerApp V2 应用入口。"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication

from .model import ReplacerModel
from .view import MainView
from .presenter import ReplacerPresenter
from .version import __version__
from .update_checker import check_update


def app_dir():
    """返回可写目录：冻结后为 EXE 所在目录，否则为项目根。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_logging():
    """配置日志：按模块 + 轮转文件。"""
    log_dir = app_dir()
    log_path = os.path.join(log_dir, "error.log")

    handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s\n"
        "  %(pathname)s:%(lineno)d %(funcName)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # 自己的模块使用 DEBUG 级别
    for name in ["src.model", "src.presenter", "src.cad_worker", "src.view",
                 "src.config"]:
        logging.getLogger(name).setLevel(logging.DEBUG)


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    # 确保工作目录为可写目录（冻结后为 EXE 目录，否则项目根）
    project_root = app_dir()
    os.chdir(project_root)

    app = QApplication(sys.argv)

    model = ReplacerModel()
    view = MainView()
    view.resize(900, 650)

    config_path = os.path.join(project_root, "config.json")
    presenter = ReplacerPresenter(view, model, config_path)

    view.show()

    logger.info("CADReplacerApp V%s 启动", __version__)

    # 启动后异步检查更新
    has_update, latest_version, download_url = check_update()
    if has_update:
        view.show_update_dialog(latest_version, download_url)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
