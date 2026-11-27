# Context Manager Demo

一个可在本机运行的上下文管理工作台：粘贴对话消息，整理目标、约束、决策与待办，按输入 token 预算构建上下文，并查看消息分区、摘要及被省略的消息。长工具结果会保存为本地 artifact，构建结果提供可取回的 artifact ID。

当前版本使用确定性的离线近似 token 估算（每 3 个字符约 1 token），不调用外部模型或服务。

## 环境要求

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/)

## 项目结构

```text
backend/
  app/        FastAPI 路由、请求/响应模型与 artifact 存储
  context/    token 估算、上下文筛选与结构化摘要
  tests/      策略核心与 API 回归测试
frontend/     无构建步骤的静态演示工作台
artifacts/    本地运行时生成的工具结果（已 gitignore）
```

建议阅读顺序：`backend/context/models.py` → `backend/context/builder.py` → `backend/app/schemas.py` → `backend/app/routes.py` → `frontend/app.js`。

## 功能边界

- 保留 system 指令和最新 user 消息；根据近期消息数和预算选择其余消息。
- 将省略历史的目标、约束/决策、待办和工具结论组成可追踪摘要。
- 超长工具结果以稳定 artifact ID 引用，并支持通过 API 取回完整内容。
- 输入预算放不下必需消息时明确返回错误，不静默丢弃必需内容。
- 当前只实现 mock/离线演示：不调用真实模型，没有真实质量评测、80 轮固定数据集或调试异常注入面板。

## 安装与启动

```bash
uv sync --extra dev
uv run uvicorn backend.app.main:app --reload
```

打开 <http://127.0.0.1:8000/>。页面提供示例对话和表单，可直接点击「构建上下文」；API 文档位于 <http://127.0.0.1:8000/docs>。

## API

- `GET /health`：返回服务状态及 mock provider 标记。
- `POST /api/context/build`：根据消息、结构化记忆和预算构建上下文。
- `GET /api/artifacts/{artifact_id}`：取回完整工具结果。

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
