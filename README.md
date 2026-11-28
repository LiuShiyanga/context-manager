# Context Manager Demo

一个本地上下文管理工作台：选择固定合成会话，整理目标/约束/决定/待办，按预算构建上下文，查看消息分区、来源摘要及可取回的工具 artifact。固定样本包括 80 轮对话和 10 道评测题。

默认使用 deterministic mock，不访问外部服务；在本地 `.env` 设置 `PROVIDER=anthropic` 和 `ANTHROPIC_API_KEY` 后，可启用真实 Anthropic Provider。密钥仅由后端读取，`.env` 已被 Git 忽略；usage 日志只记录 provider、模型、token 与耗时等元数据，不记录提示词、回答或密钥。Mock token 数为离线估算，真实模式使用 API 返回的用量。Mock 评测仅验证流程，不代表模型质量。

## 验收状态

| 范围 | 状态 | 说明 |
|---|---|---|
| 固定合成会话、预算策略、来源追踪、artifact | 完成（演示级） | 版本化 fixture；离线估算 token |
| Mock provider、调用元数据、固定流程评测 | 完成（mock 范围） | 不发真实请求；不构成答案质量评估 |
| 轮次选择、构建/预算演示、错误调试面板 | 完成（mock 范围） | mock 异常由本地 debug 路由模拟 |
| Anthropic Provider、真实压缩与回答链路 | 完成（本地演示级） | 后端读取 `.env`；已完成真实端到端冒烟验证 |
| 精确 tokenizer 校准、真实质量评测 | 未完成 | usage 使用 API 实际值；尚未建立质量基准 |
| 完整平台 session/trace 导出与 usage heatmap | 未完成 | 不生成、不上传伪造或未经审查的数据；详见 `ai-logs/README.md` |
| 干净环境启动及发布验收 | 部分完成 | 提供 Windows 启动脚本；尚未在全新机器验证 |

## 环境要求

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/)

## 项目结构

```text
backend/       FastAPI API、上下文策略、Mock Provider、固定数据和测试
frontend/      无构建步骤的本地演示工作台
scripts/       Windows 本地启动脚本
artifacts/     运行时 artifact/usage（忽略，不提交）
docs/          架构、需求追踪和演示脚本
ai-logs/       日志/用量数据可用性说明（没有伪造导出）
```

建议阅读顺序：`backend/context/models.py` → `backend/context/builder.py` → `backend/app/schemas.py` → `backend/app/routes.py` → `frontend/app.js`。

## 功能边界

- 保留 system 指令和最新 user 消息；根据近期消息数和预算选择其余消息。
- 将省略历史的目标、约束/决策、待办和工具结论组成可追踪摘要。
- 超长工具结果以稳定 artifact ID 引用，并支持通过 API 取回完整内容。
- 输入预算放不下必需消息时明确返回错误，不静默丢弃必需内容。
- 本地调试错误默认关闭；显式开启时仅模拟错误响应，不改写数据。
- 默认使用 mock/离线演示；配置 Anthropic 模式后，只有“压缩并回答”流程会发起真实请求。
- 右侧构建面板显示本次 API 选择的保留/省略消息及预算分区；回答面板另行展示实际发送上下文和 usage。

## 安装与启动

在 Windows 命令提示符运行 `scripts\\start-demo.cmd`。它会同步依赖并启动绑定到 `127.0.0.1:8000` 的服务。终止时按 Ctrl+C。也可手动运行：

```bash
uv sync --extra dev
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/`；API 文档位于 `/docs`。默认路径不需要 API key；`.env.example` 只是配置字段示例，不代表已实现真实 provider。不要把密钥放入已跟踪文件。

## API

- `GET /health`：检查服务状态、当前 provider、usage 估算标记和 debug 开关。
- `GET /api/sessions/synthetic-garden-80?turns=10|40|80`：加载固定版本合成会话。
- `GET /api/evaluations/questions`：加载固定评测问题。
- `GET /api/evaluations/run?input_budget=4096`：运行确定性 mock 流程对比，不调用真实 provider。
- `POST /api/mock/answer` 与 `POST /api/mock/summarize`：显式的 mock 演示端点。
- `POST /api/context/build`：根据消息、结构化记忆和预算构建上下文。
- `POST /api/context/answer`：按预算压缩上下文，并使用当前 provider 生成回答和实际 usage。
- `GET /api/artifacts/{artifact_id}`：取回完整工具结果。
- `POST /api/debug/trigger`：仅本地模拟预置错误；默认关闭（`DEBUG_ENABLED = False`）。不要在公共部署中启用。

生成固定评测报告：

```bash
uv run python -m backend.evaluation --input-budget 4096 --output reports/mock-evaluation.json
```

报告包括数据版本、fixture SHA-256、预算与 provider 配置、每题流程的 token 统计、`real_provider_requests: 0` 和评分限制。Mock expected-term 检查不是模型质量指标。

构建请求示例：

```json
{
  "session_id": "demo-session",
  "messages": [
    {"id": "m1", "role": "user", "content": "请调查这个问题"},
    {"id": "m2", "role": "tool", "tool_name": "search", "content": "工具返回内容"}
  ],
  "budget": {"input_tokens": 1200, "output_tokens": 256},
  "recent_message_count": 4,
  "tool_result_char_limit": 500,
  "objective": "找出问题原因",
  "constraints": ["保留原始工具结果"],
  "decisions": [],
  "todos": [],
  "tool_conclusions": []
}
```

预算无法容纳必需消息时返回 `422` 和 `budget_unsatisfiable`；请求校验失败返回 `422` 和 `invalid_request`。`estimated: true` 表示离线近似 token 数。

## 测试

```bash
uv run pytest -q
```

更完整的操作步骤见 `docs/demo-script.md`；范围和限制见 `docs/requirements-traceability.md`、`docs/architecture.md`。
