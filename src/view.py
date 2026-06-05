"""视图层 — GUI 实现 IMainView 接口。"""
import logging
import os
import webbrowser
from abc import ABCMeta, abstractmethod
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QCheckBox, QDialog,
    QPushButton, QListWidget, QProgressBar, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QListWidgetItem, QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt, QObject
from PySide6.QtGui import QAction, QColor, QIcon

from .model import ReplaceRule, ScopeConfig, FileStatus, FileResult

logger = logging.getLogger(__name__)


# ─── Qt + ABC 混合元类 ──────────────────────────────────────────

class QtABCMeta(type(QObject), ABCMeta):
    """混合元类，解决 QObject 和 ABC 多重继承的元类冲突。"""
    pass


# ─── IMainView 抽象接口 ───────────────────────────────────────────

class IMainView(metaclass=QtABCMeta):
    """主视图接口 — Presenter 仅依赖此接口，不依赖具体 Qt 控件。"""

    # 规则相关
    @abstractmethod
    def get_find_text(self) -> str: ...
    @abstractmethod
    def get_replace_text(self) -> str: ...
    @abstractmethod
    def get_regex_enabled(self) -> bool: ...
    @abstractmethod
    def get_case_sensitive(self) -> bool: ...
    @abstractmethod
    def add_rule_item(self, rule: ReplaceRule): ...
    @abstractmethod
    def remove_selected_rules(self) -> list: ...
    @abstractmethod
    def clear_rule_inputs(self): ...

    # 文件相关
    @abstractmethod
    def get_selected_files(self) -> list: ...
    @abstractmethod
    def add_file_items(self, paths: list): ...
    @abstractmethod
    def remove_selected_files(self) -> list: ...
    @abstractmethod
    def mark_file_status(self, index: int, status: FileStatus, message: str = ""): ...

    # 范围配置
    @abstractmethod
    def get_scope_config(self) -> ScopeConfig: ...

    # 进度
    @abstractmethod
    def update_progress(self, value: int, text: str = ""): ...
    @abstractmethod
    def set_processing_mode(self, processing: bool): ...

    # 消息
    @abstractmethod
    def show_error(self, title: str, message: str): ...
    @abstractmethod
    def show_warning(self, title: str, message: str): ...
    @abstractmethod
    def show_info(self, title: str, message: str): ...
    @abstractmethod
    def ask_confirmation(self, title: str, message: str) -> bool: ...


# ─── Qt 信号总线 ──────────────────────────────────────────────────

class ViewSignals(QObject):
    """视图发出的信号，Presenter 连接处理。"""
    rule_add_requested = Signal()
    rule_delete_requested = Signal()
    file_add_requested = Signal()
    file_delete_requested = Signal()
    process_start_requested = Signal()
    process_cancel_requested = Signal()
    undo_requested = Signal()
    preview_requested = Signal()


# ─── Qt View 实现 ─────────────────────────────────────────────────

