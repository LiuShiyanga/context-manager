const sampleMessages = [
  {id: 'system-1', role: 'system', content: 'You are a careful engineering assistant. Preserve user goals, decisions, and active constraints.'},
  {id: 'user-1', role: 'user', content: 'Help me investigate why background jobs occasionally retry after completing.'},
  {id: 'assistant-1', role: 'assistant', content: 'I will trace the worker acknowledgement and retry flow, then identify where completion state can be lost.'},
  {id: 'tool-1', role: 'tool', tool_name: 'search_logs', content: 'Synthetic tool result example: completed jobs show acknowledgement timeout; refresh the receipt during long-running work. '.repeat(12)},
  {id: 'assistant-2', role: 'assistant', content: 'The likely cause is a stale queue receipt. Refresh it during processing and acknowledge only after persistence.'},
  {id: 'user-2', role: 'user', content: 'Keep the change backward compatible and add a regression test.'},
  {id: 'assistant-3', role: 'assistant', content: 'I will preserve the current queue contract and test delayed acknowledgement behavior.'},
];

const messageBox = document.querySelector('#messages');
const button = document.querySelector('#build-button');
const errorBox = document.querySelector('#error');

function lines(selector) {
  return document.querySelector(selector).value.split('\n').map((value) => value.trim()).filter(Boolean);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
}

function buildPayload(originalMessages) {
  return {
    session_id: document.querySelector('#session-id').value.trim() || 'demo-session',
    messages: originalMessages,
    budget: {input_tokens: Number(document.querySelector('#input-budget').value), output_tokens: 256},
    recent_message_count: Number(document.querySelector('#recent-count').value),
    tool_result_char_limit: Number(document.querySelector('#tool-limit').value),
    objective: document.querySelector('#objective').value.trim(),
    constraints: lines('#constraints'), decisions: lines('#decisions'),
    todos: lines('#todos'), tool_conclusions: lines('#tool-conclusions'),
  };
}

function renderAnswer(result, originalMessages) {
  renderResults(result.context, originalMessages);
  const usage = result.usage;
  const summaryUsage = result.compression.usage;
  document.querySelector('#results').insertAdjacentHTML('afterbegin', `
    <section class="answer-card"><p class="eyebrow">MODEL ANSWER · ${escapeHtml(usage.provider)}</p><h2>模型回答</h2><p>${escapeHtml(result.answer)}</p>
    <div class="result-summary"><div><span>实际输入</span><strong>${usage.input_tokens} tokens</strong></div><div><span>实际输出</span><strong>${usage.output_tokens} tokens</strong></div><div><span>延迟</span><strong>${usage.duration_ms} ms</strong></div></div>
    <p><small>模型 ${escapeHtml(usage.model)} · ${usage.estimated ? '估算 usage' : 'Provider 报告实际 usage'}${summaryUsage ? ` · 摘要调用 ${summaryUsage.input_tokens}/${summaryUsage.output_tokens} tokens` : ' · 未发摘要请求'}</small></p></section>`);
}

function renderResults(result, originalMessages) {
  const originalById = new Map(originalMessages.map((message) => [message.id, message]));
  const omitted = result.omitted_message_ids.map((id) => originalById.get(id)).filter(Boolean);
  const kept = result.messages;
  const maxTokens = Math.max(1, ...Object.values(result.partitions));
  const partitionLabels = {system: '系统指令', summary: '摘要/结构化信息', recent: '近期对话', tools: '工具结果'};
  const partitionHtml = Object.entries(result.partitions).map(([key, value]) => `<div class="partition-row"><div><span>${partitionLabels[key] || escapeHtml(key)}</span><strong>${value} tokens</strong></div><div class="partition-track"><i style="width:${Math.min(100, value / maxTokens * 100)}%"></i></div></div>`).join('');
  const messageHtml = (message) => `<article class="result-message"><div class="result-message-heading"><strong>${escapeHtml(message.role)}${message.tool_name ? ` · ${escapeHtml(message.tool_name)}` : ''}</strong><code>${escapeHtml(message.id)}</code></div><p>${escapeHtml(message.content)}</p>${message.source_ids?.length ? `<small>来源：${message.source_ids.map(escapeHtml).join(', ')}</small>` : ''}</article>`;
  const artifactsHtml = result.artifacts.length ? `<section><h3>可取回的完整工具结果</h3>${result.artifacts.map((id) => `<button class="text-button artifact-link" data-artifact="${escapeHtml(id)}">查看 ${escapeHtml(id)}</button>`).join('')}<div class="artifact-result"></div></section>` : '';
  document.querySelector('#results').innerHTML = `
    <header class="result-header"><p class="eyebrow">本次构建 · 本地策略</p><h2>上下文构建结果</h2><p>下面数据来自当前输入及后端构建响应；没有调用大模型。</p></header>
    <section class="result-summary"><div><span>估算输入量</span><strong>${result.input_tokens} <small>/ ${Number(document.querySelector('#input-budget').value)} tokens</small></strong></div><div><span>保留消息</span><strong>${kept.length} <small>/ ${originalMessages.length}</small></strong></div><div><span>省略消息</span><strong>${omitted.length}</strong></div></section>
    <section><h3>预算分布 <small>离线估算${result.estimated ? '' : ' · 精确计数器'}</small></h3>${partitionHtml}</section>
    <section><h3>构建后实际保留上下文 <small>${kept.length} 条</small></h3><div class="result-messages">${kept.map(messageHtml).join('') || '<p>没有保留消息。</p>'}</div></section>
    <details class="omitted-details"><summary>被省略的原始消息（${omitted.length} 条）</summary><div class="result-messages">${omitted.map(messageHtml).join('') || '<p>没有省略消息。</p>'}</div></details>
    ${artifactsHtml}`;
  document.querySelectorAll('.artifact-link').forEach((artifactButton) => artifactButton.addEventListener('click', async () => {
    const container = document.querySelector('.artifact-result');
    container.textContent = '读取中…';
    try {
      const response = await fetch(`/api/artifacts/${encodeURIComponent(artifactButton.dataset.artifact)}`);
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message || '读取 artifact 失败');
      container.textContent = body.content;
    } catch (error) { container.textContent = error.message; }
  }));
}

