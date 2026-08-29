"""GitHub Releases 更新检查模块。

启动时查询 GitHub API，比较本地版本与远端 Release 版本号。
网络异常或超时静默跳过，不阻塞程序启动。
"""
import json
import logging
import urllib.request
from typing import Optional, Tuple

from .version import __version__

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/huhaa/CADReplacerApp/releases/latest"


def check_update() -> Tuple[bool, str, str]:
    """检查 GitHub 最新 Release。

    Returns:
        (has_update, latest_version, download_url)
        has_update=False 且其余为空字符串表示无需更新或检查失败。
    """
    try:
        req = urllib.request.Request(GITHUB_API)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "CADReplacerApp")

        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag: str = data.get("tag_name", "")
        if not tag:
            logger.debug("GitHub Release 无 tag_name，跳过更新检查")
            return False, "", ""

        latest_version = tag.lstrip("v").lstrip("V")
        html_url: str = data.get("html_url", "")

        if _version_tuple(latest_version) > _version_tuple(__version__):
            logger.info("发现新版本: %s (当前 %s)", latest_version, __version__)
            return True, latest_version, html_url

        logger.debug("已是最新版本: %s", __version__)
        return False, "", ""

    except urllib.error.URLError as e:
        logger.debug("网络不可达，跳过更新检查: %s", e)
    except Exception:
        logger.debug("更新检查异常", exc_info=True)

    return False, "", ""


def _version_tuple(v: str) -> Tuple[int, ...]:
    """将版本字符串转为可比较的元组，如 '2.0.2' → (2, 0, 2)。"""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0,)
