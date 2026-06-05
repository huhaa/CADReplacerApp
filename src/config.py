"""配置持久化 — JSON 文件读写。"""
import json
import logging
import os
from dataclasses import asdict
from typing import Optional

from .model import AppConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    """管理 AppConfig 的 JSON 持久化。"""

    def __init__(self, config_path: str):
        self._config_path = config_path

    def save(self, config: AppConfig) -> bool:
        """保存配置到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            data = {
                "rules": config.rules,
                "scope": config.scope,
                "last_files": config.last_files,
                "window_geometry": config.window_geometry,
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def load(self) -> AppConfig:
        """从 JSON 文件加载配置，文件不存在或损坏时返回默认值。"""
        if not os.path.exists(self._config_path):
            return AppConfig()
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig(
                rules=data.get("rules", []),
                scope=data.get("scope", {}),
                last_files=data.get("last_files", []),
                window_geometry=data.get("window_geometry", {}),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"加载配置失败，使用默认值: {e}")
            return AppConfig()
