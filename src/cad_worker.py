"""CAD 工作线程 — 在独立 STA 线程中通过 COM 操作 AutoCAD。"""
import logging
import os
import re
import time

import pythoncom
import win32com.client
from win32com.client import dynamic as _dynamic
from PySide6.QtCore import QThread, Signal


def _dyn(obj):
    """强制动态分发，绕过 gen_py 早期绑定接口缺成员(GetAttributes/TextString)的问题。"""
    try:
        return _dynamic.Dispatch(obj)
    except Exception:
        return obj

from .model import ReplaceRule, ReplaceRecord, ScopeConfig, FileStatus

logger = logging.getLogger(__name__)


class CADWorker(QThread):
    """在独立 STA 线程中批量处理 DWG 文件的文字替换。"""

    # 信号（跨线程安全）
    connection_status = Signal(bool, str)        # OK/FAIL, message
    progress = Signal(int, str)                   # percent, status_text
    file_started = Signal(str, int, int)          # path, index, total
    file_done = Signal(str, int)                  # path, replaced_count
    file_error = Signal(str, str)                 # path, error_message
    all_done = Signal(dict)                       # summary dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: list = []
        self._rules: list = []          # list[ReplaceRule]
        self._scope = None              # ScopeConfig
        self._cancel_flag = False
        self._acad = None
        self._records: dict = {}        # file_path -> list[ReplaceRecord]

    def setup(self, files: list, rules: list, scope: ScopeConfig):
        """配置本次批量任务（主线程调用）。"""
        self._files = list(files)
        self._rules = list(rules)
        self._scope = scope
        self._cancel_flag = False
        self._records = {}

    def cancel(self):
        """请求取消（主线程调用）。"""
        self._cancel_flag = True

    def run(self):
        """线程入口 — 在 STA 线程中执行。"""
        pythoncom.CoInitialize()
        try:
            if not self._connect_autocad():
                return

            total = len(self._files)
            for idx, path in enumerate(self._files):
                if self._cancel_flag:
                    logger.info("收到取消信号，停止处理")
                    break

                self.file_started.emit(path, idx, total)
                self.progress.emit(
                    int(idx / total * 100),
                    f"处理中: {os.path.basename(path)} ({idx+1}/{total})")

                try:
                    count = self._process_dwg(path)
                    self.file_done.emit(path, count)
                except Exception as e:
                    logger.exception(f"处理失败: {path}")
                    self.file_error.emit(path, str(e))

                self.progress.emit(
                    int((idx + 1) / total * 100),
                    f"完成 ({idx+1}/{total})")

            self.progress.emit(100, "处理完成")

            summary = {
                "total": len(self._files),
                "cancelled": self._cancel_flag,
            }
            self.all_done.emit(summary)

        finally:
            self._disconnect_autocad()
            pythoncom.CoUninitialize()

    # ─── AutoCAD 连接 ──────────────────────────────────────────

    def _connect_autocad(self) -> bool:
        """连接 AutoCAD（三层降级: Dispatch → GetActiveObject → fail）。"""
        for attempt in range(2):
            try:
                self._acad = win32com.client.Dispatch("AutoCAD.Application")
                self._acad.Visible = True
                self.connection_status.emit(True, "已启动 AutoCAD")
                return True
            except Exception:
                try:
                    self._acad = win32com.client.GetActiveObject(
                        "AutoCAD.Application")
                    self._acad.Visible = True
                    self.connection_status.emit(True, "已连接 AutoCAD")
                    return True
                except Exception:
                    if attempt == 0:
                        self.msleep(2000)

        self.connection_status.emit(
            False, "无法连接 AutoCAD，请确认已安装并打开")
        return False

    def _disconnect_autocad(self):
        """断开 AutoCAD（不强制退出应用）。"""
        if self._acad is not None:
            try:
                self._acad = None
            except Exception:
                pass

    # ─── DWG 文件处理 ──────────────────────────────────────────

    def _process_dwg(self, path: str) -> int:
        """处理单个 DWG 文件，返回替换次数。"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {path}")

        doc = None
        for attempt in range(3):
            if self._cancel_flag:
                return 0
            try:
                doc = self._acad.Documents.Open(path)
                self.msleep(1000)
                break
            except pythoncom.com_error as e:
                logger.warning(f"打开文件失败 (第{attempt+1}次): {path}")
                if getattr(e, "hresult", None) == -2147418111:
                    self._connect_autocad()
                self.msleep(2000)

        if doc is None:
            raise RuntimeError(f"无法打开文件（已重试3次）: {path}")

        try:
            total_replaced = 0
            records = []

            # 处理模型空间
            total_replaced += self._process_space(
                doc.ModelSpace, path, records)

            # 处理图纸空间
            if self._scope and self._scope.paper_space:
                try:
                    total_replaced += self._process_space(
                        doc.PaperSpace, path, records)
                except Exception as e:
                    logger.warning(f"图纸空间处理失败: {path}: {e}")

            self._records[path] = records
            return total_replaced

        finally:
            try:
                doc.Save()
                doc.Close(True)
            except Exception as e:
                logger.error(f"关闭文件失败: {path}: {e}")

    def _process_space(self, space, file_path: str,
                       records: list) -> int:
        """遍历空间中的实体，返回替换次数。"""
        count = 0
        for entity in space:
            if self._cancel_flag:
                break
            entity = _dyn(entity)
            obj_name = self._safe_get_obj_name(entity)
            if obj_name in ("AcDbText", "AcDbMText"):
                c = self._apply_rules_to_entity(entity, file_path, records)
                count += c
            elif obj_name == "AcDbBlockReference":
                c = self._process_block_ref(entity, file_path, records)
                count += c
        return count

    def _process_block_ref(self, block_ref, file_path: str,
                           records: list) -> int:
        """处理块引用，递归进入嵌套块。"""
        count = 0
        block_ref = _dyn(block_ref)
        try:
            for attrib in block_ref.GetAttributes():
                c = self._apply_rules_to_entity(
                    _dyn(attrib), file_path, records)
                count += c
        except Exception as e:
            logger.warning(f"块引用属性处理失败: {e}")

        # 递归处理嵌套块
        if self._scope and self._scope.nested_blocks:
            try:
                for entity in block_ref:
                    entity = _dyn(entity)
                    obj_name = self._safe_get_obj_name(entity)
                    if obj_name in ("AcDbText", "AcDbMText"):
                        c = self._apply_rules_to_entity(
                            entity, file_path, records)
                        count += c
                    elif obj_name == "AcDbBlockReference":
                        c = self._process_block_ref(
                            entity, file_path, records)
                        count += c
            except Exception:
                pass  # 某些块不支持迭代

        return count

    def _apply_rules_to_entity(self, entity, file_path: str,
                                records: list) -> int:
        """对单个实体应用所有规则，返回替换次数。"""
        entity = _dyn(entity)
        try:
            text = entity.TextString
            if not text:
                return 0
            replaced = 0
            modified = text

            for rule in self._rules:
                if rule.use_regex:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    new_text, n = re.subn(
                        rule.find_text, rule.replace_text,
                        modified, flags=flags)
                    if n > 0:
                        records.append(ReplaceRecord(
                            entity_handle=str(entity.Handle),
                            old_text=modified,
                            new_text=new_text,
                            rule_id=rule.rule_id,
                        ))
                        modified = new_text
                        replaced += n
                else:
                    if rule.case_sensitive:
                        count_val = modified.count(rule.find_text)
                        if count_val > 0:
                            records.append(ReplaceRecord(
                                entity_handle=str(entity.Handle),
                                old_text=modified,
                                new_text=modified.replace(
                                    rule.find_text, rule.replace_text),
                                rule_id=rule.rule_id,
                            ))
                            modified = modified.replace(
                                rule.find_text, rule.replace_text)
                            replaced += count_val
                    else:
                        pattern = re.compile(
                            re.escape(rule.find_text), re.IGNORECASE)
                        new_text, n = pattern.subn(
                            rule.replace_text, modified)
                        if n > 0:
                            records.append(ReplaceRecord(
                                entity_handle=str(entity.Handle),
                                old_text=modified,
                                new_text=new_text,
                                rule_id=rule.rule_id,
                            ))
                            modified = new_text
                            replaced += n

            if replaced > 0:
                entity.TextString = modified
            return replaced
        except Exception as e:
            logger.debug(f"实体处理失败: {e}")
            return 0

    @staticmethod
    def _safe_get_obj_name(entity) -> str:
        """安全获取实体对象名。"""
        try:
            return _dyn(entity).ObjectName or ""
        except Exception:
            return ""
