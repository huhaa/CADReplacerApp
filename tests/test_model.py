"""Model 层单元测试。"""
import pytest
from src.model import (
    ReplaceRule, ReplaceRecord, FileResult, FileStatus, ScopeConfig, AppConfig
)


class TestReplaceRule:
    def test_create_basic_rule(self):
        rule = ReplaceRule("find", "replace")
        assert rule.find_text == "find"
        assert rule.replace_text == "replace"
        assert rule.use_regex is False
        assert rule.case_sensitive is True

    def test_rule_auto_generates_id(self):
        rule = ReplaceRule("a", "b")
        assert len(rule.rule_id) == 8

    def test_rule_preserves_explicit_id(self):
        rule = ReplaceRule("a", "b", rule_id="custom01")
        assert rule.rule_id == "custom01"


class TestFileStatus:
    def test_enum_values(self):
        assert FileStatus.PENDING.value == "pending"
        assert FileStatus.DONE.value == "done"
        assert FileStatus.FAILED.value == "failed"


class TestFileResult:
    def test_default_status_is_pending(self):
        result = FileResult("test.dwg")
        assert result.status == FileStatus.PENDING
        assert result.replaced_count == 0
        assert result.records == []


class TestScopeConfig:
    def test_defaults(self):
        scope = ScopeConfig()
        assert scope.text is True
        assert scope.mtext is True
        assert scope.paper_space is False

    def test_custom(self):
        scope = ScopeConfig(text=False, paper_space=True)
        assert scope.text is False
        assert scope.paper_space is True


class TestAppConfig:
    def test_empty_config(self):
        config = AppConfig()
        assert config.rules == []
        assert config.last_files == []

    def test_with_data(self):
        config = AppConfig(
            rules=[{"find": "a", "replace": "b"}],
            last_files=["C:/test.dwg"]
        )
        assert len(config.rules) == 1
        assert config.last_files == ["C:/test.dwg"]


from src.model import ReplacerModel


class TestReplacerModel:
    def setup_method(self):
        self.model = ReplacerModel()

    # --- 规则管理 ---
    def test_add_rule(self):
        self.model.add_rule(ReplaceRule("find", "replace"))
        assert len(self.model.rules) == 1

    def test_add_duplicate_rule(self):
        self.model.add_rule(ReplaceRule("a", "b"))
        self.model.add_rule(ReplaceRule("a", "b"))
        assert len(self.model.rules) == 1  # 去重

    def test_remove_rule(self):
        self.model.add_rule(ReplaceRule("a", "b"))
        self.model.add_rule(ReplaceRule("c", "d"))
        self.model.remove_rule(0)
        assert len(self.model.rules) == 1
        assert self.model.rules[0].find_text == "c"

    def test_remove_rule_invalid_index(self):
        self.model.remove_rule(99)  # 不应抛异常

    def test_clear_rules(self):
        self.model.add_rule(ReplaceRule("a", "b"))
        self.model.clear_rules()
        assert len(self.model.rules) == 0

    # --- 文件管理 ---
    def test_add_file(self):
        self.model.add_file("C:/test.dwg")
        assert len(self.model.files) == 1
        assert self.model.files[0] == "C:/test.dwg"

    def test_add_duplicate_file(self):
        self.model.add_file("C:/test.dwg")
        self.model.add_file("C:/test.dwg")
        assert len(self.model.files) == 1

    def test_remove_file(self):
        self.model.add_file("a.dwg")
        self.model.add_file("b.dwg")
        self.model.remove_file(0)
        assert self.model.files == ["b.dwg"]

    def test_clear_files(self):
        self.model.add_file("a.dwg")
        self.model.clear_files()
        assert len(self.model.files) == 0

    # --- 替换历史 ---
    def test_record_replace(self):
        self.model.record_replace(
            "file.dwg", ReplaceRecord("h1", "old", "new", "r1"))
        history = self.model.get_history("file.dwg")
        assert len(history) == 1
        assert history[0].old_text == "old"

    def test_clear_history(self):
        self.model.record_replace("f1.dwg", ReplaceRecord("h1", "a", "b", "r1"))
        self.model.clear_history("f1.dwg")
        assert self.model.get_history("f1.dwg") == []

    def test_clear_all_history(self):
        self.model.record_replace("f1.dwg", ReplaceRecord("h1", "a", "b", "r1"))
        self.model.record_replace("f2.dwg", ReplaceRecord("h2", "c", "d", "r2"))
        self.model.clear_all_history()
        assert self.model.get_history("f1.dwg") == []
        assert self.model.get_history("f2.dwg") == []

    def test_get_all_history_files(self):
        self.model.record_replace("f1.dwg", ReplaceRecord("h1", "a", "b", "r1"))
        self.model.record_replace("f2.dwg", ReplaceRecord("h2", "c", "d", "r2"))
        files = self.model.get_all_history_files()
        assert set(files) == {"f1.dwg", "f2.dwg"}

    # --- 文件结果 ---
    def test_set_file_result(self):
        self.model.add_file("a.dwg")
        self.model.set_file_result("a.dwg", FileStatus.DONE, 5)
        result = self.model.get_file_result("a.dwg")
        assert result.status == FileStatus.DONE
        assert result.replaced_count == 5

    def test_get_file_results_summary(self):
        self.model.add_file("a.dwg")
        self.model.add_file("b.dwg")
        self.model.set_file_result("a.dwg", FileStatus.DONE, 3)
        self.model.set_file_result("b.dwg", FileStatus.FAILED, 0)
        summary = self.model.get_summary()
        assert summary["total"] == 2
        assert summary["done"] == 1
        assert summary["failed"] == 1
        assert summary["no_match"] == 0
        assert summary["total_replaced"] == 3

    def test_no_match_status(self):
        self.model.add_file("a.dwg")
        self.model.set_file_result("a.dwg", FileStatus.NO_MATCH, 0)
        result = self.model.get_file_result("a.dwg")
        assert result.status == FileStatus.NO_MATCH
        summary = self.model.get_summary()
        assert summary["no_match"] == 1
