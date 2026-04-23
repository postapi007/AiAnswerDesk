from __future__ import annotations

from html import escape


def login_page_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>后台登录</title>
  <style>
    :root {
      --bg: #f1f5f9;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --line: #e2e8f0;
      --primary: #0f766e;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at 20% 10%, #d1fae5 0%, var(--bg) 40%);
      color: var(--text);
      font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    }
    .card {
      width: min(420px, 92vw);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
      padding: 24px;
    }
    h1 { margin: 0 0 6px; font-size: 22px; }
    p { margin: 0 0 18px; color: var(--muted); font-size: 14px; }
    label { display: block; font-size: 14px; margin-bottom: 8px; }
    input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
    }
    input:focus { border-color: var(--primary); }
    button {
      margin-top: 14px;
      width: 100%;
      border: 0;
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--primary);
      color: #fff;
      font-size: 14px;
      cursor: pointer;
    }
    .msg {
      margin-top: 10px;
      min-height: 18px;
      font-size: 13px;
      color: var(--danger);
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>知识库管理后台</h1>
    <label for="password">登录密码</label>
    <input id="password" type="password" placeholder="请输入后台密码" />
    <button id="loginBtn" type="button">登录</button>
    <div id="msg" class="msg"></div>
  </div>

  <script>
    async function login() {
      const msg = document.getElementById("msg");
      const password = document.getElementById("password").value.trim();
      if (!password) {
        msg.textContent = "请输入密码";
        return;
      }

      msg.textContent = "";
      try {
        const res = await fetch("/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ password })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          msg.textContent = data.detail || "登录失败";
          return;
        }
        location.href = "/admin";
      } catch (err) {
        msg.textContent = "请求失败，请稍后重试";
      }
    }

    document.getElementById("loginBtn").addEventListener("click", login);
    document.getElementById("password").addEventListener("keydown", (e) => {
      if (e.key === "Enter") login();
    });
  </script>
</body>
</html>
"""


def _format_float(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def dashboard_page_html(
    min_embedding_chars: int,
    similarity_threshold: float,
    not_configured_answer: str,
    faq_collection: str,
    pending_collection: str,
    docs_collection: str,
) -> str:
    html_text = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>知识库后台管理</title>
  <style>
    :root {
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --line: #e2e8f0;
      --primary: #0369a1;
      --danger: #b91c1c;
      --ok: #166534;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: linear-gradient(140deg, #e0f2fe 0%, #f8fafc 45%);
      color: var(--text);
      font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    }
    .layout {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 220px 1fr;
    }
    .sidebar {
      border-right: 1px solid var(--line);
      background: #0b1f35;
      color: #dbeafe;
      padding: 18px 14px;
      display: flex;
      flex-direction: column;
    }
    .brand {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 18px;
      letter-spacing: 0.5px;
    }
    .menu .menu-btn {
      width: 100%;
      text-align: left;
      border: 0;
      background: #133456;
      color: #e2e8f0;
      padding: 10px 12px;
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
    }
    .menu .menu-btn.active {
      background: #1d4ed8;
      color: #fff;
    }
    .logout {
      margin-top: auto;
      border: 1px solid #2f4868;
      background: transparent;
      color: #bfdbfe;
      border-radius: 8px;
      padding: 8px 10px;
      cursor: pointer;
      width: 100%;
    }
    .main { padding: 20px; }
    .view { display: none; }
    .view.active {
      display: grid;
      gap: 14px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
    }
    details {
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #f8fafc;
      padding: 12px;
    }
    summary {
      cursor: pointer;
      user-select: none;
      font-weight: 600;
    }
    .flow-wrap {
      margin-top: 12px;
      display: grid;
      gap: 6px;
      font-size: 14px;
      line-height: 1.6;
    }
    .flow-arrow {
      color: var(--muted);
      font-size: 12px;
    }
    .flow-code {
      margin-top: 6px;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 12px;
      font-size: 12px;
      overflow: auto;
      white-space: pre;
      word-break: break-word;
    }
    h2 {
      margin: 0 0 10px;
      font-size: 18px;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }
    .grid-two {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    label {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .switch-row {
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }
    .switch-row input[type="checkbox"] {
      width: auto;
      transform: translateY(1px);
    }
    .doc-mode-group {
      margin-top: 6px;
      display: inline-flex;
      gap: 6px;
      padding: 4px;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      background: #f1f5f9;
    }
    .doc-mode-item {
      margin: 0;
      display: inline-flex;
      align-items: center;
    }
    .doc-mode-item input {
      display: none;
    }
    .doc-mode-item span {
      display: inline-block;
      min-width: 92px;
      text-align: center;
      padding: 8px 12px;
      border-radius: 9px;
      font-size: 13px;
      color: #334155;
      cursor: pointer;
      transition: all 0.16s ease;
    }
    .doc-mode-item input:checked + span {
      background: linear-gradient(135deg, #0284c7, #0ea5e9);
      color: #fff;
      font-weight: 600;
      box-shadow: 0 6px 14px rgba(2, 132, 199, 0.25);
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 9px 10px;
      font-size: 14px;
      font-family: inherit;
      outline: none;
    }
    textarea { min-height: 130px; resize: vertical; }
    #qaTemplateEditor { min-height: 720px; }
    input:focus, textarea:focus, select:focus { border-color: var(--primary); }
    .btn {
      border: 0;
      border-radius: 8px;
      padding: 9px 12px;
      color: #fff;
      background: var(--primary);
      cursor: pointer;
      font-size: 13px;
    }
    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .btn-danger { background: var(--danger); }
    .btn-row { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
    .toolbar {
      margin-bottom: 10px;
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
    }
    .search-box {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .search-box input {
      width: min(340px, 70vw);
    }
    .status {
      margin-top: 8px;
      min-height: 18px;
      font-size: 13px;
    }
    .file-hint {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }
    .file-upload-row {
      margin-top: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .file-upload-name {
      max-width: min(560px, 74vw);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      background: #f8fafc;
    }
    .preview-box {
      margin-top: 10px;
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #f8fafc;
    }
    .preview-meta {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .error-lines {
      margin-top: 8px;
      color: var(--danger);
      font-size: 12px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .pager {
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .pager-info {
      font-size: 13px;
      color: var(--muted);
      min-width: 180px;
      text-align: right;
    }
    .status.ok { color: var(--ok); }
    .status.err { color: var(--danger); }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      padding: 10px 8px;
      word-break: break-all;
    }
    th { background: #f8fafc; }
    .col-check { width: 6%; }
    .col-id { width: 20%; }
    .col-q { width: 22%; }
    .col-a { width: 26%; }
    .col-score { width: 12%; }
    .col-op { width: 14%; }
    .row-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    @media (max-width: 960px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .grid-two { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">后台管理</div>
      <div class="menu">
        <button class="menu-btn active" id="menuConsole" type="button">控制台</button>
        <button class="menu-btn" id="menuKnowledge" type="button">知识库列表</button>
        <button class="menu-btn" id="menuDocChunk" type="button">知识库分片</button>
        <button class="menu-btn" id="menuPending" type="button">知识库待审核</button>
        <button class="menu-btn" id="menuWebReply" type="button">应答界面</button>
        <button class="menu-btn" id="menuLlmTemplate" type="button">LLM模版</button>
        <button class="menu-btn" id="menuSettings" type="button">系统设置</button>
      </div>
      <button class="logout" id="logoutBtn" type="button">退出登录</button>
    </aside>
    <main class="main">
      <section class="view active" id="consoleView">
        <section class="card">
          <h2>控制台</h2>
          <p class="muted">这里说明客服检索链路，便于排查命中和未命中原因。</p>
          <details open>
            <summary>系统说明（点击展开）</summary>
            <div class="flow-wrap">
              <div>请求：<code>/api/?content=怎么退款</code></div>
              <div class="flow-arrow">↓</div>
              <div>关键词归一化匹配（去空格、大小写统一、全半角统一）</div>
              <div class="flow-arrow">↓</div>
              <div>长度小于 <code>__MIN_EMBEDDING_CHARS__</code> 时，直接返回 <code>__NOT_CONFIGURED_ANSWER__</code></div>
              <div>长度大于等于 <code>__MIN_EMBEDDING_CHARS__</code> 时，继续检索</div>
              <div class="flow-arrow">↓</div>
              <div>1. 命中知识库，直接返回答案</div>
              <div>2. (可以开启)未命中则走 知识库 检索 且分数 ≥ <code>__SIMILARITY_THRESHOLD__</code>；知识库 命中后会把当前问法回写到知识库</div>
              <div class="flow-arrow">↓</div>
              <div>1. (可以开启)执行LLM问答大模型，LLM问答结果自动写入知识库的开启时直写知识库，关闭时写入待审核库，需要手动通过</div>
              <div>2. LLM自定义模版，如果包含 <code>{fragmenteddata}</code> 将会匹配知识库分片</div>
              <div>3. 如果请求异常，直接返回 <code>__NOT_CONFIGURED_ANSWER__</code></div>
              <div class="flow-arrow">↓</div>
              <div>如果都没有命中或者LLM异常,直接返回 <code>__NOT_CONFIGURED_ANSWER__</code></div>
              <div>返回示例：</div>
              <div class="flow-code">{
  "content": "怎么退款",
  "vector_hit": true,
  "answer": "退款需要9个工作日"
}</div>
            </div>
          </details>
        </section>
      </section>

      <section class="view" id="knowledgeView">
        <section class="card">
          <h2>知识库管理</h2>
          <p class="muted">支持搜索、新增、删除、批量新增和批量删除(新增将会消耗EM的TOKEN)。</p>
        </section>

        <section class="grid-two">
          <div class="card" id="singleKnowledgeCard">
            <h2>新增单条知识</h2>
            <label for="singleQuestion">问题</label>
            <input id="singleQuestion" placeholder="例如：怎么退款" />
            <label for="singleAnswer" style="margin-top:8px;">答案</label>
            <textarea id="singleAnswer" placeholder="例如：退款需要7个工作日"></textarea>
            <div class="btn-row">
              <button class="btn" id="addBtn" type="button">新增</button>
            </div>
            <div class="status" id="singleStatus"></div>
          </div>

          <div class="card" id="batchImportCard">
            <h2>批量导入（xlsx/txt）</h2>
            <p class="muted">
              支持文件上传与文本导入，先预览再导入。<br />
              txt格式：每行 `问题|答案` 或 `问题[TAB]答案`<br />
              xlsx格式：默认读取第1个工作表，按前两列（问题、答案）解析（可有表头）
            </p>
            <label>分割类型</label>
            <div class="doc-mode-group">
              <label class="doc-mode-item"><input type="radio" name="batchSourceMode" value="text" checked /><span>文本</span></label>
              <label class="doc-mode-item"><input type="radio" name="batchSourceMode" value="file" /><span>上传文件</span></label>
            </div>

            <div id="batchModeTextPanel" style="margin-top:8px;">
              <label for="batchContent">粘贴txt内容</label>
              <textarea id="batchContent" placeholder="怎么退款|退款需要7个工作日&#10;多久到账|预计3-7个工作日"></textarea>
            </div>

            <div id="batchModeFilePanel" style="margin-top:8px; display:none;">
              <label for="batchFileInput">上传文件（.xlsx / .txt）</label>
              <div class="file-upload-row">
                <button class="btn" id="batchPickFileBtn" type="button">选择文件</button>
                <span class="file-upload-name" id="batchFileName">未选择文件</span>
              </div>
              <input id="batchFileInput" type="file" accept=".xlsx,.txt" style="display:none;" />
              <div class="file-hint">支持 .xlsx 和 .txt 文件</div>
            </div>

            <div class="switch-row">
              <input id="batchRollbackOnError" type="checkbox" checked />
              <label for="batchRollbackOnError" style="margin:0;">导入出错时回滚已写入数据</label>
            </div>
            <div class="btn-row">
              <button class="btn" id="previewBatchBtn" type="button">导入预览</button>
              <button class="btn" id="batchBtn" type="button">确认导入</button>
            </div>
            <div class="status" id="batchStatus"></div>
          </div>
        </section>

        <section class="card">
          <h2 id="knowledgeListTitle">知识列表</h2>
          <div class="toolbar">
            <div class="search-box">
              <input id="searchKeyword" placeholder="输入关键字搜索（问题/答案/id）" />
              <button class="btn" id="searchBtn" type="button">搜索</button>
              <button class="btn" id="resetSearchBtn" type="button">重置</button>
            </div>
            <div class="btn-row" style="margin-top:0;">
              <button class="btn" id="listRefreshBtn" type="button">刷新</button>
              <button class="btn btn-danger" id="batchDeleteBtn" type="button">批量删除勾选</button>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th class="col-check"><input id="selectAllCheckbox" type="checkbox" /></th>
                <th class="col-id">ID</th>
                <th class="col-q">问题</th>
                <th class="col-a">答案</th>
                <th class="col-score" id="metricHeader">相似度</th>
                <th class="col-op" id="operationHeader">操作</th>
              </tr>
            </thead>
            <tbody id="knowledgeTableBody"></tbody>
          </table>
          <div class="status" id="tableStatus"></div>
          <div class="pager">
            <button class="btn" id="prevPageBtn" type="button">上一页</button>
            <button class="btn" id="nextPageBtn" type="button">下一页</button>
            <div class="pager-info" id="pageInfo">第 1 / 1 页，共 0 条</div>
          </div>
        </section>
      </section>

      <section class="view" id="docChunkView">
        <section class="card">
          <h2>知识库分片</h2>
          <p class="muted">目标集合：<code>__DOCS_COLLECTION__</code>，支持导入文件切片后写入向量库。</p>
          <p class="muted">支持格式：.txt / .md / .markdown / .csv / .json / .jsonl / .docx / .xlsx / 图片（png/jpg/jpeg/webp/gif/bmp/svg）</p>
        </section>

        <section class="card">
          <label style="margin-top:10px;">分段分隔符</label>
          <div class="doc-mode-group">
            <label class="doc-mode-item"><input type="radio" name="docChunkDelimiterMode" value="newline" checked /><span>换行符</span></label>
            <label class="doc-mode-item"><input type="radio" name="docChunkDelimiterMode" value="double_newline" /><span>两个换行符</span></label>
            <label class="doc-mode-item"><input type="radio" name="docChunkDelimiterMode" value="page_break" /><span>分页符</span></label>
            <label class="doc-mode-item"><input type="radio" name="docChunkDelimiterMode" value="custom" /><span>自定义分隔符</span></label>
          </div>
          <div id="docChunkCustomDelimiterPanel" style="margin-top:10px; display:none;">
            <label for="docChunkCustomDelimiter">自定义分隔符（最多20字符）</label>
            <input id="docChunkCustomDelimiter" type="text" maxlength="20" placeholder="请输入分隔符，例如 ###" />
          </div>

          <label style="margin-top:16px;">分割类型</label>
          <div class="doc-mode-group">
            <label class="doc-mode-item"><input type="radio" name="docChunkSourceMode" value="text" checked /><span>文本</span></label>
            <label class="doc-mode-item"><input type="radio" name="docChunkSourceMode" value="file" /><span>文件</span></label>
            <label class="doc-mode-item"><input type="radio" name="docChunkSourceMode" value="image" /><span>图片</span></label>
          </div>

          <div id="docChunkModeFilePanel" style="margin-top:10px; display:none;">
            <label for="docChunkFileInput">上传文件</label>
            <div class="file-upload-row">
              <button class="btn" id="docChunkPickFileBtn" type="button">选择文件</button>
              <span class="file-upload-name" id="docChunkFileName">未选择文件</span>
            </div>
            <input id="docChunkFileInput" type="file" accept=".txt,.md,.markdown,.csv,.json,.jsonl,.docx,.xlsx" style="display:none;" />
            <div class="file-hint">支持文档文件：txt/md/csv/json/jsonl/docx/xlsx。</div>
          </div>

          <div id="docChunkModeImagePanel" style="margin-top:10px; display:none;">
            <label for="docImageUploadInput">图片上传（上传到项目 /picture）</label>
            <div class="file-upload-row">
              <button class="btn" id="docChunkPickImageBtn" type="button">选择图片</button>
              <span class="file-upload-name" id="docImageSelectedName">未选择图片</span>
            </div>
            <input id="docImageUploadInput" type="file" accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,.svg" style="display:none;" />
            <div class="btn-row">
              <button class="btn" id="uploadDocImageBtn" type="button">上传图片到 /picture</button>
              <button class="btn" id="clearUploadedDocImageBtn" type="button">清空已上传图片</button>
            </div>
            <div class="preview-meta" id="docImageUploadResult">未上传图片</div>
          </div>

          <div id="docChunkModeTextPanel" style="margin-top:10px;">
            <label for="docChunkContent">粘贴文档内容</label>
            <textarea id="docChunkContent" placeholder="在这里粘贴需要切片的文档内容"></textarea>
          </div>

          <div class="grid-two" style="margin-top:10px;">
            <div>
              <label for="docChunkSize">切片长度（100~1200）</label>
              <input id="docChunkSize" type="number" min="100" max="1200" step="1" value="300" />
            </div>
            <div>
              <label for="docChunkOverlap">切片重叠（0~300）</label>
              <input id="docChunkOverlap" type="number" min="0" max="300" step="1" value="60" />
            </div>
          </div>

          <div class="switch-row">
            <input id="docChunkRollbackOnError" type="checkbox" checked />
            <label for="docChunkRollbackOnError" style="margin:0;">导入出错时回滚已写入数据</label>
          </div>

          <div class="btn-row">
            <button class="btn" id="previewDocChunkBtn" type="button">切片预览</button>
            <button class="btn" id="importDocChunkBtn" type="button">确认导入</button>
          </div>
          <div class="status" id="docChunkStatus"></div>

          <div class="preview-box" id="docChunkPreviewBox" style="display:none;">
            <div class="preview-meta" id="docChunkPreviewSummary"></div>
            <div class="preview-meta" id="docChunkPreviewSample"></div>
          </div>
        </section>

        <section class="card">
          <h2>分片管理列表</h2>
          <div class="toolbar">
            <div class="search-box">
              <input id="docSearchKeyword" placeholder="输入关键字搜索（文件名/路径/内容/id）" />
              <button class="btn" id="docSearchBtn" type="button">搜索</button>
              <button class="btn" id="docSimilarityTestBtn" type="button">测试向量相似度(消耗Token)</button>
              <button class="btn" id="docResetSearchBtn" type="button">重置</button>
            </div>
            <div class="btn-row" style="margin-top:0;">
              <button class="btn" id="docListRefreshBtn" type="button">刷新</button>
              <button class="btn btn-danger" id="docBatchDeleteBtn" type="button">批量删除勾选</button>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th class="col-check"><input id="docSelectAllCheckbox" type="checkbox" /></th>
                <th class="col-id">ID</th>
                <th class="col-q">文件名</th>
                <th class="col-a">路径/内容</th>
                <th class="col-score">类型</th>
                <th class="col-score">相似度</th>
                <th class="col-op">操作</th>
              </tr>
            </thead>
            <tbody id="docChunkTableBody"></tbody>
          </table>
          <div class="status" id="docTableStatus"></div>
          <div class="pager">
            <button class="btn" id="docPrevPageBtn" type="button">上一页</button>
            <button class="btn" id="docNextPageBtn" type="button">下一页</button>
            <div class="pager-info" id="docPageInfo">第 1 / 1 页，共 0 条</div>
          </div>
        </section>
      </section>

      <section class="view" id="llmTemplateView">
        <section class="card">
          <h2>LLM自定义模版</h2>
          <p class="muted">模版需包含 <code>{content}</code> 占位符，接口会用用户提问替换后提交到问答模型。</p>
          <textarea id="qaTemplateEditor" placeholder="请输入LLM自定义模版"></textarea>
          <div class="btn-row">
            <button class="btn" id="reloadQaTemplateBtn" type="button">读取模版</button>
            <button class="btn" id="saveQaTemplateBtn" type="button">保存模版</button>
          </div>
          <div class="status" id="qaTemplateStatus"></div>
        </section>
        <section class="card">
          <h3 style="margin:0 0 10px;font-size:16px;">占位符说明</h3>
          <p class="muted">用户发送过来的消息=<code>{content}</code>（必填）</p>
          <p class="muted">知识库分片=<code>{fragmenteddata}</code>（非必填，留空则不匹配分片数据）</p>
        </section>
      </section>

      <section class="view" id="webReplyView">
        <section class="card">
          <h2>应答界面</h2>
          <p class="muted">前台地址：<code>/web?username=张三</code>（username 可为空）</p>

          <div class="switch-row">
            <input id="webEnabled" type="checkbox" />
            <label for="webEnabled" style="margin:0;">启用Web应答界面（关闭后 /web 不可访问）</label>
          </div>

          <label for="webChatTitle" style="margin-top:10px;">页面标题</label>
          <input id="webChatTitle" type="text" placeholder="例如：智能客服" />

          <label for="webWelcomeTemplate" style="margin-top:10px;">欢迎语模版（支持 <code>{username}</code>，可留空）</label>
          <textarea id="webWelcomeTemplate" placeholder="例如：您好{username}，欢迎咨询。"></textarea>

          <label for="webQuickPhrases" style="margin-top:10px;">快捷语（每行一条）</label>
          <textarea id="webQuickPhrases" placeholder="怎么退款&#10;多久到账&#10;客服在线时间"></textarea>

          <label for="webPreviewUsername" style="margin-top:10px;">预览用户名（可为空）</label>
          <input id="webPreviewUsername" type="text" placeholder="例如：小王" />

          <div class="btn-row">
            <button class="btn" id="reloadWebReplyBtn" type="button">读取配置</button>
            <button class="btn" id="saveWebReplyBtn" type="button">保存配置</button>
            <button class="btn" id="openWebChatBtn" type="button">打开应答界面</button>
          </div>
          <div class="status" id="webReplyStatus"></div>
        </section>
      </section>

      <section class="view" id="settingsView">
        <section class="card">
          <h2>系统设置</h2>
        </section>
        <section class="card">
          <h3 style="margin:0 0 10px;font-size:16px;">API配置</h3>
          <label for="cfgSimilarityThreshold">相似度阈值（0~1）</label>
          <input id="cfgSimilarityThreshold" type="number" min="0" max="1" step="0.01" />

          <label for="cfgMinEmbeddingChars" style="margin-top:10px;">文本最小长度（>=1）</label>
          <input id="cfgMinEmbeddingChars" type="number" min="1" step="1" />

          <label for="cfgNotConfiguredAnswer" style="margin-top:10px;">未命中时回复</label>
          <input id="cfgNotConfiguredAnswer" type="text" />

          <div class="switch-row">
            <input id="cfgAutoRetrieveKnowledge" type="checkbox" />
            <label for="cfgAutoRetrieveKnowledge" style="margin:0;">自动检索知识库,学习知识库(消耗EM的TOKEN)</label>
          </div>
          <div class="switch-row">
            <input id="cfgEnableQaModel" type="checkbox" />
            <label for="cfgEnableQaModel" style="margin:0;">调用LLM问答大模型(消耗QA的TOKEN)</label>
          </div>
          <div class="switch-row">
            <input id="cfgAutoCacheQaAnswer" type="checkbox" />
            <label for="cfgAutoCacheQaAnswer" style="margin:0;">LLM问答结果自动写入知识库(消耗EM的TOKEN;如果关闭的话，将会投入待审核)</label>
          </div>

          <div class="btn-row">
            <button class="btn" id="reloadSettingsBtn" type="button">重新读取</button>
            <button class="btn" id="saveSettingsBtn" type="button">保存配置</button>
          </div>
          <div class="status" id="settingsStatus"></div>
        </section>
        <section class="card">
          <h3 style="margin:0 0 10px;font-size:16px;">分片读取</h3>
          <label for="cfgFragmentReadSimilarityThreshold">分片相似度阈值（0~1）</label>
          <input id="cfgFragmentReadSimilarityThreshold" type="number" min="0" max="1" step="0.01" />

          <label for="cfgFragmentReadLimit" style="margin-top:10px;">分片返回条数（1~10）</label>
          <input id="cfgFragmentReadLimit" type="number" min="1" max="10" step="1" />

          <div class="btn-row">
            <button class="btn" id="reloadFragmentReadBtn" type="button">重新读取</button>
            <button class="btn" id="saveFragmentReadBtn" type="button">保存配置</button>
          </div>
          <div class="status" id="fragmentReadSettingsStatus"></div>
        </section>
      </section>
    </main>
  </div>

  <script>
    const selectedIds = new Set();
    const PAGE_SIZE = 10;
    const FAQ_COLLECTION = "__FAQ_COLLECTION__";
    const PENDING_COLLECTION = "__PENDING_COLLECTION__";
    const VIEW_STORAGE_KEY = "admin_active_view";
    const ALLOWED_VIEWS = new Set(["console", "knowledge", "docChunk", "pending", "webReply", "llmTemplate", "settings"]);
    let currentPage = 1;
    let totalPages = 0;
    let knowledgeLoaded = false;
    let settingsLoaded = false;
    let qaTemplateLoaded = false;
    let webReplyLoaded = false;
    let docChunkLoaded = false;
    let batchPreviewEntries = [];
    let docChunkImportPayload = null;
    let uploadedDocImagePath = "";
    let uploadedDocImageName = "";
    let activeKnowledgeCollection = FAQ_COLLECTION;
    const docSelectedIds = new Set();
    let docCurrentPage = 1;
    let docTotalPages = 0;

    function saveActiveView(view) {
      if (!ALLOWED_VIEWS.has(view)) return;
      try {
        localStorage.setItem(VIEW_STORAGE_KEY, view);
      } catch (_) {
      }
    }

    function getActiveView() {
      try {
        const value = localStorage.getItem(VIEW_STORAGE_KEY) || "";
        if (ALLOWED_VIEWS.has(value)) {
          return value;
        }
      } catch (_) {
      }
      return "console";
    }

    function isPendingCollection() {
      return activeKnowledgeCollection === PENDING_COLLECTION;
    }

    function updateKnowledgeModeUi() {
      const isPending = isPendingCollection();
      const title = document.getElementById("knowledgeListTitle");
      const metricHeader = document.getElementById("metricHeader");
      const operationHeader = document.getElementById("operationHeader");
      const batchDeleteBtn = document.getElementById("batchDeleteBtn");
      const singleCard = document.getElementById("singleKnowledgeCard");
      const batchCard = document.getElementById("batchImportCard");

      if (title) {
        title.textContent = isPending ? "待审核列表" : "知识列表";
      }
      if (metricHeader) {
        metricHeader.textContent = "相似度";
        metricHeader.style.display = isPending ? "none" : "";
      }
      if (operationHeader) {
        operationHeader.textContent = isPending ? "审核操作" : "操作";
      }
      if (batchDeleteBtn) {
        batchDeleteBtn.textContent = isPending ? "批量拒绝勾选" : "批量删除勾选";
      }
      if (singleCard) {
        singleCard.style.display = isPending ? "none" : "";
      }
      if (batchCard) {
        batchCard.style.display = isPending ? "none" : "";
      }
    }

    function switchView(view) {
      const safeView = ALLOWED_VIEWS.has(view) ? view : "console";
      saveActiveView(safeView);

      const consoleView = document.getElementById("consoleView");
      const knowledgeView = document.getElementById("knowledgeView");
      const docChunkView = document.getElementById("docChunkView");
      const webReplyView = document.getElementById("webReplyView");
      const llmTemplateView = document.getElementById("llmTemplateView");
      const settingsView = document.getElementById("settingsView");
      const menuConsole = document.getElementById("menuConsole");
      const menuKnowledge = document.getElementById("menuKnowledge");
      const menuDocChunk = document.getElementById("menuDocChunk");
      const menuPending = document.getElementById("menuPending");
      const menuWebReply = document.getElementById("menuWebReply");
      const menuLlmTemplate = document.getElementById("menuLlmTemplate");
      const menuSettings = document.getElementById("menuSettings");

      if (consoleView) consoleView.classList.toggle("active", safeView === "console");
      if (knowledgeView) knowledgeView.classList.toggle("active", safeView === "knowledge" || safeView === "pending");
      if (docChunkView) docChunkView.classList.toggle("active", safeView === "docChunk");
      if (webReplyView) webReplyView.classList.toggle("active", safeView === "webReply");
      if (llmTemplateView) llmTemplateView.classList.toggle("active", safeView === "llmTemplate");
      if (settingsView) settingsView.classList.toggle("active", safeView === "settings");
      if (menuConsole) menuConsole.classList.toggle("active", safeView === "console");
      if (menuKnowledge) menuKnowledge.classList.toggle("active", safeView === "knowledge");
      if (menuDocChunk) menuDocChunk.classList.toggle("active", safeView === "docChunk");
      if (menuPending) menuPending.classList.toggle("active", safeView === "pending");
      if (menuWebReply) menuWebReply.classList.toggle("active", safeView === "webReply");
      if (menuLlmTemplate) menuLlmTemplate.classList.toggle("active", safeView === "llmTemplate");
      if (menuSettings) menuSettings.classList.toggle("active", safeView === "settings");

      if (safeView === "knowledge" || safeView === "pending") {
        const nextCollection = safeView === "pending" ? PENDING_COLLECTION : FAQ_COLLECTION;
        const modeChanged = activeKnowledgeCollection !== nextCollection;
        activeKnowledgeCollection = nextCollection;
        updateKnowledgeModeUi();
        if (!knowledgeLoaded) {
          knowledgeLoaded = true;
          loadKnowledgeList(1);
        } else if (modeChanged) {
          selectedIds.clear();
          loadKnowledgeList(1);
        }
      }
      if (safeView === "docChunk" && !docChunkLoaded) {
        docChunkLoaded = true;
        loadDocChunkList(1);
      }
      if (safeView === "llmTemplate" && !qaTemplateLoaded) {
        qaTemplateLoaded = true;
        loadQaTemplate();
      }
      if (safeView === "webReply" && !webReplyLoaded) {
        webReplyLoaded = true;
        loadWebReplySettings();
      }
      if (safeView === "settings" && !settingsLoaded) {
        settingsLoaded = true;
        loadSystemSettings();
        loadFragmentReadSettings();
      }
    }

    function setStatus(id, message, ok) {
      const el = document.getElementById(id);
      el.textContent = message || "";
      el.className = "status " + (message ? (ok ? "ok" : "err") : "");
    }

    function escapeHtml(text) {
      return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function clearBatchPreview() {
      batchPreviewEntries = [];
      const box = document.getElementById("batchPreviewBox");
      const summary = document.getElementById("batchPreviewSummary");
      const errors = document.getElementById("batchErrorLines");
      if (box) box.style.display = "none";
      if (summary) summary.textContent = "";
      if (errors) errors.textContent = "";
    }

    function getBatchSourceMode() {
      const selected = document.querySelector('input[name="batchSourceMode"]:checked');
      const value = selected ? String(selected.value || "").trim() : "text";
      return value || "text";
    }

    function updateBatchSourceModeUi() {
      const mode = getBatchSourceMode();
      const textPanel = document.getElementById("batchModeTextPanel");
      const filePanel = document.getElementById("batchModeFilePanel");
      if (textPanel) textPanel.style.display = mode === "text" ? "" : "none";
      if (filePanel) filePanel.style.display = mode === "file" ? "" : "none";
      clearBatchPreview();
    }

    function updateBatchFileName() {
      const fileInput = document.getElementById("batchFileInput");
      const file = fileInput && fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
      const fileNameEl = document.getElementById("batchFileName");
      if (!fileNameEl) return;
      fileNameEl.textContent = file ? String(file.name || "").trim() : "未选择文件";
    }

    function chooseBatchFile() {
      const fileInput = document.getElementById("batchFileInput");
      if (fileInput) fileInput.click();
    }

    function renderBatchPreview(data) {
      const box = document.getElementById("batchPreviewBox");
      const summary = document.getElementById("batchPreviewSummary");
      const errorsEl = document.getElementById("batchErrorLines");
      if (!box || !summary || !errorsEl) return;

      const totalValid = Number(data.total_valid || 0);
      const totalErrors = Number(data.total_errors || 0);
      const errors = Array.isArray(data.errors) ? data.errors : [];

      summary.textContent = `预览完成：有效 ${totalValid} 条，错误 ${totalErrors} 条`;

      if (!errors.length) {
        errorsEl.textContent = "";
      } else {
        const lines = errors.map((item) => {
          const index = item.index ?? "?";
          const message = item.error ?? "解析失败";
          const raw = item.raw ? `，原始内容: ${item.raw}` : "";
          return `第${index}行: ${message}${raw}`;
        });
        errorsEl.textContent = lines.join("\\n");
      }

      box.style.display = "block";
    }

    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = String(reader.result || "");
          const marker = "base64,";
          const pos = result.indexOf(marker);
          if (pos < 0) {
            reject(new Error("文件读取失败"));
            return;
          }
          resolve(result.slice(pos + marker.length));
        };
        reader.onerror = () => reject(new Error("文件读取失败"));
        reader.readAsDataURL(file);
      });
    }

    function clearDocChunkPreview() {
      docChunkImportPayload = null;
      const box = document.getElementById("docChunkPreviewBox");
      const summary = document.getElementById("docChunkPreviewSummary");
      const sample = document.getElementById("docChunkPreviewSample");
      if (box) box.style.display = "none";
      if (summary) summary.textContent = "";
      if (sample) sample.textContent = "";
    }

    function updateDocImageUploadResult() {
      const el = document.getElementById("docImageUploadResult");
      if (!el) return;
      if (!uploadedDocImagePath) {
        el.textContent = "未上传图片";
        return;
      }
      el.textContent = `已上传：${uploadedDocImageName || "image"} -> ${uploadedDocImagePath}`;
    }

    function updateDocChunkFileName() {
      const fileInput = document.getElementById("docChunkFileInput");
      const file = fileInput && fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
      const fileNameEl = document.getElementById("docChunkFileName");
      if (!fileNameEl) return;
      fileNameEl.textContent = file ? String(file.name || "").trim() : "未选择文件";
    }

    function updateDocImageSelectedName() {
      const fileInput = document.getElementById("docImageUploadInput");
      const file = fileInput && fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
      const fileNameEl = document.getElementById("docImageSelectedName");
      if (!fileNameEl) return;
      fileNameEl.textContent = file ? String(file.name || "").trim() : "未选择图片";
    }

    function chooseDocChunkFile() {
      const fileInput = document.getElementById("docChunkFileInput");
      if (fileInput) fileInput.click();
    }

    function chooseDocChunkImage() {
      const fileInput = document.getElementById("docImageUploadInput");
      if (fileInput) fileInput.click();
    }

    function clearUploadedDocImage() {
      uploadedDocImagePath = "";
      uploadedDocImageName = "";
      const input = document.getElementById("docImageUploadInput");
      if (input) input.value = "";
      updateDocImageSelectedName();
      updateDocImageUploadResult();
      clearDocChunkPreview();
    }

    function onDocImageUploadInputChange() {
      uploadedDocImagePath = "";
      uploadedDocImageName = "";
      updateDocImageSelectedName();
      updateDocImageUploadResult();
      clearDocChunkPreview();
    }

    function getDocChunkSourceMode() {
      const selected = document.querySelector('input[name="docChunkSourceMode"]:checked');
      const value = selected ? String(selected.value || "").trim() : "file";
      return value || "file";
    }

    function getDocChunkDelimiterMode() {
      const selected = document.querySelector('input[name="docChunkDelimiterMode"]:checked');
      const value = selected ? String(selected.value || "").trim() : "newline";
      return value || "newline";
    }

    function updateDocChunkSourceModeUi() {
      const mode = getDocChunkSourceMode();
      const filePanel = document.getElementById("docChunkModeFilePanel");
      const imagePanel = document.getElementById("docChunkModeImagePanel");
      const textPanel = document.getElementById("docChunkModeTextPanel");
      if (filePanel) filePanel.style.display = mode === "file" ? "" : "none";
      if (imagePanel) imagePanel.style.display = mode === "image" ? "" : "none";
      if (textPanel) textPanel.style.display = mode === "text" ? "" : "none";
      clearDocChunkPreview();
    }

    function updateDocChunkDelimiterModeUi() {
      const mode = getDocChunkDelimiterMode();
      const panel = document.getElementById("docChunkCustomDelimiterPanel");
      if (panel) panel.style.display = mode === "custom" ? "" : "none";
      clearDocChunkPreview();
    }

    async function uploadDocImageToPicture() {
      const input = document.getElementById("docImageUploadInput");
      const file = input && input.files && input.files.length ? input.files[0] : null;
      if (!file) {
        setStatus("docChunkStatus", "请先选择图片文件", false);
        return;
      }
      const lower = String(file.name || "").toLowerCase();
      const allowed = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"];
      if (!allowed.some((suffix) => lower.endsWith(suffix))) {
        setStatus("docChunkStatus", "仅支持图片格式：png/jpg/jpeg/webp/gif/bmp/svg", false);
        return;
      }

      setStatus("docChunkStatus", "图片上传中...", true);
      try {
        const fileContentBase64 = await readFileAsBase64(file);
        const data = await apiRequest("POST", "/admin/api/docs-chunk/upload-image", {
          file_name: String(file.name || "").trim(),
          file_content_base64: fileContentBase64
        });
        if (!data) return;
        uploadedDocImagePath = String(data.file_path || "").trim();
        uploadedDocImageName = String(data.file_name || file.name || "").trim();
        if (!uploadedDocImagePath) {
          throw new Error("上传成功但未返回文件路径");
        }
        updateDocImageUploadResult();
        clearDocChunkPreview();
        setStatus("docChunkStatus", "图片上传成功", true);
      } catch (err) {
        setStatus("docChunkStatus", err.message || "图片上传失败", false);
      }
    }

    async function buildDocChunkPayload() {
      const fileInput = document.getElementById("docChunkFileInput");
      const file = fileInput && fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
      const content = document.getElementById("docChunkContent").value || "";
      const chunkSize = Number(document.getElementById("docChunkSize").value);
      const chunkOverlap = Number(document.getElementById("docChunkOverlap").value);
      const imagePath = uploadedDocImagePath;
      const sourceMode = getDocChunkSourceMode();
      const delimiterMode = getDocChunkDelimiterMode();
      const customDelimiterInput = document.getElementById("docChunkCustomDelimiter");
      const customDelimiter = customDelimiterInput ? String(customDelimiterInput.value || "") : "";

      if (!Number.isInteger(chunkSize) || chunkSize < 100 || chunkSize > 1200) {
        throw new Error("切片长度必须是 100~1200 的整数");
      }
      if (!Number.isInteger(chunkOverlap) || chunkOverlap < 0 || chunkOverlap > 300) {
        throw new Error("切片重叠必须是 0~300 的整数");
      }
      if (chunkOverlap >= chunkSize) {
        throw new Error("切片重叠必须小于切片长度");
      }

      if (sourceMode !== "image" && delimiterMode === "custom") {
        if (!customDelimiter) {
          throw new Error("请选择自定义分隔符后请填写输入内容");
        }
        if (customDelimiter.length > 20) {
          throw new Error("自定义分隔符长度不能超过20");
        }
      }

      const body = {
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        segment_delimiter_mode: delimiterMode,
        custom_delimiter: delimiterMode === "custom" ? customDelimiter : ""
      };

      if (sourceMode === "file") {
        if (!file) {
          throw new Error("请先选择文档文件");
        }
        const fileName = String(file.name || "").trim();
        const lower = fileName.toLowerCase();
        const supported = [
          ".txt",
          ".md",
          ".markdown",
          ".csv",
          ".json",
          ".jsonl",
          ".docx",
          ".xlsx"
        ];
        const isSupported = supported.some((suffix) => lower.endsWith(suffix));
        if (!isSupported) {
          throw new Error("文件模式仅支持 txt/md/csv/json/jsonl/docx/xlsx");
        }
        body.file_name = fileName;
        body.file_content_base64 = await readFileAsBase64(file);
      } else if (sourceMode === "image") {
        if (!imagePath) {
          throw new Error("请先上传图片到 /picture");
        }
        body.image_path = imagePath;
        if (uploadedDocImageName) {
          body.file_name = uploadedDocImageName;
        }
      } else if (sourceMode === "text") {
        if (!content.trim()) {
          throw new Error("请先粘贴文档内容");
        }
        body.content = content;
      } else {
        throw new Error("分割类型无效");
      }
      return body;
    }

    function renderDocChunkPreview(data) {
      const box = document.getElementById("docChunkPreviewBox");
      const summary = document.getElementById("docChunkPreviewSummary");
      const sample = document.getElementById("docChunkPreviewSample");
      if (!box || !summary || !sample) return;

      const totalChunks = Number(data.total_chunks || 0);
      const sourceChars = Number(data.source_chars || 0);
      const chunkSize = Number(data.chunk_size || 0);
      const chunkOverlap = Number(data.chunk_overlap || 0);
      if (data.is_image) {
        summary.textContent = `预览完成：图片模式，记录 ${totalChunks} 条（文件名/路径入库）`;
      } else {
        const delimiterLabel = String(data.segment_delimiter_label || "");
        const customDelimiter = String(data.custom_delimiter || "");
        const delimiterExtra = delimiterLabel
          ? `，分段分隔符=${delimiterLabel}${customDelimiter ? `（${customDelimiter}）` : ""}`
          : "";
        summary.textContent = `预览完成：文本 ${sourceChars} 字，切片 ${totalChunks} 条，chunk_size=${chunkSize}，chunk_overlap=${chunkOverlap}${delimiterExtra}`;
      }

      const previewChunks = Array.isArray(data.preview_chunks) ? data.preview_chunks : [];
      if (!previewChunks.length) {
        sample.textContent = "";
      } else {
        const lines = previewChunks.slice(0, 3).map((item) => {
          const idx = Number(item.index || 0);
          const chars = Number(item.chars || 0);
          const preview = String(item.preview || "").replace(/\s+/g, " ").trim();
          return `#${idx} (${chars}字): ${preview}`;
        });
        sample.textContent = lines.join("\\n");
      }
      box.style.display = "block";
    }

    async function previewDocChunkImport() {
      setStatus("docChunkStatus", "切片预览中...", true);
      clearDocChunkPreview();
      try {
        const payload = await buildDocChunkPayload();
        payload.max_preview = 20;
        const data = await apiRequest("POST", "/admin/api/docs-chunk/preview", payload);
        if (!data) return;
        delete payload.max_preview;
        docChunkImportPayload = payload;
        renderDocChunkPreview(data);
        setStatus("docChunkStatus", `预览完成：共 ${data.total_chunks || 0} 条切片`, true);
      } catch (err) {
        setStatus("docChunkStatus", err.message || "切片预览失败", false);
      }
    }

    async function importDocChunks() {
      if (!docChunkImportPayload) {
        setStatus("docChunkStatus", "请先执行切片预览，再确认导入", false);
        return;
      }
      const rollbackOnError = !!document.getElementById("docChunkRollbackOnError").checked;
      setStatus("docChunkStatus", "导入中...", true);
      try {
        const payload = {
          ...docChunkImportPayload,
          rollback_on_error: rollbackOnError
        };
        const data = await apiRequest("POST", "/admin/api/docs-chunk/import", payload);
        if (!data) return;
        const rolledBack = !!data.rolled_back;
        const rollbackError = String(data.rollback_error || "");
        let msg = `总切片 ${data.total_chunks}，成功 ${data.success}，失败 ${data.failed}`;
        if (rolledBack) msg += "，已回滚";
        if (rollbackError) msg += `，回滚异常：${rollbackError}`;
        setStatus("docChunkStatus", msg, data.failed === 0 || (rolledBack && !rollbackError));
        await loadDocChunkList(1);
      } catch (err) {
        setStatus("docChunkStatus", err.message || "切片导入失败", false);
      }
    }

    function updateDocSelectAllState() {
      const selectAll = document.getElementById("docSelectAllCheckbox");
      const rowChecks = Array.from(document.querySelectorAll(".doc-row-check"));
      if (!selectAll) return;
      if (!rowChecks.length) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
        return;
      }
      const checkedCount = rowChecks.filter((el) => el.checked).length;
      selectAll.checked = checkedCount === rowChecks.length;
      selectAll.indeterminate = checkedCount > 0 && checkedCount < rowChecks.length;
    }

    function updateDocPager(total, page, pages) {
      docTotalPages = pages || 0;
      docCurrentPage = page || 1;
      const prevBtn = document.getElementById("docPrevPageBtn");
      const nextBtn = document.getElementById("docNextPageBtn");
      const info = document.getElementById("docPageInfo");
      if (prevBtn) prevBtn.disabled = docCurrentPage <= 1 || docTotalPages === 0;
      if (nextBtn) nextBtn.disabled = docTotalPages === 0 || docCurrentPage >= docTotalPages;
      if (info) {
        const safeTotalPages = docTotalPages || 1;
        info.textContent = `第 ${docCurrentPage} / ${safeTotalPages} 页，共 ${total} 条`;
      }
    }

    function bindDocChunkTableActions() {
      document.querySelectorAll(".doc-row-check").forEach((el) => {
        el.addEventListener("change", () => {
          const id = decodeURIComponent(el.getAttribute("data-id") || "");
          if (!id) return;
          if (el.checked) {
            docSelectedIds.add(id);
          } else {
            docSelectedIds.delete(id);
          }
          updateDocSelectAllState();
        });
      });

      document.querySelectorAll(".doc-row-delete").forEach((el) => {
        el.addEventListener("click", () => {
          const id = decodeURIComponent(el.getAttribute("data-id") || "");
          if (!id) return;
          deleteDocChunkPoint(id);
        });
      });

      updateDocSelectAllState();
    }

    function renderDocChunkTable(items) {
      const tbody = document.getElementById("docChunkTableBody");
      if (!tbody) return;
      if (!items.length) {
        tbody.innerHTML = "<tr><td colspan='7'>暂无数据</td></tr>";
        bindDocChunkTableActions();
        return;
      }

      tbody.innerHTML = items.map((item) => {
        const id = String(item.id ?? "");
        const idAttr = encodeURIComponent(id);
        const checked = docSelectedIds.has(id) ? "checked" : "";
        const fileName = escapeHtml(item.file_name || item.doc_name || item.question || "");
        const docTypeRaw = String(item.doc_type || "").toLowerCase();
        const isImage = !!item.is_image || docTypeRaw === "image";
        const pathOrTextRaw = isImage
          ? String(item.file_path || item.answer || "")
          : String(item.answer || item.file_path || "");
        const pathOrTextDisplay = pathOrTextRaw.length > 220
          ? `${pathOrTextRaw.slice(0, 220)}...`
          : pathOrTextRaw;
        const pathOrText = escapeHtml(pathOrTextDisplay);
        const docType = escapeHtml(item.doc_type || (isImage ? "image" : "text"));
        const rawScore = Number(item.score);
        const scoreText = Number.isFinite(rawScore) ? rawScore.toFixed(6) : "-";
        return `
          <tr>
            <td><input type="checkbox" class="doc-row-check" data-id="${idAttr}" ${checked} /></td>
            <td>${escapeHtml(id)}</td>
            <td>${fileName}</td>
            <td>${pathOrText}</td>
            <td>${docType}</td>
            <td>${escapeHtml(scoreText)}</td>
            <td><button class="btn btn-danger doc-row-delete" type="button" data-id="${idAttr}">删除</button></td>
          </tr>
        `;
      }).join("");

      bindDocChunkTableActions();
    }

    async function loadDocChunkList(targetPage) {
      setStatus("docTableStatus", "加载中...", true);
      docSelectedIds.clear();
      try {
        if (typeof targetPage === "number" && targetPage > 0) {
          docCurrentPage = targetPage;
        }
        const keyword = document.getElementById("docSearchKeyword").value.trim();
        const query = new URLSearchParams({
          limit: String(PAGE_SIZE),
          page: String(docCurrentPage),
          collection: "__DOCS_COLLECTION__"
        });
        if (keyword) query.set("keyword", keyword);
        const data = await apiRequest("GET", `/admin/api/knowledge?${query.toString()}`);
        if (!data) return;
        const items = data.items || [];
        const total = Number(data.total || 0);
        const pages = Number(data.total_pages || 0);
        if (pages > 0 && docCurrentPage > pages) {
          return loadDocChunkList(pages);
        }
        renderDocChunkTable(items);
        updateDocPager(total, Number(data.page || docCurrentPage), pages);
        const title = keyword
          ? `分片搜索结果 ${total} 条，本页 ${items.length} 条`
          : `分片共 ${total} 条，本页 ${items.length} 条`;
        setStatus("docTableStatus", title, true);
      } catch (err) {
        setStatus("docTableStatus", err.message || "加载失败", false);
      }
    }

    async function testDocChunkSimilarity() {
      const keyword = document.getElementById("docSearchKeyword").value.trim();
      if (!keyword) {
        setStatus("docTableStatus", "请先输入搜索内容", false);
        return;
      }

      setStatus("docTableStatus", "向量相似度测试中...(消耗Token)", true);
      docSelectedIds.clear();
      try {
        const query = new URLSearchParams({
          content: keyword
        });
        const data = await apiRequest("GET", `/admin/api/docs-chunk/similarity?${query.toString()}`);
        if (!data) return;
        const items = data.items || [];
        const total = Number(data.total || items.length || 0);
        const usedThreshold = Number(data.similarity_threshold);
        const usedLimit = Number(data.limit);
        renderDocChunkTable(items);
        updateDocPager(total, 1, 1);
        const thresholdText = Number.isFinite(usedThreshold) ? usedThreshold : "-";
        const limitText = Number.isFinite(usedLimit) ? usedLimit : "-";
        setStatus("docTableStatus", `向量相似度测试完成：命中 ${items.length} 条（阈值 ${thresholdText}，条数 ${limitText}）`, true);
      } catch (err) {
        setStatus("docTableStatus", err.message || "向量相似度测试失败", false);
      }
    }

    async function deleteDocChunkPoint(id) {
      if (!confirm(`确认删除分片 ID=${id} ?`)) return;
      try {
        const query = new URLSearchParams({ collection: "__DOCS_COLLECTION__" });
        await apiRequest("DELETE", `/admin/api/knowledge/${encodeURIComponent(id)}?${query.toString()}`);
        docSelectedIds.delete(id);
        await loadDocChunkList(docCurrentPage);
      } catch (err) {
        setStatus("docTableStatus", err.message || "删除失败", false);
      }
    }

    async function batchDeleteDocChunkSelected() {
      if (docSelectedIds.size === 0) {
        setStatus("docTableStatus", "请先勾选要删除的分片记录", false);
        return;
      }
      const ids = Array.from(docSelectedIds);
      if (!confirm(`确认批量删除 ${ids.length} 条分片记录？`)) return;
      try {
        const query = new URLSearchParams({ collection: "__DOCS_COLLECTION__" });
        const data = await apiRequest("POST", `/admin/api/knowledge/batch-delete?${query.toString()}`, { ids });
        if (!data) return;
        setStatus("docTableStatus", `批量删除成功：${data.deleted_count} 条`, true);
        await loadDocChunkList(docCurrentPage);
      } catch (err) {
        setStatus("docTableStatus", err.message || "批量删除失败", false);
      }
    }

    async function apiRequest(method, url, body) {
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined
      });
      if (res.status === 401) {
        location.href = "/admin";
        return null;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "请求失败");
      }
      return data;
    }

    function updateSelectAllState() {
      const selectAll = document.getElementById("selectAllCheckbox");
      const rowChecks = Array.from(document.querySelectorAll(".row-check"));
      if (!selectAll) return;
      if (!rowChecks.length) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
        return;
      }
      const checkedCount = rowChecks.filter((el) => el.checked).length;
      selectAll.checked = checkedCount === rowChecks.length;
      selectAll.indeterminate = checkedCount > 0 && checkedCount < rowChecks.length;
    }

    function updatePager(total, page, pages) {
      totalPages = pages || 0;
      currentPage = page || 1;
      const prevBtn = document.getElementById("prevPageBtn");
      const nextBtn = document.getElementById("nextPageBtn");
      const info = document.getElementById("pageInfo");
      if (prevBtn) prevBtn.disabled = currentPage <= 1 || totalPages === 0;
      if (nextBtn) nextBtn.disabled = totalPages === 0 || currentPage >= totalPages;
      if (info) {
        const safeTotalPages = totalPages || 1;
        info.textContent = `第 ${currentPage} / ${safeTotalPages} 页，共 ${total} 条`;
      }
    }

    function bindTableActions() {
      document.querySelectorAll(".row-check").forEach((el) => {
        el.addEventListener("change", () => {
          const id = decodeURIComponent(el.getAttribute("data-id") || "");
          if (!id) return;
          if (el.checked) {
            selectedIds.add(id);
          } else {
            selectedIds.delete(id);
          }
          updateSelectAllState();
        });
      });

      document.querySelectorAll(".row-delete").forEach((el) => {
        el.addEventListener("click", () => {
          const id = decodeURIComponent(el.getAttribute("data-id") || "");
          if (!id) return;
          deletePoint(id);
        });
      });

      document.querySelectorAll(".row-approve").forEach((el) => {
        el.addEventListener("click", () => {
          const id = decodeURIComponent(el.getAttribute("data-id") || "");
          if (!id) return;
          approvePendingPoint(id);
        });
      });

      updateSelectAllState();
    }

    function renderTable(items) {
      const tbody = document.getElementById("knowledgeTableBody");
      const pendingMode = isPendingCollection();
      if (!items.length) {
        const colspan = pendingMode ? 5 : 6;
        tbody.innerHTML = `<tr><td colspan='${colspan}'>暂无数据</td></tr>`;
        bindTableActions();
        return;
      }

      tbody.innerHTML = items.map((item) => {
        const id = String(item.id ?? "");
        const idAttr = encodeURIComponent(id);
        const checked = selectedIds.has(id) ? "checked" : "";
        const question = escapeHtml(item.question ?? "");
        const answer = escapeHtml(item.answer ?? "");
        const metricCell = pendingMode
          ? ""
          : `<td class="metric-cell">${escapeHtml(item.cached_from_score ?? 1)}</td>`;
        const operationHtml = pendingMode
          ? `<div class="row-actions">
              <button class="btn row-approve" type="button" data-id="${idAttr}">通过</button>
              <button class="btn btn-danger row-delete" type="button" data-id="${idAttr}">拒绝</button>
            </div>`
          : `<button class="btn btn-danger row-delete" type="button" data-id="${idAttr}">删除</button>`;
        return `
          <tr>
            <td><input type="checkbox" class="row-check" data-id="${idAttr}" ${checked} /></td>
            <td>${escapeHtml(id)}</td>
            <td>${question}</td>
            <td>${answer}</td>
            ${metricCell}
            <td>${operationHtml}</td>
          </tr>
        `;
      }).join("");

      bindTableActions();
    }

    async function loadKnowledgeList(targetPage) {
      setStatus("tableStatus", "加载中...", true);
      selectedIds.clear();
      try {
        if (typeof targetPage === "number" && targetPage > 0) {
          currentPage = targetPage;
        }
        const keyword = document.getElementById("searchKeyword").value.trim();
        const query = new URLSearchParams({
          limit: String(PAGE_SIZE),
          page: String(currentPage),
          collection: activeKnowledgeCollection
        });
        if (keyword) query.set("keyword", keyword);
        const data = await apiRequest("GET", `/admin/api/knowledge?${query.toString()}`);
        if (!data) return;
        const items = data.items || [];
        const total = Number(data.total || 0);
        const pages = Number(data.total_pages || 0);
        if (pages > 0 && currentPage > pages) {
          return loadKnowledgeList(pages);
        }
        renderTable(items);
        updatePager(total, Number(data.page || currentPage), pages);
        const modeName = isPendingCollection() ? "待审核" : "知识库";
        const title = keyword
          ? `${modeName}搜索结果 ${total} 条，本页 ${items.length} 条`
          : `${modeName}共 ${total} 条，本页 ${items.length} 条`;
        setStatus("tableStatus", title, true);
      } catch (err) {
        setStatus("tableStatus", err.message || "加载失败", false);
      }
    }

    async function loadSystemSettings() {
      setStatus("settingsStatus", "读取配置中...", true);
      try {
        const data = await apiRequest("GET", "/admin/api/settings/app");
        if (!data) return;
        const api = data.api || {};
        document.getElementById("cfgSimilarityThreshold").value = String(api.similarity_threshold ?? "");
        document.getElementById("cfgMinEmbeddingChars").value = String(api.min_embedding_chars ?? "");
        document.getElementById("cfgNotConfiguredAnswer").value = String(api.not_configured_answer ?? "");
        document.getElementById("cfgAutoRetrieveKnowledge").checked = !!api.auto_retrieve_knowledge;
        document.getElementById("cfgEnableQaModel").checked = !!api.enable_qa_model;
        document.getElementById("cfgAutoCacheQaAnswer").checked = !!api.auto_cache_qa_answer;
        setStatus("settingsStatus", "配置读取成功", true);
      } catch (err) {
        setStatus("settingsStatus", err.message || "读取配置失败", false);
      }
    }

    async function loadFragmentReadSettings() {
      setStatus("fragmentReadSettingsStatus", "读取配置中...", true);
      try {
        const data = await apiRequest("GET", "/admin/api/settings/fragment-read");
        if (!data) return;
        const fragmentRead = data.fragment_read || {};
        document.getElementById("cfgFragmentReadSimilarityThreshold").value = String(fragmentRead.similarity_threshold ?? "");
        document.getElementById("cfgFragmentReadLimit").value = String(fragmentRead.limit ?? "");
        setStatus("fragmentReadSettingsStatus", "配置读取成功", true);
      } catch (err) {
        setStatus("fragmentReadSettingsStatus", err.message || "读取配置失败", false);
      }
    }

    async function loadQaTemplate() {
      setStatus("qaTemplateStatus", "读取模版中...", true);
      try {
        const data = await apiRequest("GET", "/admin/api/settings/qa-template");
        if (!data) return;
        document.getElementById("qaTemplateEditor").value = String(data.qa_prompt_template ?? "");
        setStatus("qaTemplateStatus", "模版读取成功", true);
      } catch (err) {
        setStatus("qaTemplateStatus", err.message || "读取模版失败", false);
      }
    }

    async function saveQaTemplate() {
      const template = document.getElementById("qaTemplateEditor").value.trim();
      if (!template) {
        setStatus("qaTemplateStatus", "LLM自定义模版不能为空", false);
        return;
      }
      if (!template.includes("{content}")) {
        setStatus("qaTemplateStatus", "模版必须包含 {content} 占位符", false);
        return;
      }
      setStatus("qaTemplateStatus", "保存中...", true);
      try {
        await apiRequest("POST", "/admin/api/settings/qa-template", {
          qa_prompt_template: template
        });
        setStatus("qaTemplateStatus", "模版保存成功", true);
      } catch (err) {
        setStatus("qaTemplateStatus", err.message || "保存模版失败", false);
      }
    }

    async function loadWebReplySettings() {
      setStatus("webReplyStatus", "读取配置中...", true);
      try {
        const data = await apiRequest("GET", "/admin/api/settings/web-chat");
        if (!data) return;
        const web = data.web || {};
        document.getElementById("webEnabled").checked = !!web.enabled;
        document.getElementById("webChatTitle").value = String(web.chat_title ?? "");
        document.getElementById("webWelcomeTemplate").value = String(web.welcome_template ?? "");
        const quickPhrases = Array.isArray(web.quick_phrases) ? web.quick_phrases : [];
        document.getElementById("webQuickPhrases").value = quickPhrases
          .map((item) => String(item || "").trim())
          .filter((item) => !!item)
          .join("\\n");
        setStatus("webReplyStatus", "配置读取成功", true);
      } catch (err) {
        setStatus("webReplyStatus", err.message || "读取配置失败", false);
      }
    }

    async function saveWebReplySettings() {
      const enabled = !!document.getElementById("webEnabled").checked;
      const chatTitle = document.getElementById("webChatTitle").value.trim();
      const welcomeTemplate = document.getElementById("webWelcomeTemplate").value.trim();
      const quickPhraseText = document.getElementById("webQuickPhrases").value || "";
      const quickPhrases = quickPhraseText
        .split(/\\r?\\n/)
        .map((item) => item.trim())
        .filter((item) => !!item);
      if (!chatTitle) {
        setStatus("webReplyStatus", "页面标题不能为空", false);
        return;
      }

      setStatus("webReplyStatus", "保存中...", true);
      try {
        await apiRequest("POST", "/admin/api/settings/web-chat", {
          enabled: enabled,
          chat_title: chatTitle,
          welcome_template: welcomeTemplate,
          quick_phrases: quickPhrases
        });
        setStatus("webReplyStatus", "保存成功", true);
      } catch (err) {
        setStatus("webReplyStatus", err.message || "保存失败", false);
      }
    }

    function openWebChatPage() {
      const username = document.getElementById("webPreviewUsername").value.trim();
      const url = username ? `/web?username=${encodeURIComponent(username)}` : "/web";
      window.open(url, "_blank");
    }

    async function saveSystemSettings() {
      const similarityThreshold = Number(document.getElementById("cfgSimilarityThreshold").value);
      const minEmbeddingChars = Number(document.getElementById("cfgMinEmbeddingChars").value);
      const notConfiguredAnswer = document.getElementById("cfgNotConfiguredAnswer").value.trim();
      const autoRetrieveKnowledge = !!document.getElementById("cfgAutoRetrieveKnowledge").checked;
      const enableQaModel = !!document.getElementById("cfgEnableQaModel").checked;
      const autoCacheQaAnswer = !!document.getElementById("cfgAutoCacheQaAnswer").checked;

      if (Number.isNaN(similarityThreshold) || similarityThreshold < 0 || similarityThreshold > 1) {
        setStatus("settingsStatus", "similarity_threshold 必须在 0~1 之间", false);
        return;
      }
      if (!Number.isInteger(minEmbeddingChars) || minEmbeddingChars < 1) {
        setStatus("settingsStatus", "min_embedding_chars 必须是 >=1 的整数", false);
        return;
      }
      if (!notConfiguredAnswer) {
        setStatus("settingsStatus", "not_configured_answer 不能为空", false);
        return;
      }

      setStatus("settingsStatus", "保存中...", true);
      try {
        await apiRequest("POST", "/admin/api/settings/app", {
          similarity_threshold: similarityThreshold,
          min_embedding_chars: minEmbeddingChars,
          not_configured_answer: notConfiguredAnswer,
          auto_retrieve_knowledge: autoRetrieveKnowledge,
          enable_qa_model: enableQaModel,
          auto_cache_qa_answer: autoCacheQaAnswer
        });
        setStatus("settingsStatus", "保存成功", true);
        await loadSystemSettings();
      } catch (err) {
        setStatus("settingsStatus", err.message || "保存失败", false);
      }
    }

    async function saveFragmentReadSettings() {
      const similarityThreshold = Number(document.getElementById("cfgFragmentReadSimilarityThreshold").value);
      const limit = Number(document.getElementById("cfgFragmentReadLimit").value);
      if (Number.isNaN(similarityThreshold) || similarityThreshold < 0 || similarityThreshold > 1) {
        setStatus("fragmentReadSettingsStatus", "similarity_threshold 必须在 0~1 之间", false);
        return;
      }
      if (!Number.isInteger(limit) || limit < 1 || limit > 10) {
        setStatus("fragmentReadSettingsStatus", "limit 必须是 1~10 的整数", false);
        return;
      }

      setStatus("fragmentReadSettingsStatus", "保存中...", true);
      try {
        await apiRequest("POST", "/admin/api/settings/fragment-read", {
          similarity_threshold: similarityThreshold,
          limit: limit
        });
        setStatus("fragmentReadSettingsStatus", "保存成功", true);
        await loadFragmentReadSettings();
      } catch (err) {
        setStatus("fragmentReadSettingsStatus", err.message || "保存失败", false);
      }
    }

    async function addSingle() {
      const question = document.getElementById("singleQuestion").value.trim();
      const answer = document.getElementById("singleAnswer").value.trim();
      if (!question || !answer) {
        setStatus("singleStatus", "问题和答案不能为空", false);
        return;
      }
      setStatus("singleStatus", "提交中...", true);
      try {
        await apiRequest("POST", "/admin/api/knowledge", { question, answer });
        document.getElementById("singleQuestion").value = "";
        document.getElementById("singleAnswer").value = "";
        setStatus("singleStatus", "新增成功", true);
        await loadKnowledgeList();
      } catch (err) {
        setStatus("singleStatus", err.message || "新增失败", false);
      }
    }

    async function deletePoint(id) {
      const actionText = isPendingCollection() ? "拒绝并删除" : "删除";
      if (!confirm(`确认${actionText} ID=${id} ?`)) return;
      try {
        const query = new URLSearchParams({ collection: activeKnowledgeCollection });
        await apiRequest("DELETE", `/admin/api/knowledge/${encodeURIComponent(id)}?${query.toString()}`);
        selectedIds.delete(id);
        await loadKnowledgeList();
      } catch (err) {
        setStatus("tableStatus", err.message || "删除失败", false);
      }
    }

    async function approvePendingPoint(id) {
      if (!confirm(`确认通过待审核记录 ID=${id} 并写入知识库？`)) return;
      try {
        const data = await apiRequest("POST", `/admin/api/pending/${encodeURIComponent(id)}/approve`);
        if (!data) return;
        const warning = String(data.delete_warning || "");
        const msg = warning
          ? `通过成功，但清理待审核记录失败：${warning}`
          : "通过成功，已写入知识库";
        setStatus("tableStatus", msg, !warning);
        selectedIds.delete(id);
        await loadKnowledgeList();
      } catch (err) {
        setStatus("tableStatus", err.message || "通过失败", false);
      }
    }

    async function batchDeleteSelected() {
      if (selectedIds.size === 0) {
        setStatus("tableStatus", "请先勾选要处理的记录", false);
        return;
      }
      const ids = Array.from(selectedIds);
      const actionText = isPendingCollection() ? "批量拒绝并删除" : "批量删除";
      if (!confirm(`确认${actionText} ${ids.length} 条记录？`)) return;
      try {
        const query = new URLSearchParams({ collection: activeKnowledgeCollection });
        const data = await apiRequest("POST", `/admin/api/knowledge/batch-delete?${query.toString()}`, { ids });
        if (!data) return;
        setStatus("tableStatus", `${actionText}成功：${data.deleted_count} 条`, true);
        await loadKnowledgeList();
      } catch (err) {
        setStatus("tableStatus", err.message || `${actionText}失败`, false);
      }
    }

    async function previewBatchImport() {
      const content = document.getElementById("batchContent").value || "";
      const fileInput = document.getElementById("batchFileInput");
      const file = fileInput && fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
      const sourceMode = getBatchSourceMode();

      setStatus("batchStatus", "预览中...", true);
      clearBatchPreview();
      try {
        const body = { max_preview: 30 };
        if (sourceMode === "file") {
          if (!file) {
            setStatus("batchStatus", "请先选择xlsx/txt文件", false);
            return;
          }
          const fileName = String(file.name || "").trim();
          const lower = fileName.toLowerCase();
          if (!(lower.endsWith(".xlsx") || lower.endsWith(".txt"))) {
            setStatus("batchStatus", "仅支持 .xlsx 和 .txt 文件", false);
            return;
          }
          body.file_name = fileName;
          body.file_content_base64 = await readFileAsBase64(file);
        } else {
          if (!content.trim()) {
            setStatus("batchStatus", "请先粘贴批量内容", false);
            return;
          }
          body.content = content;
        }

        const data = await apiRequest("POST", "/admin/api/knowledge/batch/preview", body);
        if (!data) return;
        batchPreviewEntries = Array.isArray(data.entries) ? data.entries : [];
        renderBatchPreview(data);
        setStatus(
          "batchStatus",
          `预览完成：有效 ${data.total_valid || 0} 条，错误 ${data.total_errors || 0} 条`,
          Number(data.total_errors || 0) === 0
        );
      } catch (err) {
        setStatus("batchStatus", err.message || "导入预览失败", false);
      }
    }

    async function batchImport() {
      if (!batchPreviewEntries.length) {
        setStatus("batchStatus", "请先执行导入预览，确认后再导入", false);
        return;
      }

      const rollbackOnError = !!document.getElementById("batchRollbackOnError").checked;
      setStatus("batchStatus", "导入中...", true);
      try {
        const data = await apiRequest("POST", "/admin/api/knowledge/batch/import", {
          entries: batchPreviewEntries,
          rollback_on_error: rollbackOnError
        });
        if (!data) return;
        const rolledBack = !!data.rolled_back;
        const rollbackError = String(data.rollback_error || "");
        let msg = `总计 ${data.total}，成功 ${data.success}，失败 ${data.failed}`;
        if (rolledBack) msg += "，已回滚";
        if (rollbackError) msg += `，回滚异常：${rollbackError}`;
        setStatus("batchStatus", msg, data.failed === 0 || (rolledBack && !rollbackError));
        await loadKnowledgeList();
      } catch (err) {
        setStatus("batchStatus", err.message || "批量导入失败", false);
      }
    }

    async function logout() {
      try {
        await apiRequest("POST", "/admin/logout");
      } catch (_) {
      }
      location.href = "/admin";
    }

    document.getElementById("addBtn").addEventListener("click", addSingle);
    document.getElementById("previewBatchBtn").addEventListener("click", previewBatchImport);
    document.getElementById("batchBtn").addEventListener("click", batchImport);
    document.getElementById("batchPickFileBtn").addEventListener("click", chooseBatchFile);
    document.getElementById("batchFileInput").addEventListener("change", () => {
      updateBatchFileName();
      clearBatchPreview();
    });
    document.querySelectorAll('input[name="batchSourceMode"]').forEach((el) => {
      el.addEventListener("change", updateBatchSourceModeUi);
    });
    document.getElementById("batchContent").addEventListener("input", clearBatchPreview);
    document.getElementById("menuConsole").addEventListener("click", () => switchView("console"));
    document.getElementById("menuKnowledge").addEventListener("click", () => switchView("knowledge"));
    document.getElementById("menuDocChunk").addEventListener("click", () => switchView("docChunk"));
    document.getElementById("menuPending").addEventListener("click", () => switchView("pending"));
    document.getElementById("menuWebReply").addEventListener("click", () => switchView("webReply"));
    document.getElementById("menuLlmTemplate").addEventListener("click", () => switchView("llmTemplate"));
    document.getElementById("menuSettings").addEventListener("click", () => switchView("settings"));
    document.getElementById("reloadSettingsBtn").addEventListener("click", loadSystemSettings);
    document.getElementById("saveSettingsBtn").addEventListener("click", saveSystemSettings);
    document.getElementById("reloadFragmentReadBtn").addEventListener("click", loadFragmentReadSettings);
    document.getElementById("saveFragmentReadBtn").addEventListener("click", saveFragmentReadSettings);
    document.getElementById("reloadQaTemplateBtn").addEventListener("click", loadQaTemplate);
    document.getElementById("saveQaTemplateBtn").addEventListener("click", saveQaTemplate);
    document.getElementById("reloadWebReplyBtn").addEventListener("click", loadWebReplySettings);
    document.getElementById("saveWebReplyBtn").addEventListener("click", saveWebReplySettings);
    document.getElementById("openWebChatBtn").addEventListener("click", openWebChatPage);
    document.getElementById("previewDocChunkBtn").addEventListener("click", previewDocChunkImport);
    document.getElementById("importDocChunkBtn").addEventListener("click", importDocChunks);
    document.getElementById("docChunkPickFileBtn").addEventListener("click", chooseDocChunkFile);
    document.getElementById("docChunkPickImageBtn").addEventListener("click", chooseDocChunkImage);
    document.getElementById("docChunkFileInput").addEventListener("change", () => {
      updateDocChunkFileName();
      clearDocChunkPreview();
    });
    document.querySelectorAll('input[name="docChunkSourceMode"]').forEach((el) => {
      el.addEventListener("change", updateDocChunkSourceModeUi);
    });
    document.querySelectorAll('input[name="docChunkDelimiterMode"]').forEach((el) => {
      el.addEventListener("change", updateDocChunkDelimiterModeUi);
    });
    document.getElementById("docImageUploadInput").addEventListener("change", onDocImageUploadInputChange);
    document.getElementById("uploadDocImageBtn").addEventListener("click", uploadDocImageToPicture);
    document.getElementById("clearUploadedDocImageBtn").addEventListener("click", clearUploadedDocImage);
    document.getElementById("docChunkContent").addEventListener("input", clearDocChunkPreview);
    document.getElementById("docChunkSize").addEventListener("input", clearDocChunkPreview);
    document.getElementById("docChunkOverlap").addEventListener("input", clearDocChunkPreview);
    document.getElementById("docChunkCustomDelimiter").addEventListener("input", clearDocChunkPreview);
    document.getElementById("docListRefreshBtn").addEventListener("click", () => loadDocChunkList(docCurrentPage));
    document.getElementById("docSearchBtn").addEventListener("click", () => loadDocChunkList(1));
    document.getElementById("docSimilarityTestBtn").addEventListener("click", testDocChunkSimilarity);
    document.getElementById("docResetSearchBtn").addEventListener("click", () => {
      document.getElementById("docSearchKeyword").value = "";
      loadDocChunkList(1);
    });
    document.getElementById("docBatchDeleteBtn").addEventListener("click", batchDeleteDocChunkSelected);
    document.getElementById("docSearchKeyword").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        loadDocChunkList(1);
      }
    });
    document.getElementById("docPrevPageBtn").addEventListener("click", () => {
      if (docCurrentPage > 1) loadDocChunkList(docCurrentPage - 1);
    });
    document.getElementById("docNextPageBtn").addEventListener("click", () => {
      if (docTotalPages === 0 || docCurrentPage >= docTotalPages) return;
      loadDocChunkList(docCurrentPage + 1);
    });
    document.getElementById("docSelectAllCheckbox").addEventListener("change", (e) => {
      const checked = !!e.target.checked;
      document.querySelectorAll(".doc-row-check").forEach((el) => {
        el.checked = checked;
        const id = decodeURIComponent(el.getAttribute("data-id") || "");
        if (!id) return;
        if (checked) {
          docSelectedIds.add(id);
        } else {
          docSelectedIds.delete(id);
        }
      });
      updateDocSelectAllState();
    });
    document.getElementById("logoutBtn").addEventListener("click", logout);
    document.getElementById("listRefreshBtn").addEventListener("click", () => loadKnowledgeList(currentPage));
    document.getElementById("searchBtn").addEventListener("click", () => loadKnowledgeList(1));
    document.getElementById("resetSearchBtn").addEventListener("click", () => {
      document.getElementById("searchKeyword").value = "";
      loadKnowledgeList(1);
    });
    document.getElementById("batchDeleteBtn").addEventListener("click", batchDeleteSelected);
    document.getElementById("searchKeyword").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        loadKnowledgeList(1);
      }
    });
    document.getElementById("prevPageBtn").addEventListener("click", () => {
      if (currentPage > 1) loadKnowledgeList(currentPage - 1);
    });
    document.getElementById("nextPageBtn").addEventListener("click", () => {
      if (totalPages === 0 || currentPage >= totalPages) return;
      loadKnowledgeList(currentPage + 1);
    });
    document.getElementById("selectAllCheckbox").addEventListener("change", (e) => {
      const checked = !!e.target.checked;
      document.querySelectorAll(".row-check").forEach((el) => {
        el.checked = checked;
        const id = decodeURIComponent(el.getAttribute("data-id") || "");
        if (!id) return;
        if (checked) {
          selectedIds.add(id);
        } else {
          selectedIds.delete(id);
        }
      });
      updateSelectAllState();
    });

    updateBatchFileName();
    updateBatchSourceModeUi();
    updateDocChunkFileName();
    updateDocImageSelectedName();
    updateDocImageUploadResult();
    updateDocChunkSourceModeUi();
    updateDocChunkDelimiterModeUi();
    switchView(getActiveView());
  </script>
</body>
</html>
"""
    return (
        html_text.replace("__MIN_EMBEDDING_CHARS__", escape(str(min_embedding_chars)))
        .replace("__SIMILARITY_THRESHOLD__", escape(_format_float(similarity_threshold)))
        .replace("__NOT_CONFIGURED_ANSWER__", escape(not_configured_answer))
        .replace("__FAQ_COLLECTION__", escape(faq_collection))
        .replace("__PENDING_COLLECTION__", escape(pending_collection))
        .replace("__DOCS_COLLECTION__", escape(docs_collection))
    )
