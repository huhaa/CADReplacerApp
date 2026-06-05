"""主持层 — 业务逻辑编排，不依赖 Qt 控件。"""
import logging
import os

from .model import (
    ReplacerModel, ReplaceRule, ReplaceRecord,
    FileStatus, ScopeConfig, AppConfig,
)
from .cad_worker import CADWorker
from .config import ConfigManager

logger = logging.getLogger(__name__)


class ReplacerPresenter:
    """协调 Model、View、Worker 的主持人。

    所有方法在主线程调用。Worker 在独立线程运行。
    """

    def __init__(self, view, model: ReplacerModel,
                 config_path: str = "config.json"):
        """初始化 Presenter。

        Args:
            view: IMainView 实现（鸭子类型，不强制类型检查以避免导入问题）
            model: ReplacerModel 实例
            config_path: 配置文件路径
        """
        self._view = view
        self._model = model
        self._worker = None             # CADWorker
        self._config = ConfigManager(config_path)
        self._is_processing = False

        # 连接 View 信号
        view.signals.rule_add_requested.connect(self._on_add_rule)
        view.signals.rule_delete_requested.connect(self._on_delete_rule)
        view.signals.file_add_requested.connect(self._on_add_files)
        view.signals.file_delete_requested.connect(self._on_delete_files)
        view.signals.process_start_requested.connect(self.start_process)
        view.signals.process_cancel_requested.connect(self.cancel_process)
        view.signals.undo_requested.connect(self.undo_last)
        view.signals.preview_requested.connect(self.preview)

        # 加载保存的配置
        self._load_config()

    # ─── 规则操作 ──────────────────────────────────────────────

    def _on_add_rule(self):
        find = self._view.get_find_text().strip()
        replace = self._view.get_replace_text().strip()
        if not find:
            self._view.show_warning("警告", "请输入查找内容！")
            return
        rule = ReplaceRule(
            find_text=find,
            replace_text=replace,
            use_regex=self._view.get_regex_enabled(),
            case_sensitive=self._view.get_case_sensitive(),
        )
        if self._model.add_rule(rule):
            self._view.add_rule_item(rule)
            self._view.clear_rule_inputs()
        else:
            self._view.show_warning("警告", "相同规则已存在！")

    def _on_delete_rule(self):
        indices = self._view.remove_selected_rules()
        for i in indices:
            self._model.remove_rule(i)

    # ─── 文件操作 ──────────────────────────────────────────────

    def _on_add_files(self):
        paths = self._view.get_selected_files()
        added = []
        for path in paths:
            if self._model.add_file(path):
                added.append(path)
        if added:
            self._view.add_file_items(added)

    def _on_delete_files(self):
        indices = self._view.remove_selected_files()
        for i in indices:
            self._model.remove_file(i)

    # ─── 处理流程 ──────────────────────────────────────────────

    def start_process(self):
        """启动批量替换。"""
        if self._is_processing:
            return

        if not self._model.rules:
            self._view.show_warning("警告", "请先添加替换规则！")
            return
        if not self._model.files:
            self._view.show_warning("警告", "请选择要处理的DWG文件！")
            return

        self._is_processing = True
        self._view.set_processing_mode(True)
        self._view.update_progress(0, "正在连接 AutoCAD...")

        self._model.clear_all_history()

        scope = self._view.get_scope_config()

        self._worker = CADWorker()
        self._worker.setup(
            files=list(self._model.files),
            rules=list(self._model.rules),
            scope=scope,
        )

        # 连接 Worker 信号
        self._worker.connection_status.connect(self._on_connection_status)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.file_error.connect(self._on_file_error)
        self._worker.progress.connect(self._view.update_progress)
        self._worker.all_done.connect(self._on_all_done)

        self._worker.start()

    def cancel_process(self):
        """取消当前处理。"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._view.update_progress(0, "正在取消...")

    def _on_connection_status(self, ok: bool, message: str):
        if not ok:
            self._view.show_error("连接失败", message)
            self._reset_processing_state()

    def _on_file_started(self, path: str, index: int, total: int):
        self._model.set_file_result(path, FileStatus.PROCESSING)
        self._view.mark_file_status(index, FileStatus.PROCESSING)

    def _on_file_done(self, path: str, replaced_count: int):
        try:
            index = self._model.files.index(path)
        except ValueError:
            index = -1
        if replaced_count > 0:
            self._model.set_file_result(path, FileStatus.DONE, replaced_count)
            self._view.mark_file_status(index, FileStatus.DONE,
                                        f"替换 {replaced_count} 处")
        else:
            self._model.set_file_result(path, FileStatus.NO_MATCH, 0)
            self._view.mark_file_status(index, FileStatus.NO_MATCH,
                                        "未找到匹配文字")

    def _on_file_error(self, path: str, error_message: str):
        logger.error(f"文件处理失败: {path}: {error_message}")
        try:
            index = self._model.files.index(path)
        except ValueError:
            index = -1
        self._model.set_file_result(path, FileStatus.FAILED, 0, error_message)
        self._view.mark_file_status(index, FileStatus.FAILED, error_message)

        # 连续失败检查
        results = [self._model.get_file_result(f) for f in self._model.files]
        recent = [r for r in results if r and r.status == FileStatus.FAILED]
        if len(recent) >= 3:
            cont = self._view.ask_confirmation(
                "连续失败",
                f"连续 {len(recent)} 个文件处理失败，是否继续？")
            if not cont:
                self.cancel_process()

    def _on_all_done(self, _summary):
        """Worker 完成回调。"""
        self._reset_processing_state()

        if _summary and _summary.get("cancelled"):
            self._view.update_progress(0, "已取消")
            return

        summary = self._model.get_summary()
        msg = (f"处理完成！\n"
               f"替换成功: {summary['done']} 个文件\n"
               f"未找到匹配: {summary['no_match']} 个文件\n"
               f"失败: {summary['failed']} 个文件\n"
               f"共替换: {summary['total_replaced']} 处")
        self._view.show_info("处理完成", msg)

        # 保存配置
        self._save_config()

    def _reset_processing_state(self):
        self._is_processing = False
        self._view.set_processing_mode(False)
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    # ─── 预览 ──────────────────────────────────────────────────

    def preview(self):
        """统计预览信息。"""
        if not self._model.rules:
            self._view.show_warning("警告", "请先添加替换规则！")
            return
        if not self._model.files:
            self._view.show_warning("警告", "请选择要处理的DWG文件！")
            return

        total_files = len(self._model.files)
        total_rules = len(self._model.rules)
        msg = (f"预览统计\n\n"
               f"待处理文件: {total_files} 个\n"
               f"替换规则: {total_rules} 条\n\n"
               f"规则列表:\n")
        for i, rule in enumerate(self._model.rules, 1):
            flags = []
            if rule.use_regex:
                flags.append("正则")
            if not rule.case_sensitive:
                flags.append("忽略大小写")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            msg += (f"  {i}. \"{rule.find_text}\" → "
                    f"\"{rule.replace_text}\"{flag_str}\n")

        msg += "\n是否开始处理？"
        self._view.show_info("替换预览", msg)

    # ─── 撤销 ──────────────────────────────────────────────────

    def undo_last(self):
        """撤销上一次替换操作。"""
        if self._is_processing:
            self._view.show_warning("警告", "正在处理中，请等待完成！")
            return

        files_with_history = self._model.get_all_history_files()
        if not files_with_history:
            self._view.show_info("提示", "没有可撤销的操作")
            return

        confirmed = self._view.ask_confirmation(
            "撤销确认",
            f"将撤销以下文件的替换:\n" +
            "\n".join(f"  • {os.path.basename(f)}"
                      for f in files_with_history) +
            "\n\n确认撤销？")
        if not confirmed:
            return

        self._is_processing = True
        self._view.set_processing_mode(True)
        self._view.update_progress(0, "正在撤销...")

        self._worker = CADWorker()
        # 构建反向规则
        reverse_rules = []
        seen = set()
        for file_path in files_with_history:
            for record in self._model.get_history(file_path):
                key = (record.new_text, record.old_text)
                if key not in seen:
                    seen.add(key)
                    reverse_rules.append(
                        ReplaceRule(record.new_text, record.old_text))

        self._worker.setup(
            files=files_with_history,
            rules=reverse_rules,
            scope=ScopeConfig(),
        )
        self._worker.all_done.connect(self._on_undo_done)
        self._worker.file_error.connect(
            lambda p, e: logger.error(f"撤销失败: {p}: {e}"))
        self._worker.start()

    def _on_undo_done(self, _summary):
        self._model.clear_all_history()
        self._reset_processing_state()
        self._view.show_info("撤销完成", "已撤销所有替换，文件已恢复。")

    # ─── 配置持久化 ────────────────────────────────────────────

    def _save_config(self):
        config = AppConfig(
            rules=[r.to_dict() for r in self._model.rules],
            scope=self._view.get_scope_config().to_dict(),
            last_files=list(self._model.files),
        )
        self._config.save(config)

    def _load_config(self):
        config = self._config.load()
        # 恢复规则
        for rule_dict in config.rules:
            rule = ReplaceRule.from_dict(rule_dict)
            self._model.add_rule(rule)
            self._view.add_rule_item(rule)
