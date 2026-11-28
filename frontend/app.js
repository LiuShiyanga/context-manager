// 页面启动时加载的短会话样本，用于快速演示上下文构建流程。
const sampleMessages = [
  {id: 'system-1', role: 'system', content: 'You are a careful engineering assistant. Preserve user goals, decisions, and active constraints.'},
  {id: 'user-1', role: 'user', content: 'Help me investigate why background jobs occasionally retry after completing.'},
  {id: 'assistant-1', role: 'assistant', content: 'I will trace the worker acknowledgement and retry flow, then identify where completion state can be lost.'},
  {id: 'tool-1', role: 'tool', tool_name: 'search_logs', content: 'Synthetic tool result example: completed jobs show acknowledgement timeout; refresh the receipt during long-running work. '.repeat(12)},
  {id: 'assistant-2', role: 'assistant', content: 'The likely cause is a stale queue receipt. Refresh it during processing and acknowledge only after persistence.'},
  {id: 'user-2', role: 'user', content: 'Keep the change backward compatible and add a regression test.'},
  {id: 'assistant-3', role: 'assistant', content: 'I will preserve the current queue contract and test delayed acknowledgement behavior.'},
  {id: 'user-3', role: 'user', content: 'What should happen if receipt refresh fails?'},
  {id: 'assistant-4', role: 'assistant', content: 'Stop processing safely, retain the persisted state, and let the retry policy handle recovery.'},
];

// 缓存频繁使用的页面节点，避免每次交互都重复查询 DOM。
const messageBox = document.querySelector('#messages');
const errorBox = document.querySelector('#error');
const button = document.querySelector('#build-button');
const results = document.querySelector('#results');

// 将“每行一项”的文本域规范化为去空白、去空行的字符串数组。
function lines(selector) {
  return document.querySelector(selector).value.split('\n').map((value) => value.trim()).filter(Boolean);
}

// 把构建响应转换为预算分区、消息卡片和 artifact 入口。
function renderResult(data) {
  const messages = data.messages.map((message) => {
    const sourceInfo = message.source_ids?.length ? `<small>来源: ${message.source_ids.join(', ')}</small>` : '';
    const artifact = message.artifact_id ? `<button class="text-button" data-artifact="${message.artifact_id}">查看完整工具结果</button>` : '';
    // 消息正文必须先转义，防止会话内容被浏览器解释为 HTML。
    return `<article class="message-card"><div><strong>${message.role}</strong><span>${message.id}</span></div><p>${escapeHtml(message.content)}</p>${sourceInfo}${artifact}</article>`;
  }).join('');
  const partitions = Object.entries(data.partitions).map(([key, value]) => `<li><span>${key}</span><strong>${value}</strong></li>`).join('');
  results.innerHTML = `<section class="panel result-panel"><p class="eyebrow">BUILT CONTEXT</p><h2>${data.input_tokens} / ${document.querySelector('#input-budget').value} tokens</h2><p>${data.estimated ? '离线估算值' : '精确计数'}</p><h3>预算分区</h3><ul class="partition-list">${partitions}</ul><h3>保留消息</h3>${messages}<h3>省略消息 (${data.omitted_message_ids.length})</h3><p>${data.omitted_message_ids.join(', ') || '无'}</p><h3>可取回 Artifacts (${data.artifacts.length})</h3><ul>${data.artifacts.map((id) => `<li><button class="text-button" data-artifact="${id}">${id}</button></li>`).join('')}</ul><pre id="artifact-content" hidden></pre></section>`;
  // 结果区是动态创建的，因此在每次渲染后为 artifact 按钮重新绑定事件。
  results.querySelectorAll('[data-artifact]').forEach((element) => element.addEventListener('click', () => readArtifact(element.dataset.artifact)));
}

// 转义五种具有 HTML 语义的字符，供 innerHTML 模板安全展示外部文本。
function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
}

