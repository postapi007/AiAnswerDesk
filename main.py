from __future__ import annotations

import json
import re
import secrets
import string
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import router
from admin import router as admin_router
from config.settings import CONFIG_FILE_PATH, _strip_json_comments
from web import router as web_router


app = FastAPI()
app.include_router(router)
app.include_router(admin_router)
app.include_router(web_router)

PICTURE_DIR = Path(__file__).resolve().parent / "picture"
PICTURE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/picture", StaticFiles(directory=str(PICTURE_DIR)), name="picture")


def _find_named_block_bounds(raw_text: str, block_name: str) -> tuple[int, int]:
    block_match = re.search(rf'"{re.escape(block_name)}"\s*:\s*\{{', raw_text)
    if not block_match:
        raise ValueError(f'配置文件缺少 "{block_name}" 节点')

    start = block_match.end()
    i = start
    depth = 1
    in_string = False
    escaped = False
    while i < len(raw_text):
        ch = raw_text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1

    if depth != 0 or i >= len(raw_text):
        raise ValueError(f'配置文件 "{block_name}" 节点结构错误')
    return start, i


def _upsert_admin_route_prefix(raw_text: str, route_prefix: str) -> str:
    start, end = _find_named_block_bounds(raw_text, "admin")
    block = raw_text[start:end]

    replace_pattern = re.compile(
        r'(^\s*"route_prefix"\s*:\s*")([^"]*)(".*$)',
        re.MULTILINE,
    )
    replaced_block, count = replace_pattern.subn(rf'\g<1>{route_prefix}\g<3>', block, count=1)
    if count > 0:
        return f"{raw_text[:start]}{replaced_block}{raw_text[end:]}"

    lines = block.splitlines()
    key_indent = "    "
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('"') and ":" in stripped:
            key_indent = line[: len(line) - len(line.lstrip())]
            break

    for idx in range(len(lines) - 1, -1, -1):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or ":" not in stripped:
            continue
        no_comment = line.split("//", 1)[0]
        if "," in no_comment:
            break
        if "//" in line:
            before_comment, comment = line.split("//", 1)
            lines[idx] = f"{before_comment.rstrip()}, //{comment}"
        else:
            lines[idx] = f"{line.rstrip()},"
        break

    insert_at = len(lines)
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip():
            insert_at = idx + 1
            break

    lines.insert(
        insert_at,
        f'{key_indent}"route_prefix": "{route_prefix}", // 后台路由前缀（例如 /admin）',
    )
    updated_block = "\n".join(lines)
    return f"{raw_text[:start]}{updated_block}{raw_text[end:]}"


def _random_route_suffix(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def run_admin_revise() -> int:
    route_prefix = f"/{_random_route_suffix(10)}"
    try:
        raw_text = CONFIG_FILE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读取配置失败: {exc}")
        return 1

    try:
        updated_text = _upsert_admin_route_prefix(raw_text, route_prefix)
        json.loads(_strip_json_comments(updated_text.lstrip("\ufeff")))
    except Exception as exc:
        print(f"更新配置失败: {exc}")
        return 1

    try:
        CONFIG_FILE_PATH.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        print(f"写入配置失败: {exc}")
        return 1

    print(f"后台路由已更新: {route_prefix}")
    print("请重启服务后生效。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "AdminRevise":
        raise SystemExit(run_admin_revise())
    print("Usage: python main.py AdminRevise")
