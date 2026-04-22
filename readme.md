## 项目说明  AI AnswerDesk（AI 应答台）
* 这是一个基于 `Python + FastAPI + Qdrant` 的 AI客服系统，检索增强客服（RAG-like）
* 支持“手动导入知识库或者自主学习 + 检索 + 问答模型兜底”。
* 对外接口：`GET /api/?content=...`，用于客服问答。
* 前台应答界面：`GET /web?username=...`，用于客服聊天展示（username 可为空）。
* 后台入口：`GET /admin`，用于知识库和系统配置管理。
* ========================================================
* 核心检索增强流程：
* 先做关键词归一化命中（快、成本低）。
* 未命中时按配置走向量检索（Embedding + Qdrant）。
* 仍未命中时按配置走 LLM 问答或直接返回兜底答案。
* ========================================================
* 自动学习能力：
* 向量命中后可回写当前问法，提升下次命中率。
* LLM 回复后可通过 `auto_cache_qa_answer` 控制是否自动写入知识库。
* 可观测性：
* 每次 `/api/` 请求都会记录命中链路日志（步骤、分数、耗时、来源）。
* 日志按天落盘到 `logs/YYYYMMDD.log`。
* ========================================================
* 后台能力：
* 知识库列表、搜索、新增、删除、批量新增、批量删除。
* LLM 模版独立管理（支持 `{content}` 占位符）。
* 系统参数在线修改并实时生效（无需重启）。
* 主要目录：
* `api/`：客服接口、检索、Embedding、问答、日志链路
* `admin/`：后台页面与管理接口
* `config/`：系统配置与读取逻辑
* `web/`：前台应答界面与其配置读写逻辑


## python 
* python > 3.10
* python -m venv venv 创建虚拟环境
* source venv/bin/activate 进入 venv 再启动。
* pip install fastapi uvicorn langgraph langchain openai 安装依赖
* 配置文件：`config/app.json`
* 模型使用 Embedding + Qa
* 阿里云百炼官网 https://bailian.console.aliyun.com/
* 设置key（当前终端有效）：`export DASHSCOPE_API_KEY='你的key'`
* 删除key：`unset DASHSCOPE_API_KEY`
* 测试环境：uvicorn main:app --reload 启动服务
* 生产环境：uvicorn main:app --host 0.0.0.0 --port 8000 


## 接口：FAQ查询（`@router.get("/api/")`）
* 路径：`GET /api/`
* 参数：
* `content`（必填）：用户提问内容
* 仅返回 1 条最高分结果

curl "http://127.0.0.1:8000/api/?content=怎么退款"

### 返回结构说明
* 当前接口统一返回 3 个主字段：
* `content`：原始提问
* `vector_hit`：是否走了向量检索；`false` 表示走了 embedding，`true` 表示未走 embedding（例如关键词命中或短文本直接返回）
* `answer`：最终回复文案

示例：
```json
{
  "content": "怎么退款",
  "vector_hit": true,
  "answer": "退款需要9个工作日"
}
```

## 后台管理（`/admin`）
* 入口：`GET /admin`
* 登录方式：固定密码登录（配置项：`config/app.json -> admin.password`）
* 后台代码目录：`admin/`（登录、页面、知识库管理接口都在此目录）
* 布局：左侧菜单栏（控制台、知识库列表、知识库待审核、应答界面、LLM模版、系统设置）+ 右侧内容区

后台功能：
* 读取向量库列表（分页）：`GET /admin/api/knowledge?limit=10&page=1&collection=faq`
* 切换读取待审核列表：`GET /admin/api/knowledge?limit=10&page=1&collection=pending_kb`
* 搜索知识：`GET /admin/api/knowledge?keyword=退款&collection=faq`
* 新增单条知识：`POST /admin/api/knowledge`
* 删除知识：`DELETE /admin/api/knowledge/{point_id}?collection=faq`
* 拒绝待审核（删除）：`DELETE /admin/api/knowledge/{point_id}?collection=pending_kb`
* 批量删除：`POST /admin/api/knowledge/batch-delete?collection=faq`
* 批量拒绝待审核：`POST /admin/api/knowledge/batch-delete?collection=pending_kb`
* 批量新增：`POST /admin/api/knowledge/batch`
* 批量导入预览（xlsx/txt）：`POST /admin/api/knowledge/batch/preview`
* 批量确认导入（支持出错回滚）：`POST /admin/api/knowledge/batch/import`
* 通过待审核并写入知识库：`POST /admin/api/pending/{point_id}/approve`
* 独立菜单“LLM模版”中编辑 LLM 自定义模版（包含 `{content}` 占位符）
* 读取系统设置：`GET /admin/api/settings/app`
* 保存系统设置：`POST /admin/api/settings/app`
* 读取 LLM 模版：`GET /admin/api/settings/qa-template`
* 保存 LLM 模版：`POST /admin/api/settings/qa-template`
* 读取应答界面配置：`GET /admin/api/settings/web-chat`
* 保存应答界面配置（含 `enabled` 开关、欢迎语 `{username}`、快捷语）：`POST /admin/api/settings/web-chat`

## 前台应答界面（`/web`）
* 入口：`GET /web`
* 开关：`config/app.json -> web.enabled`（`true` 启用，`false` 关闭）
* 用户名参数：`GET /web?username=张三`
* 发送逻辑：页面会请求 `GET /api/?content=...`
* 每次进入/刷新页面都会推送欢迎语：读取 `config/app.json -> web.welcome_template`，支持 `{username}` 占位符
* 当欢迎语为空时，不推送欢迎消息
* 快捷语读取 `config/app.json -> web.quick_phrases`（后台“应答界面”可直接设置）

## 向量库说明（Qdrant）
* 安装向量库说明（Qdrant）
* docker run -d \
  --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
* 服务地址：`http://127.0.0.1:6333`
* 后台地址：`http://127.0.0.1:6333/dashboard`
* 知识库集合名（表名）：`faq`（来自 `config/app.json` 的 `qdrant.collection`）
* 审核知识库集合名（表名）：`pending_kb`（来自 `config/app.json` 的 `qdrant.pending_collection`）
* http://127.0.0.1:6333/dashboard#/console  执行创建集合
```json
PUT /collections/faq
{
  "vectors": {
    "size": 1024,
    "distance": "Cosine"
  }
}

PUT /collections/pending_kb
{
  "vectors": {
    "size": 1024,
    "distance": "Cosine"
  }
}
```
Point 通用结构：
```json
{
  "id": "uuid字符串",
  "vector": [0.123, -0.456, "..."],
  "payload": {
    "question": "原始问题",
    "normalized_question": "归一化后的问题",
    "answer": "答案"
  }
}
```

embedding 回写缓存 Point（比主知识多以下字段）：
* `cache_type`: 固定 `embedding_fallback`
* `cached_from_id`: 来源点 id
* `cached_from_score`: 当次命中分数