class MainView(QMainWindow, IMainView):
    """主窗口，实现 IMainView 接口。"""

    def __init__(self):
        super().__init__()
        self.signals = ViewSignals()
        self._setup_window()
        self._setup_toolbars()
        self._setup_ui()
        self._setup_style()

    def _setup_window(self):
        self.setWindowTitle("AutoCAD批量文字替换工具 V2.0")
        # Resolve project root: src/view.py -> src/ -> project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(project_root, "pictures", "DHB.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _setup_toolbars(self):
        # 帮助
        help_tb = self.addToolBar("帮助")
        help_tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        help_action = QAction("使用说明", self)
        help_action.triggered.connect(self._show_help)
        help_tb.addAction(help_action)

        # 更新日志
        update_tb = self.addToolBar("更新日志")
        update_tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        update_action = QAction("📒更新日志", self)
        update_action.triggered.connect(self._show_update_log)
        update_tb.addAction(update_action)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(18)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ── 查找替换行 ──
        fr_layout = QHBoxLayout()
        fr_layout.addWidget(QLabel("查找:"))
        self.find_entry = QLineEdit()
        self.find_entry.setFixedWidth(180)
        fr_layout.addWidget(self.find_entry)

        fr_layout.addWidget(QLabel("替换:"))
        self.replace_entry = QLineEdit()
        self.replace_entry.setFixedWidth(180)
        fr_layout.addWidget(self.replace_entry)

        # 正则 + 大小写
        self.regex_check = QCheckBox("正则")
        self.regex_check.setToolTip("启用正则表达式匹配")
        fr_layout.addWidget(self.regex_check)

        self.case_check = QCheckBox("大小写")
        self.case_check.setChecked(True)
        self.case_check.setToolTip("区分大小写")
        fr_layout.addWidget(self.case_check)

        add_rule_btn = QPushButton("添加规则")
        add_rule_btn.clicked.connect(self.signals.rule_add_requested.emit)
        fr_layout.addWidget(add_rule_btn)
        main_layout.addLayout(fr_layout)

        # ── 替换范围 ──
        scope_group = QGroupBox("替换范围")
        scope_layout = QHBoxLayout()
        self.text_check = QCheckBox("普通文字")
        self.text_check.setChecked(True)
        self.mtext_check = QCheckBox("多行文字")
        self.mtext_check.setChecked(True)
        self.attrib_check = QCheckBox("块属性")
        self.attrib_check.setChecked(True)
        self.nested_check = QCheckBox("嵌套块")
        self.nested_check.setChecked(True)
        self.paperspace_check = QCheckBox("布局")
        self.paperspace_check.setChecked(True)
        scope_layout.addWidget(self.text_check)
        scope_layout.addWidget(self.mtext_check)
        scope_layout.addWidget(self.attrib_check)
        scope_layout.addWidget(self.nested_check)
        scope_layout.addWidget(self.paperspace_check)
        scope_group.setLayout(scope_layout)
        main_layout.addWidget(scope_group)

        # ── 规则与文件并排区域 ──
        lists_layout = QHBoxLayout()

        # 左侧：规则列表
        left_panel = QVBoxLayout()
        del_rule_btn = QPushButton("删除选中规则")
        del_rule_btn.clicked.connect(self.signals.rule_delete_requested.emit)
        self.rule_list = QListWidget()
        self.rule_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.rule_list.setAlternatingRowColors(True)

        rule_header = QHBoxLayout()
        rule_header.addWidget(del_rule_btn)
        rule_header.addWidget(QLabel("替换规则列表:"))
        rule_header.addStretch()
        left_panel.addLayout(rule_header)
        left_panel.addWidget(self.rule_list)

        # 右侧：文件列表
        right_panel = QVBoxLayout()
        add_file_btn = QPushButton("添加文件")
        add_file_btn.clicked.connect(self.signals.file_add_requested.emit)
        del_file_btn = QPushButton("删除选中文件")
        del_file_btn.clicked.connect(self.signals.file_delete_requested.emit)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setAlternatingRowColors(True)

        file_header = QHBoxLayout()
        file_header.addWidget(add_file_btn)
        file_header.addWidget(del_file_btn)
        file_header.addWidget(QLabel("待处理文件:"))
        file_header.addStretch()
        right_panel.addLayout(file_header)
        right_panel.addWidget(self.file_list)

        lists_layout.addLayout(left_panel)
        lists_layout.addLayout(right_panel)
        main_layout.addLayout(lists_layout)

        # ── 操作按钮行 ──
        btn_layout = QHBoxLayout()

        self.preview_btn = QPushButton("统计")
        self.preview_btn.clicked.connect(self.signals.preview_requested.emit)
        btn_layout.addWidget(self.preview_btn)

        self.execute_btn = QPushButton("🚀 开始替换")
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 14px 32px;
                font-size: 15px;
                font-weight: bold;
                min-height: 48px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
            QPushButton:pressed {
                background-color: #3730A3;
            }
        """)
        self.execute_btn.clicked.connect(self.signals.process_start_requested.emit)
        btn_layout.addWidget(self.execute_btn)

        self.undo_btn = QPushButton("↩ 撤销上次")
        self.undo_btn.clicked.connect(self.signals.undo_requested.emit)
        btn_layout.addWidget(self.undo_btn)

        main_layout.addLayout(btn_layout)

        # ── 进度条 ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.status_label = QLabel("就绪")
        prog_layout = QHBoxLayout()
        prog_layout.addWidget(QLabel("进度:"))
        prog_layout.addWidget(self.progress)
        prog_layout.addWidget(self.status_label)
        main_layout.addLayout(prog_layout)

    def _setup_style(self):
        self.setStyleSheet("""
            /* ── 全局 ── */
            QMainWindow {
                background-color: #F8F9FC;
            }
            * {
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }

            /* ── 卡片分组 ── */
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #1E293B;
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #4F46E5;
            }

            /* ── 按钮基础 ── */
            QPushButton {
                background-color: #FFFFFF;
                color: #4F46E5;
                border: 1px solid #C7D2FE;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 13px;
                min-height: 34px;
            }
            QPushButton:hover {
                background-color: #EEF2FF;
                border-color: #4F46E5;
            }
            QPushButton:pressed {
                background-color: #E0E7FF;
            }

            /* ── 输入框 ── */
            QLineEdit {
                background-color: #FFFFFF;
                border: 1.5px solid #E2E8F0;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border-color: #4F46E5;
            }

            /* ── 复选框 ── */
            QCheckBox {
                font-size: 13px;
                color: #334155;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1.5px solid #CBD5E1;
                border-radius: 3px;
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                background-color: #4F46E5;
                border-color: #4F46E5;
            }

            /* ── 列表 ── */
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                color: #1E293B;
                outline: none;
                alternate-background-color: #F8FAFC;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
                min-height: 22px;
            }
            QListWidget::item:hover {
                background-color: #EEF2FF;
            }
            QListWidget::item:selected {
                background-color: #4F46E5;
                color: #FFFFFF;
            }

            /* ── 进度条 ── */
            QProgressBar {
                background-color: #E2E8F0;
                border: none;
                border-radius: 14px;
                height: 28px;
                text-align: center;
                font-size: 12px;
                color: #1E293B;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4F46E5, stop:1 #7C3AED);
                border-radius: 14px;
            }

            /* ── 标签 ── */
            QLabel {
                color: #334155;
                font-size: 13px;
            }

            /* ── 工具栏 ── */
            QToolBar {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E2E8F0;
                padding: 4px 8px;
                spacing: 8px;
            }
            QToolBar QToolButton {
                color: #64748B;
                font-size: 12px;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QToolBar QToolButton:hover {
                background-color: #F1F5F9;
                color: #4F46E5;
            }

            /* ── 滚动条 ── */
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    # ─── IMainView 实现 ─────────────────────────────────────────

    def get_find_text(self) -> str:
        return self.find_entry.text()

    def get_replace_text(self) -> str:
        return self.replace_entry.text()

    def get_regex_enabled(self) -> bool:
        return self.regex_check.isChecked()

    def get_case_sensitive(self) -> bool:
        return self.case_check.isChecked()

    def add_rule_item(self, rule: ReplaceRule):
        label = f"{rule.find_text} → {rule.replace_text}"
        if rule.use_regex:
            label += "  [正则]"
        if not rule.case_sensitive:
            label += "  [忽略大小写]"
        self.rule_list.addItem(QListWidgetItem(label))

    def remove_selected_rules(self) -> list:
        indices = []
        for item in self.rule_list.selectedItems():
            row = self.rule_list.row(item)
            if row >= 0:
                indices.append(row)
                self.rule_list.takeItem(row)
        return sorted(indices, reverse=True)

    def clear_rule_inputs(self):
        self.find_entry.clear()
        self.replace_entry.clear()

    def get_selected_files(self) -> list:
        """打开文件选择对话框，返回选中路径。"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要替换的文件", "", "DWG文件 (*.dwg)")
        return list(files)

    def add_file_items(self, paths: list):
        for path in paths:
            if os.path.exists(path):
                self.file_list.addItem(QListWidgetItem(path))

    def remove_selected_files(self) -> list:
        indices = []
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            if row >= 0:
                indices.append(row)
                self.file_list.takeItem(row)
        return sorted(indices, reverse=True)

    def mark_file_status(self, index: int, status: FileStatus, message: str = ""):
        if 0 <= index < self.file_list.count():
            item = self.file_list.item(index)
            color_map = {
                FileStatus.PENDING:    QColor("#64748B"),
                FileStatus.PROCESSING: QColor("#F59E0B"),
                FileStatus.DONE:       QColor("#10B981"),
                FileStatus.NO_MATCH:   QColor("#EAB308"),
                FileStatus.FAILED:     QColor("#EF4444"),
                FileStatus.SKIPPED:    QColor("#94A3B8"),
            }
            item.setForeground(color_map.get(status, QColor("#1E293B")))
            if message:
                item.setToolTip(message)

    def get_scope_config(self) -> ScopeConfig:
        return ScopeConfig(
            text=self.text_check.isChecked(),
            mtext=self.mtext_check.isChecked(),
            attribute=self.attrib_check.isChecked(),
            paper_space=self.paperspace_check.isChecked(),
            nested_blocks=self.nested_check.isChecked(),
        )

    def update_progress(self, value: int, text: str = ""):
        self.progress.setValue(value)
        if text:
            self.status_label.setText(text)

    def set_processing_mode(self, processing: bool):
        if processing:
            self.execute_btn.setText("⏹ 取消")
            self.execute_btn.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 14px 32px;
                    font-size: 15px;
                    font-weight: bold;
                    min-height: 48px;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
                QPushButton:pressed {
                    background-color: #B91C1C;
                }
            """)
            self.execute_btn.clicked.disconnect()
            self.execute_btn.clicked.connect(self.signals.process_cancel_requested.emit)
            self.preview_btn.setEnabled(False)
            self.undo_btn.setEnabled(False)
        else:
            self.execute_btn.setText("🚀 开始替换")
            self.execute_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4F46E5;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 14px 32px;
                    font-size: 15px;
                    font-weight: bold;
                    min-height: 48px;
                }
                QPushButton:hover {
                    background-color: #4338CA;
                }
                QPushButton:pressed {
                    background-color: #3730A3;
                }
            """)
            self.execute_btn.clicked.disconnect()
            self.execute_btn.clicked.connect(self.signals.process_start_requested.emit)
            self.preview_btn.setEnabled(True)
            self.undo_btn.setEnabled(True)

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_warning(self, title: str, message: str):
        QMessageBox.warning(self, title, message)

    def show_info(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def ask_confirmation(self, title: str, message: str) -> bool:
        return QMessageBox.question(
            self, title, message,
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

    # ─── 私有辅助 ──────────────────────────────────────────────

    def _show_help(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        help_path = os.path.join(project_root, "help_file", "CADReplacerAPP_help.html")
        if os.path.exists(help_path):
            webbrowser.open(help_path)
        else:
            QMessageBox.information(self, "提示", "帮助文件未找到！")

    def _show_update_log(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(project_root, "help_file", "CADReplacerAPP更新日志.txt")
        if os.path.exists(log_path):
            os.startfile(log_path)
        else:
            QMessageBox.information(self, "提示", "更新日志未找到！")

