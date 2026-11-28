# Demo 脚本

## 启动

```bash
uv sync --extra dev
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`。默认 Provider 为 deterministic mock，不访问模型服务；若本地 `.env` 配置 `PROVIDER=anthropic` 与密钥，则「压缩并回答」会调用真实 Provider，页面状态栏会显示当前模式。

## 演示固定样本

1. 在「固定合成会话轮次」选择 10、40 或 80，点击「载入固定会话」。检查消息 JSON 和结构化目标、约束、决定、待办已更新；样本来自固定版本且标记 synthetic。
2. 调整输入预算和「最近消息数」，点击「构建上下文」。结果区展示本次响应中的实际保留消息、被省略消息、token 分区与 artifact 引用；这些是本地策略的输出，不是模型回答。检查摘要消息的 source IDs 是否指向原始消息，且估算 token 总量不超过预算。使用「演示 8k → 4k」按钮切换预算，同一会话重新构建并对照结果。
3. 找到带 artifact 的工具消息，点「查看完整工具结果」。确认完整工具正文在页面显示，原会话 JSON 未被改写。
4. 检查摘要消息的 `source_ids`，并在摘要字段中核对目标、约束、决定和待办。
5. 点击「运行固定 Mock 评测」，确认展示截断 baseline 和管理流程的 token 统计、固定版本及每题评分说明。Mock answer 固定文本不随上下文变化，因此此比较只验证数据流/预算口径，不构成答案质量指标。
6. 将预算降到低于 system + 最新 user 的硬保留成本，点击构建；预期显示结构化预算错误，编辑区中的原始消息仍在。
7. 勾选「启用模拟异常」后分别触发预算不足、摘要 provider 失败、artifact 缺失；检查页面显示结构化错误，消息 JSON 和结构化记忆仍保留。取消勾选后按钮禁用；生产默认 API 也关闭 debug 路由。
8. 将工具截断字符数改为 0 验证 artifact；手工篡改 artifact ID 后请求读取，预期 404。
9. 在窄屏视口确认表单与结果区纵向排列。

## 验收边界

固定样本版本 `1.0.0`，80 个 user turns，10 道评测题。固定评测报告仍声明 `real_provider_requests: 0`，不支持模型质量结论。token counter 在本地构建阶段是离线估算；Anthropic 回答阶段同时返回 API 实际 usage。完整用户 session/trace 导出和 usage heatmap 尚未实现。
