"""数据模型层 — 纯数据，不依赖 Qt 或 COM。"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from collections import defaultdict


class FileStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    NO_MATCH = "no_match"


@dataclass
class ReplaceRule:
    """单条查找替换规则。"""
    find_text: str
    replace_text: str
    use_regex: bool = False
    case_sensitive: bool = True
    rule_id: str = ""

    def __post_init__(self):
        if not self.rule_id:
            import uuid
            self.rule_id = uuid.uuid4().hex[:8]

    def to_dict(self) -> dict:
        return {
            "find_text": self.find_text,
            "replace_text": self.replace_text,
            "use_regex": self.use_regex,
            "case_sensitive": self.case_sensitive,
            "rule_id": self.rule_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReplaceRule":
        return cls(
            find_text=d.get("find_text", ""),
            replace_text=d.get("replace_text", ""),
            use_regex=d.get("use_regex", False),
            case_sensitive=d.get("case_sensitive", True),
            rule_id=d.get("rule_id", ""),
        )

    def __hash__(self):
        return hash((self.find_text, self.replace_text, self.use_regex, self.case_sensitive))

    def __eq__(self, other):
        if not isinstance(other, ReplaceRule):
            return False
        return (self.find_text, self.replace_text,
                self.use_regex, self.case_sensitive) == \
               (other.find_text, other.replace_text,
                other.use_regex, other.case_sensitive)


@dataclass
class ReplaceRecord:
    """单次替换记录，用于撤销。"""
    entity_handle: str
    old_text: str
    new_text: str
    rule_id: str


@dataclass
class FileResult:
    """单个文件的处理结果。"""
    file_path: str
    status: FileStatus = FileStatus.PENDING
    replaced_count: int = 0
    error_message: str = ""
    records: list = field(default_factory=list)


@dataclass
class ScopeConfig:
    """替换范围配置。"""
    text: bool = True
    mtext: bool = True
    attribute: bool = True
    paper_space: bool = False
    nested_blocks: bool = True

    def to_dict(self) -> dict:
        return {
            "text": self.text, "mtext": self.mtext,
            "attribute": self.attribute, "paper_space": self.paper_space,
            "nested_blocks": self.nested_blocks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScopeConfig":
        return cls(
            text=d.get("text", True),
            mtext=d.get("mtext", True),
            attribute=d.get("attribute", True),
            paper_space=d.get("paper_space", False),
            nested_blocks=d.get("nested_blocks", True),
        )


@dataclass
class AppConfig:
    """应用持久化配置。"""
    rules: list = field(default_factory=list)
    scope: dict = field(default_factory=dict)
    last_files: list = field(default_factory=list)
    window_geometry: dict = field(default_factory=dict)


class ReplacerModel:
    """替换任务的数据模型 — 管理规则、文件、历史、结果。"""

    def __init__(self):
        self.rules: list = []               # list[ReplaceRule]
        self.files: list = []               # list[str]
        self._history: dict = defaultdict(list)  # file_path -> list[ReplaceRecord]
        self._results: dict = {}            # file_path -> FileResult

    # --- 规则管理 ---
    def add_rule(self, rule: ReplaceRule) -> bool:
        if rule not in self.rules:
            self.rules.append(rule)
            return True
        return False

    def remove_rule(self, index: int):
        if 0 <= index < len(self.rules):
            self.rules.pop(index)

    def clear_rules(self):
        self.rules.clear()

    # --- 文件管理 ---
    def add_file(self, file_path: str) -> bool:
        if file_path not in self.files:
            self.files.append(file_path)
            return True
        return False

    def remove_file(self, index: int):
        if 0 <= index < len(self.files):
            self.files.pop(index)

    def clear_files(self):
        self.files.clear()

    # --- 替换历史 ---
    def record_replace(self, file_path: str, record: ReplaceRecord):
        self._history[file_path].append(record)

    def get_history(self, file_path: str) -> list:
        return list(self._history.get(file_path, []))

    def clear_history(self, file_path: str):
        self._history.pop(file_path, None)

    def clear_all_history(self):
        self._history.clear()

    def get_all_history_files(self) -> list:
        return list(self._history.keys())

    # --- 文件结果 ---
    def set_file_result(self, file_path: str, status: FileStatus,
                        replaced_count: int = 0, error_message: str = ""):
        result = self._results.get(file_path, FileResult(file_path))
        result.status = status
        result.replaced_count = replaced_count
        result.error_message = error_message
        self._results[file_path] = result

    def get_file_result(self, file_path: str) -> Optional[FileResult]:
        return self._results.get(file_path, FileResult(file_path))

    def get_summary(self) -> dict:
        total = len(self.files)
        done = sum(1 for r in self._results.values() if r.status == FileStatus.DONE)
        failed = sum(1 for r in self._results.values() if r.status == FileStatus.FAILED)
        skipped = sum(1 for r in self._results.values() if r.status == FileStatus.SKIPPED)
        no_match = sum(1 for r in self._results.values() if r.status == FileStatus.NO_MATCH)
        total_replaced = sum(r.replaced_count for r in self._results.values())
        return {
            "total": total, "done": done, "failed": failed,
            "skipped": skipped, "no_match": no_match,
            "total_replaced": total_replaced,
        }
