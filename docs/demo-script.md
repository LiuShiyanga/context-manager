# Demo 脚本

## 启动

```bash
uv sync --extra dev
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`。页面及 API 仅本地运行；Provider 固定为 deterministic mock，不会访问模型服务。

## 演示固定样本

1. 在「固定合成会话轮次」选择 10、40 或 80，点击「载入固定会话」。检查消息 JSON 和结构化目标、约束、决定、待办已更新；样本来自固定版本且标记 synthetic。
2. 调整输入预算和「最近消息数」，点击「构建上下文」。检查 token 总量、system/summary/recent/tools 分区，以及保留与省略消息。所有 token 数明确为离线估算。
3. 找到带 artifact 的工具消息，点「查看完整工具结果」。确认完整工具正文在页面显示，原会话 JSON 未被改写。
4. 检查摘要消息的 `source_ids`，并在摘要字段中核对目标、约束、决定和待办。
5. 点击「运行固定 Mock 评测」，确认展示截断 baseline 和管理流程的 token 统计、固定版本及每题评分说明。Mock answer 固定文本不随上下文变化，因此此比较只验证数据流/预算口径，不构成答案质量指标。
6. 将预算降到低于 system + 最新 user 的硬保留成本，点击构建；预期显示结构化预算错误，编辑区中的原始消息仍在。
7. 将工具截断字符数改为 0 验证 artifact；手工篡改 artifact ID 后请求读取，预期 404。生产 UI 不包含故障注入开关。
8. 在窄屏视口确认表单与结果区纵向排列。

## 验收边界

固定样本版本 `1.0.0`，80 个 user turns，10 道评测题。评测报告带 fixture SHA-256，声明 `real_provider_requests: 0`。Mock 评测不支持模型质量结论。token counter 是离线字符估算，不等同 provider tokenizer。真实模型、计数 API、完整用户 session/trace 导出和 usage heatmap 均未启用或生成。
