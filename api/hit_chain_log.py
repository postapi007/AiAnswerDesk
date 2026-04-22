from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


LOG_DIR_PATH = Path(__file__).resolve().parent.parent / "logs"


# 获取当前日期对应的日志文件路径，格式：logs/YYYYMMDD.log
def get_log_file_path(current_time: datetime | None = None) -> Path:
    now = current_time or datetime.now()
    return LOG_DIR_PATH / f"{now.strftime('%Y%m%d')}.log"


# 将单次客服检索链路写入日志（每行一条：时间前缀 + JSON）。
def write_hit_chain_log(record: dict[str, Any]) -> None:
    now = datetime.now()
    timestamp_text = now.strftime("%Y/%m/%d %H:%M:%S")
    log_file = get_log_file_path(now)
    payload = {
        "timestamp": timestamp_text,
        **record,
    }
    try:
        LOG_DIR_PATH.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp_text} {json.dumps(payload, ensure_ascii=False)}\n")
    except OSError:
        # 日志写入失败不影响主流程。
        return
