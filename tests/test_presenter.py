"""Presenter 层单元测试 — 使用 mock View 和 mock Model。"""
import pytest
from unittest.mock import Mock, call, MagicMock, patch

from src.model import (
    ReplacerModel, ReplaceRule, ReplaceRecord, FileStatus, ScopeConfig
)
from src.presenter import ReplacerPresenter


@pytest.fixture
def mock_view():
    """创建一个模拟 IMainView 的 mock 对象。"""
    view = MagicMock()
    view.get_find_text.return_value = ""
    view.get_replace_text.return_value = ""
    view.get_regex_enabled.return_value = False
    view.get_case_sensitive.return_value = True
    view.get_scope_config.return_value = ScopeConfig()
    view.remove_selected_rules.return_value = []
    view.remove_selected_files.return_value = []
    view.get_selected_files.return_value = []
    return view


@pytest.fixture
def model():
    return ReplacerModel()


@pytest.fixture
def presenter(mock_view, model, tmp_path):
    config_path = str(tmp_path / "test_config.json")
    return ReplacerPresenter(mock_view, model, config_path)


class TestAddRule:
    def test_add_valid_rule(self, presenter, mock_view, model):
        mock_view.get_find_text.return_value = "abc"
        mock_view.get_replace_text.return_value = "123"
        mock_view.get_regex_enabled.return_value = True
        mock_view.get_case_sensitive.return_value = False

        presenter._on_add_rule()

        assert len(model.rules) == 1
        assert model.rules[0].find_text == "abc"
        assert model.rules[0].use_regex is True
        assert model.rules[0].case_sensitive is False
        mock_view.add_rule_item.assert_called_once()
        mock_view.clear_rule_inputs.assert_called_once()

    def test_add_empty_find_shows_warning(self, presenter, mock_view):
        mock_view.get_find_text.return_value = ""
        presenter._on_add_rule()
        mock_view.show_warning.assert_called_once()
        mock_view.add_rule_item.assert_not_called()

    def test_add_duplicate_rule_warns(self, presenter, mock_view, model):
        mock_view.get_find_text.return_value = "abc"
        mock_view.get_replace_text.return_value = "123"
        presenter._on_add_rule()
        presenter._on_add_rule()  # 第二次
        assert len(model.rules) == 1
        mock_view.show_warning.assert_called_with("警告", "相同规则已存在！")


class TestDeleteRule:
    def test_delete_selected_rules(self, presenter, mock_view, model):
        model.add_rule(ReplaceRule("a", "1"))
        model.add_rule(ReplaceRule("b", "2"))
        mock_view.remove_selected_rules.return_value = [1, 0]

        presenter._on_delete_rule()

        assert len(model.rules) == 0


class TestStartProcess:
    def test_no_rules_shows_warning(self, presenter, mock_view):
        presenter.start_process()
        mock_view.show_warning.assert_called_with("警告", "请先添加替换规则！")

    def test_no_files_shows_warning(self, presenter, mock_view, model):
        model.add_rule(ReplaceRule("a", "b"))
        presenter.start_process()
        mock_view.show_warning.assert_called_with("警告", "请选择要处理的DWG文件！")

    @patch('src.presenter.CADWorker')
    def test_valid_start_creates_worker(self, mock_cad_worker, presenter, mock_view, model):
        mock_worker = MagicMock()
        mock_cad_worker.return_value = mock_worker

        model.add_rule(ReplaceRule("a", "b"))
        model.add_file("C:/test.dwg")

        presenter.start_process()

        assert presenter._worker is not None
        assert presenter._worker is mock_worker
        mock_view.set_processing_mode.assert_called_with(True)


class TestPreview:
    def test_preview_no_rules(self, presenter, mock_view):
        presenter.preview()
        mock_view.show_warning.assert_called_with("警告", "请先添加替换规则！")

    def test_preview_no_files(self, presenter, mock_view, model):
        model.add_rule(ReplaceRule("find", "replace"))
        presenter.preview()
        mock_view.show_warning.assert_called_with("警告", "请选择要处理的DWG文件！")

    def test_preview_with_data(self, presenter, mock_view, model):
        model.add_rule(ReplaceRule("find", "replace"))
        model.add_file("test.dwg")
        presenter.preview()
        mock_view.show_info.assert_called_once()
        args = mock_view.show_info.call_args[0]
        # 预览消息包含文件数量和规则信息，但不包含具体文件名
        assert "1 个" in args[1]
        assert "find" in args[1]


class TestUndo:
    def test_undo_no_history(self, presenter, mock_view):
        presenter.undo_last()
        mock_view.show_info.assert_called_with("提示", "没有可撤销的操作")

    def test_undo_while_processing(self, presenter, mock_view):
        presenter._is_processing = True
        presenter.undo_last()
        mock_view.show_warning.assert_called_with("警告", "正在处理中，请等待完成！")

    @patch('src.presenter.CADWorker')
    def test_undo_with_history_user_declines(self, mock_cad_worker, presenter, mock_view, model):
        model.record_replace("f1.dwg", ReplaceRecord("h1", "old", "new", "r1"))
        mock_view.ask_confirmation.return_value = False

        presenter.undo_last()

        # Worker should NOT be created
        assert presenter._worker is None

    @patch('src.presenter.CADWorker')
    def test_undo_with_history_user_confirms(self, mock_cad_worker, presenter, mock_view, model):
        mock_worker = MagicMock()
        mock_cad_worker.return_value = mock_worker

        model.record_replace("f1.dwg", ReplaceRecord("h1", "old", "new", "r1"))
        mock_view.ask_confirmation.return_value = True

        presenter.undo_last()

        assert presenter._worker is not None
        assert presenter._worker is mock_worker
        # 验证反向规则: new → old 被传递给 worker
        mock_worker.setup.assert_called_once()
        rules_passed = mock_worker.setup.call_args[1]['rules']
        assert len(rules_passed) == 1
        assert rules_passed[0].find_text == "new"
        assert rules_passed[0].replace_text == "old"
