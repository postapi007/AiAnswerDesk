from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from config.settings import CONFIG_FILE_PATH, _strip_json_comments, load_settings


def _read_app_config_text(config_path: Path = CONFIG_FILE_PATH) -> str:
    try:
        return config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {exc}") from exc


def _read_app_config_dict(config_path: Path = CONFIG_FILE_PATH) -> dict[str, Any]:
    raw_text = _read_app_config_text(config_path)
    try:
        parsed = json.loads(_strip_json_comments(raw_text.lstrip("\ufeff")))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"配置文件JSON解析失败: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="配置文件格式错误，根节点必须是对象")
    return parsed


def _replace_key_value(block_text: str, key: str, literal_value: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf'(^\s*"{re.escape(key)}"\s*:\s*)(.+?)(\s*,?\s*(?://.*)?$)',
        re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{literal_value}{match.group(3)}"

    replaced_text, count = pattern.subn(repl, block_text, count=1)
    return replaced_text, count > 0


def _find_named_block_bounds(raw_text: str, block_name: str) -> tuple[int, int]:
    block_match = re.search(rf'"{re.escape(block_name)}"\s*:\s*\{{', raw_text)
    if not block_match:
        raise HTTPException(status_code=500, detail=f'配置文件缺少 "{block_name}" 节点')

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
        raise HTTPException(status_code=500, detail=f'配置文件 "{block_name}" 节点结构错误')

    return start, i


def _replace_keys_in_block(raw_text: str, block_name: str, replacements: dict[str, str]) -> str:
    start, end = _find_named_block_bounds(raw_text, block_name)
    block = raw_text[start:end]
    missing_keys: list[str] = []
    updated_block = block
    for key, literal in replacements.items():
        updated_block, changed = _replace_key_value(updated_block, key, literal)
        if not changed:
            missing_keys.append(key)

    if missing_keys:
        raise HTTPException(
            status_code=500,
            detail=f'配置文件 "{block_name}" 缺少字段: {", ".join(missing_keys)}',
        )

    return f"{raw_text[:start]}{updated_block}{raw_text[end:]}"


def render_welcome_message(template: str, username: str) -> str:
    clean_template = str(template or "").strip()
    if not clean_template:
        return ""
    clean_username = str(username or "").strip()
    return clean_template.replace("{username}", clean_username).strip()


def get_web_chat_settings() -> dict[str, Any]:
    parsed = _read_app_config_dict(CONFIG_FILE_PATH)
    web = parsed.get("web")
    if not isinstance(web, dict):
        raise HTTPException(status_code=500, detail='配置文件缺少 "web" 节点')

    runtime = load_settings(CONFIG_FILE_PATH)
    raw_quick_phrases = web.get("quick_phrases")
    quick_phrases: list[str] = []
    if isinstance(raw_quick_phrases, list):
        for item in raw_quick_phrases:
            phrase = str(item or "").strip()
            if phrase:
                quick_phrases.append(phrase)
    elif isinstance(raw_quick_phrases, str):
        for item in raw_quick_phrases.splitlines():
            phrase = item.strip()
            if phrase:
                quick_phrases.append(phrase)

    return {
        "config_path": str(CONFIG_FILE_PATH),
        "web": {
            "enabled": (
                web.get("enabled")
                if isinstance(web.get("enabled"), bool)
                else runtime.web_enabled
            ),
            "chat_title": str(web.get("chat_title", runtime.web_chat_title)).strip()
            or runtime.web_chat_title,
            "welcome_template": str(web.get("welcome_template", runtime.web_welcome_template)),
            "quick_phrases": quick_phrases or list(runtime.web_quick_phrases),
        },
        "effective_web": {
            "enabled": runtime.web_enabled,
            "chat_title": runtime.web_chat_title,
            "welcome_template": runtime.web_welcome_template,
            "quick_phrases": list(runtime.web_quick_phrases),
        },
    }


def update_web_chat_settings(
    enabled: bool,
    chat_title: str,
    welcome_template: str,
    quick_phrases: list[str],
) -> dict[str, Any]:
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="enabled 必须是布尔值")

    clean_title = str(chat_title or "").strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="chat_title 不能为空")

    clean_template = str(welcome_template or "").strip()
    unique_quick_phrases: list[str] = []
    seen_phrases: set[str] = set()
    for item in quick_phrases:
        phrase = str(item or "").strip()
        if not phrase:
            continue
        if phrase in seen_phrases:
            continue
        seen_phrases.add(phrase)
        unique_quick_phrases.append(phrase)

    raw_text = _read_app_config_text(CONFIG_FILE_PATH)
    updated_text = _replace_keys_in_block(
        raw_text=raw_text,
        block_name="web",
        replacements={
            "enabled": "true" if enabled else "false",
            "chat_title": json.dumps(clean_title, ensure_ascii=False),
            "welcome_template": json.dumps(clean_template, ensure_ascii=False),
            "quick_phrases": json.dumps(unique_quick_phrases, ensure_ascii=False),
        },
    )
    try:
        CONFIG_FILE_PATH.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"写入配置文件失败: {exc}") from exc

    return {
        "saved": True,
        "message": "已更新应答界面配置",
        **get_web_chat_settings(),
    }
