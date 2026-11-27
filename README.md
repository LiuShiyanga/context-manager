# Context Manager Demo

一个本地上下文管理工作台：选择固定合成会话，整理目标/约束/决定/待办，按预算构建上下文，查看消息分区、来源摘要及可取回的工具 artifact。固定样本包括 80 轮对话和 10 道评测题。

**当前 Provider 固定为 deterministic mock。** 不调用真实模型或外部服务；token 数是离线字符估算，不是精确 tokenizer 计数。Mock 评测仅验证流程，不代表模型质量，不应用于质量结论或生产建议。

## 环境要求

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/)

## 项目结构

```text
backend/
  app/        FastAPI 路由、请求/响应模型与 artifact 存储
  context/    token counter、上下文筛选、mock provider 与 usage 元数据
  data/       版本化合成会话、评测题、哈希清单
  tests/      策略、provider、评测与 API 回归测试
  evaluation.py  可重复的 mock 流程评测入口
frontend/     无构建步骤的本地演示工作台
artifacts/    本地运行时生成的 artifact 和 usage 元数据（已 gitignore）
reports/      本地生成的评测报告（可按需归档）
```

建议阅读顺序：`backend/context/models.py` → `backend/context/builder.py` → `backend/app/schemas.py` → `backend/app/routes.py` → `frontend/app.js`。

## 功能边界

- 保留 system 指令和最新 user 消息；根据近期消息数和预算选择其余消息。
- 将省略历史的目标、约束/决策、待办和工具结论组成可追踪摘要。
- 超长工具结果以稳定 artifact ID 引用，并支持通过 API 取回完整内容。
- 输入预算放不下必需消息时明确返回错误，不静默丢弃必需内容。
- 当前只实现 mock/离线演示：不调用真实模型，没有真实质量评测或调试异常注入面板。

## 安装与启动

```bash
uv sync --extra dev
uv run uvicorn backend.app.main:app --reload
```

打开 <http://127.0.0.1:8000/>。页面提供示例对话和表单，可直接点击「构建上下文」；API 文档位于 <http://127.0.0.1:8000/docs>。

## API

- `GET /health`：检查服务状态、mock provider 和估算标记。
- `GET /api/sessions/synthetic-garden-80?turns=10|40|80`：加载固定版本合成会话。
- `GET /api/evaluations/questions`：加载固定评测问题。
- `GET /api/evaluations/run?input_budget=4096`：运行确定性 mock 流程对比；不调用真实 provider。
- `POST /api/mock/answer` 与 `POST /api/mock/summarize`：显式的 mock provider 演示端点。
- `POST /api/context/build`：根据消息、结构化记忆和预算构建上下文。
- `GET /api/artifacts/{artifact_id}`：取回完整工具结果。

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

预算无法容纳必需消息时返回 `422` 和 `budget_unsatisfiable`；请求校验失败返回 `422` 和 `invalid_request`。结果中的 `estimated: true` 表示 token 数是离线近似值。

## 测试

```bash
uv run pytest -q
```
