from __future__ import annotations

import json
from html import escape


def customer_chat_page_html(
    *,
    username: str,
    chat_title: str,
    welcome_message: str,
    quick_phrases: list[str],
) -> str:
    safe_title = escape(chat_title.strip() or "智能客服")
    clean_username = username.strip()

    username_literal = json.dumps(username.strip(), ensure_ascii=False)
    welcome_literal = json.dumps(welcome_message.strip(), ensure_ascii=False)
    quick_phrases_literal = json.dumps(quick_phrases, ensure_ascii=False)

    subtitle = f"当前用户：{clean_username}" if clean_username else "当前用户：访客"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg-top: #dcfce7;
      --bg-bottom: #f8fafc;
      --panel: #ffffff;
      --line: #d1d5db;
      --text: #0f172a;
      --muted: #64748b;
      --user: #0f766e;
      --bot: #e2e8f0;
      --btn: #0f766e;
      --btn-hover: #0b5f59;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 8%, #86efac 0%, transparent 32%),
        radial-gradient(circle at 88% 10%, #7dd3fc 0%, transparent 28%),
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .app {{
      width: min(980px, 100%);
      height: min(86vh, 860px);
      border: 1px solid rgba(15, 23, 42, 0.08);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.84);
      backdrop-filter: blur(10px);
      box-shadow: 0 20px 50px rgba(15, 23, 42, 0.12);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }}
    .head {{
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: linear-gradient(90deg, rgba(15, 118, 110, 0.08), rgba(3, 105, 161, 0.08));
    }}
    .title {{
      margin: 0;
      font-size: 19px;
      font-weight: 700;
      letter-spacing: 0.3px;
    }}
    .sub {{
      margin: 4px 0 0;
      font-size: 12px;
      color: var(--muted);
    }}
    .badge {{
      border: 1px solid rgba(15, 118, 110, 0.35);
      color: #0f766e;
      background: rgba(236, 253, 245, 0.9);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      white-space: nowrap;
    }}
    .messages {{
      overflow-y: auto;
      padding: 18px;
      display: grid;
      gap: 12px;
      align-content: start;
      background:
        linear-gradient(rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.88)),
        repeating-linear-gradient(
          45deg,
          rgba(148, 163, 184, 0.05) 0,
          rgba(148, 163, 184, 0.05) 2px,
          transparent 2px,
          transparent 8px
        );
    }}
    .row {{
      display: flex;
      width: 100%;
    }}
    .row.user {{
      justify-content: flex-end;
    }}
    .row.bot {{
      justify-content: flex-start;
    }}
    .bubble {{
      max-width: min(78%, 720px);
      border-radius: 14px;
      padding: 10px 12px;
      line-height: 1.6;
      font-size: 14px;
      box-shadow: 0 6px 14px rgba(15, 23, 42, 0.08);
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .user .bubble {{
      background: var(--user);
      color: #fff;
      border-bottom-right-radius: 6px;
    }}
    .bot .bubble {{
      background: var(--bot);
      color: var(--text);
      border-bottom-left-radius: 6px;
    }}
    .typing {{
      display: inline-flex;
      gap: 4px;
      align-items: center;
      min-width: 38px;
    }}
    .typing span {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #64748b;
      display: inline-block;
      animation: blink 1.1s infinite ease-in-out;
    }}
    .typing span:nth-child(2) {{
      animation-delay: 0.18s;
    }}
    .typing span:nth-child(3) {{
      animation-delay: 0.36s;
    }}
    @keyframes blink {{
      0%, 100% {{ opacity: 0.2; transform: translateY(0); }}
      50% {{ opacity: 1; transform: translateY(-2px); }}
    }}
    .quick {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 0 18px 10px;
    }}
    .quick button {{
      border: 1px solid var(--line);
      background: #fff;
      color: #334155;
      border-radius: 999px;
      font-size: 12px;
      padding: 6px 10px;
      cursor: pointer;
    }}
    .quick button:hover {{
      border-color: #0f766e;
      color: #0f766e;
    }}
    .input-bar {{
      border-top: 1px solid var(--line);
      padding: 12px;
      background: #f8fafc;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
    }}
    .input-bar textarea {{
      width: 100%;
      min-height: 48px;
      max-height: 48px;
      height: 48px;
      resize: none;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 10px 12px;
      outline: none;
      font: inherit;
      line-height: 1.5;
      background: #fff;
    }}
    .input-bar textarea:focus {{
      border-color: #0f766e;
    }}
    .send-btn {{
      align-self: end;
      border: 0;
      border-radius: 10px;
      min-width: 92px;
      height: 48px;
      background: var(--btn);
      color: #fff;
      font-size: 14px;
      cursor: pointer;
      padding: 0 14px;
    }}
    .send-btn:hover {{
      background: var(--btn-hover);
    }}
    .send-btn:disabled {{
      opacity: 0.65;
      cursor: not-allowed;
    }}
    @media (max-width: 720px) {{
      body {{
        padding: 10px;
      }}
      .app {{
        height: 94vh;
        border-radius: 12px;
      }}
      .bubble {{
        max-width: 86%;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <header class="head">
      <div>
        <h1 class="title">{safe_title}</h1>
        <p class="sub">{escape(subtitle)}</p>
      </div>
    </header>

    <section class="messages" id="messages"></section>
    <div class="quick" id="quickList"></div>

    <footer class="input-bar">
      <textarea id="input" placeholder="请输入您的问题，回车发送（Shift+回车换行）"></textarea>
      <button id="sendBtn" class="send-btn" type="button">发送</button>
    </footer>
  </div>

  <script>
    const API_URL_PREFIX = "/api/?content=";
    const USERNAME = {username_literal};
    const WELCOME_MESSAGE = {welcome_literal};
    const QUICK_PHRASES = {quick_phrases_literal};

    const messagesEl = document.getElementById("messages");
    const inputEl = document.getElementById("input");
    const sendBtn = document.getElementById("sendBtn");

    function addMessage(role, text) {{
      const row = document.createElement("div");
      row.className = "row " + role;
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = text;
      row.appendChild(bubble);
      messagesEl.appendChild(row);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return row;
    }}

    function addTyping() {{
      const row = document.createElement("div");
      row.className = "row bot";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      const typing = document.createElement("div");
      typing.className = "typing";
      typing.innerHTML = "<span></span><span></span><span></span>";
      bubble.appendChild(typing);
      row.appendChild(bubble);
      messagesEl.appendChild(row);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return row;
    }}

    function renderWelcome() {{
      if (!WELCOME_MESSAGE) return;
      addMessage("bot", WELCOME_MESSAGE);
    }}

    function renderQuickPhrases() {{
      const quickEl = document.getElementById("quickList");
      if (!quickEl) return;
      quickEl.innerHTML = "";
      const list = Array.isArray(QUICK_PHRASES)
        ? QUICK_PHRASES.map((item) => String(item || "").trim()).filter((item) => !!item)
        : [];
      if (!list.length) {{
        quickEl.style.display = "none";
        return;
      }}
      quickEl.style.display = "flex";
      list.forEach((phrase) => {{
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = phrase;
        button.setAttribute("data-q", phrase);
        button.addEventListener("click", () => ask(phrase));
        quickEl.appendChild(button);
      }});
    }}

    async function ask(content) {{
      const text = String(content || "").trim();
      if (!text) return;

      addMessage("user", text);
      inputEl.value = "";
      sendBtn.disabled = true;
      const typingRow = addTyping();
      try {{
        const res = await fetch(API_URL_PREFIX + encodeURIComponent(text), {{
          method: "GET"
        }});
        const data = await res.json().catch(() => ({{}}));
        if (!res.ok) {{
          throw new Error(data.detail || "请求失败");
        }}
        const answer = String(data.answer || "暂时无法回答，请稍后再试");
        typingRow.remove();
        addMessage("bot", answer);
      }} catch (err) {{
        typingRow.remove();
        addMessage("bot", "请求异常，请稍后再试");
      }} finally {{
        sendBtn.disabled = false;
        inputEl.focus();
      }}
    }}

    sendBtn.addEventListener("click", () => {{
      ask(inputEl.value);
    }});

    inputEl.addEventListener("keydown", (event) => {{
      if (event.key === "Enter" && !event.shiftKey) {{
        event.preventDefault();
        ask(inputEl.value);
      }}
    }});

    renderQuickPhrases();
    renderWelcome();
    inputEl.focus();
  </script>
</body>
</html>
"""