document.querySelector('#load-sample').addEventListener('click', () => {
  messageBox.value = JSON.stringify(sampleMessages, null, 2);
  document.querySelector('#session-id').value = 'demo-session';
  document.querySelector('#objective').value = 'Investigate safe retry behavior.';
  document.querySelector('#constraints').value = 'Keep backward compatible\nDo not lose persisted results';
  document.querySelector('#decisions').value = 'Acknowledge only after persistence';
  document.querySelector('#todos').value = 'Add delayed acknowledgement regression test';
  document.querySelector('#tool-conclusions').value = 'Synthetic fixture only; not production data';
});

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
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
});

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

button.addEventListener('click', async () => {
  errorBox.hidden = true;
  button.disabled = true;
  button.firstElementChild.textContent = '正在构建…';
  let originalMessages = [];
  try {
    originalMessages = JSON.parse(messageBox.value);
    const response = await fetch('/api/context/build', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(buildPayload(originalMessages)),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.detail?.message || result.error?.message || '上下文构建失败');
    renderResults(result, originalMessages);
  } catch (error) {
    errorBox.textContent = error instanceof SyntaxError ? '消息 JSON 格式无效。' : error.message;
    errorBox.hidden = false;
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = '构建上下文';
  }
});

document.querySelector('#evaluation-button').addEventListener('click', async () => {
  const panel = document.querySelector('#evaluation-results');
  panel.hidden = false;
  panel.textContent = '正在运行固定 Mock 评测…';
  try {
    const response = await fetch('/api/evaluations/run?input_budget=' + encodeURIComponent(document.querySelector('#input-budget').value));
    const report = await response.json();
    if (!response.ok) throw new Error(report.error?.message || '评测失败');
    panel.innerHTML = `<h3>Mock 流程比较</h3><p>${escapeHtml(report.quality_conclusion)}</p><p>数据版本 ${escapeHtml(report.dataset_version)} · 真实请求 ${report.real_provider_requests}</p>${report.results.map((row) => `<article><strong>${escapeHtml(row.question_id)}</strong><p>截断流程: ${row.baseline.input_tokens} estimated tokens · 管理流程: ${row.managed.input_tokens} estimated tokens</p><small>${escapeHtml(row.scoring_note)}</small></article>`).join('')}`;
  } catch (error) {
    panel.textContent = error.message;
  }
});

document.querySelector('#answer-button').addEventListener('click', async (event) => {
  const answerButton = event.currentTarget;
  errorBox.hidden = true;
  answerButton.disabled = true;
  answerButton.firstElementChild.textContent = '正在压缩并回答…';
  try {
    const originalMessages = JSON.parse(messageBox.value);
    const payload = buildPayload(originalMessages);
    payload.question = document.querySelector('#question').value.trim();
    payload.force_compress = document.querySelector('#force-compress').checked;
    const response = await fetch('/api/context/answer', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || '回答失败');
    renderAnswer(body, originalMessages);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    answerButton.disabled = false;
    answerButton.firstElementChild.textContent = '压缩并回答';
  }
});

fetch('/health').then((response) => response.json()).then((health) => {
  document.querySelector('.status').innerHTML = `<span class="dot"></span>${escapeHtml(health.provider)} · ${health.estimated_usage ? '估算 usage' : '实际 usage'}`;
}).catch(() => {});

document.querySelector('#load-sample').click();
