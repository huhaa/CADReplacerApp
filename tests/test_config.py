"""配置持久化测试。"""
import json
import tempfile
import os
from src.config import ConfigManager
from src.model import AppConfig, ScopeConfig


class TestConfigManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load(self):
        mgr = ConfigManager(self.config_path)
        config = AppConfig(
            rules=[{"find_text": "a", "replace_text": "b",
                    "use_regex": False, "case_sensitive": True}],
            scope={"text": True, "mtext": True, "attribute": True,
                   "paper_space": False, "nested_blocks": True},
            last_files=["C:/test.dwg"],
        )
        mgr.save(config)
        assert os.path.exists(self.config_path)

        loaded = mgr.load()
        assert loaded.rules == config.rules
        assert loaded.scope == config.scope
        assert loaded.last_files == ["C:/test.dwg"]

    def test_load_missing_file_returns_default(self):
        mgr = ConfigManager(self.config_path)
        config = mgr.load()
        assert config.rules == []
        assert config.last_files == []

    def test_load_corrupted_file_returns_default(self):
        with open(self.config_path, "w") as f:
            f.write("not valid json{{{")
        mgr = ConfigManager(self.config_path)
        config = mgr.load()
        assert config.rules == []

    def test_roundtrip_preserves_all_fields(self):
        mgr = ConfigManager(self.config_path)
        original = AppConfig(
            rules=[
                {"find_text": "2024", "replace_text": "2025",
                 "use_regex": True, "case_sensitive": False, "rule_id": "abc123"}
            ],
            scope={"text": False, "mtext": True, "attribute": False,
                   "paper_space": True, "nested_blocks": False},
            last_files=["a.dwg", "b.dwg"],
            window_geometry={"x": 100, "y": 200, "w": 800, "h": 600},
        )
        mgr.save(original)
        loaded = mgr.load()
        assert loaded == original