// 按服务端生成的稳定 ID 读取被外置的完整工具结果。
async function readArtifact(id) {
  const response = await fetch(`/api/artifacts/${encodeURIComponent(id)}`);
  const body = await response.json();
  const output = document.querySelector('#artifact-content');
  output.hidden = false;
  // 使用 textContent 展示正文，确保工具输出不会作为 HTML 执行。
  output.textContent = response.ok ? body.content : body.error?.message || '无法读取 artifact';
  output.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

// 将内置短样本和对应结构化记忆一次性填入表单。
document.querySelector('#load-sample').addEventListener('click', () => {
  messageBox.value = JSON.stringify(sampleMessages, null, 2);
  document.querySelector('#session-id').value = 'demo-session';
  document.querySelector('#objective').value = 'Investigate safe retry behavior.';
  document.querySelector('#constraints').value = 'Keep backward compatible\nDo not lose persisted results';
  document.querySelector('#decisions').value = 'Acknowledge only after persistence';
  document.querySelector('#todos').value = 'Add delayed acknowledgement regression test';
  document.querySelector('#tool-conclusions').value = 'Synthetic fixture only; not production data';
});

// 从 API 载入指定轮数的版本化合成会话，并同步其元数据字段。
document.querySelector('#load-fixture').addEventListener('click', async () => {
  errorBox.hidden = true;
  try {
    const turns = document.querySelector('#fixture-turns').value;
    const response = await fetch(`/api/sessions/synthetic-garden-80?turns=${turns}`);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || '无法加载固定会话');
    messageBox.value = JSON.stringify(body.messages, null, 2);
    document.querySelector('#session-id').value = body.session_id;
    document.querySelector('#objective').value = body.objective;
    document.querySelector('#constraints').value = body.constraints.join('\n');
    document.querySelector('#decisions').value = body.decisions.join('\n');
    document.querySelector('#todos').value = body.todos.join('\n');
    document.querySelector('#tool-conclusions').value = '固定版本合成样本；不得作为真实建议';
  } catch (error) {
    // 网络错误与 API 业务错误统一显示在表单下方的告警区域。
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
});

// 滑块变化时只更新可见数值，实际预算在构建请求时读取。
document.querySelector('#input-budget').addEventListener('input', (event) => {
  document.querySelector('#budget-value').textContent = event.target.value;
});

document.querySelector('#budget-demo').addEventListener('click', () => {
  const budget = document.querySelector('#input-budget');
  budget.value = Number(budget.value) > 5000 ? 4000 : 8000;
  budget.dispatchEvent(new Event('input'));
});

document.querySelector('#debug-enabled').addEventListener('change', (event) => {
  document.querySelector('#debug-trigger').disabled = !event.target.checked;
});

document.querySelector('#debug-trigger').addEventListener('click', async () => {
  errorBox.hidden = true;
  const scenario = document.querySelector('#debug-scenario').value;
  try {
    const response = await fetch('/api/debug/trigger', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scenario}),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || '模拟异常');
  } catch (error) {
    errorBox.textContent = `${error.message}（演示调试错误；输入会话未更改）`;
    errorBox.hidden = false;
  }
});

// 收集完整表单并请求上下文构建，同时维护按钮的加载与恢复状态。
button.addEventListener('click', async () => {
  errorBox.hidden = true;
  button.disabled = true;
  button.firstElementChild.textContent = '正在构建…';
  try {
    const response = await fetch('/api/context/build', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        session_id: document.querySelector('#session-id').value.trim() || 'demo-session',
        messages: JSON.parse(messageBox.value),
        budget: {input_tokens: Number(document.querySelector('#input-budget').value), output_tokens: 256},
        recent_message_count: Number(document.querySelector('#recent-count').value),
        tool_result_char_limit: Number(document.querySelector('#tool-limit').value),
        objective: document.querySelector('#objective').value.trim(),
        constraints: lines('#constraints'), decisions: lines('#decisions'),
        todos: lines('#todos'), tool_conclusions: lines('#tool-conclusions'),
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || body.detail?.message || body.detail || '构建失败。');
    renderResult(body);
  } catch (error) {
    // JSON 解析、请求失败和服务端错误都通过同一个可访问告警节点反馈。
    errorBox.textContent = error.message || '无法连接本地服务，请确认 API 已启动。';
    errorBox.hidden = false;
  } finally {
    // 无论请求结果如何都恢复按钮，避免页面停留在不可操作状态。
    button.disabled = false;
    button.firstElementChild.textContent = '构建上下文';
  }
});

// 运行固定 Mock 评测，并在独立面板中展示两条流程的估算 token 对比。
document.querySelector('#evaluation-button').addEventListener('click', async () => {
  const panel = document.querySelector('#evaluation-results');
  panel.hidden = false;
  panel.textContent = '正在运行固定 Mock 评测…';
  try {
    const response = await fetch('/api/evaluations/run?input_budget=' + encodeURIComponent(document.querySelector('#input-budget').value));
    const report = await response.json();
    if (!response.ok) throw new Error(report.error?.message || '评测失败');
    panel.innerHTML = `<h3>Mock 流程比较</h3><p>${escapeHtml(report.quality_conclusion)}</p><p>数据版本 ${report.dataset_version} · 真实请求 ${report.real_provider_requests}</p>${report.results.map((row) => `<article><strong>${row.question_id}</strong><p>截断流程: ${row.baseline.input_tokens} estimated tokens · 管理流程: ${row.managed.input_tokens} estimated tokens</p><small>${escapeHtml(row.scoring_note)}</small></article>`).join('')}`;
  } catch (error) {
    panel.textContent = error.message;
  }
});

// 首次打开页面时自动填充短样本，让工作台处于可立即运行的状态。
document.querySelector('#load-sample').click();
