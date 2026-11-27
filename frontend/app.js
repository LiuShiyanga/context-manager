const sampleMessages = [
  {id: 'system-1', role: 'system', content: 'You are a careful engineering assistant. Preserve user goals, decisions, and active constraints.'},
  {id: 'user-1', role: 'user', content: 'Help me investigate why background jobs occasionally retry after completing.'},
  {id: 'assistant-1', role: 'assistant', content: 'I will trace the worker acknowledgement and retry flow, then identify where completion state can be lost.'},
  {id: 'tool-1', role: 'tool', tool_name: 'search_logs', content: 'Several completed jobs show an acknowledgement timeout after the worker has persisted the result. The retry consumer checks the queue receipt, but the receipt is not refreshed after long-running tasks. '.repeat(5)},
  {id: 'assistant-2', role: 'assistant', content: 'The likely cause is a stale queue receipt for long-running tasks. Refresh the receipt while processing and acknowledge only after the result is persisted.'},
  {id: 'user-2', role: 'user', content: 'Keep the change backward compatible and include a focused regression test.'},
  {id: 'assistant-3', role: 'assistant', content: 'Understood. I will preserve the existing queue contract and add a test for a task that runs beyond the receipt interval.'},
  {id: 'user-3', role: 'user', content: 'What should we verify before deploying?'},
];

const messagesField = document.querySelector('#messages');
const results = document.querySelector('#results');
const button = document.querySelector('#build-button');
const errorBox = document.querySelector('#error');
const budgetSlider = document.querySelector('#input-budget');

document.querySelector('#load-sample').addEventListener('click', () => {
  messagesField.value = JSON.stringify(sampleMessages, null, 2);
  document.querySelector('#session-id').value = 'retry-investigation';
  document.querySelector('#objective').value = 'Find and fix duplicate retries of completed background jobs.';
  document.querySelector('#constraints').value = 'Keep the queue contract backward compatible.\nAcknowledge only after results are persisted.';
  document.querySelector('#decisions').value = 'Refresh the queue receipt during long-running tasks.';
  document.querySelector('#todos').value = 'Add a regression test for tasks exceeding the receipt interval.\nVerify completed tasks are acknowledged exactly once.';
  document.querySelector('#tool-conclusions').value = 'Logs show stale queue receipts when long-running tasks exceed the receipt interval.';
});

budgetSlider.addEventListener('input', () => {
  document.querySelector('#budget-value').textContent = budgetSlider.value;
});

function lines(id) {
  return document.querySelector(id).value.split('\n').map((value) => value.trim()).filter(Boolean);
}

function safeText(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
}

function renderResult(data) {
  const budget = Number(budgetSlider.value);
  const usage = Math.min(100, Math.round(data.input_tokens / budget * 100));
  const labels = {system: '系统指令', summary: '结构化摘要', recent: '近期消息', tools: '工具结果'};
  const partitions = Object.entries(data.partitions).map(([key, value]) => `<div class="partition"><span>${labels[key] || safeText(key)}</span><strong>${value} tokens</strong></div>`).join('');
  const messages = data.messages.map((message) => {
    const role = message.role === 'summary' ? '结构化摘要' : message.role === 'tool' ? `工具 · ${message.tool_name || ''}` : message.role === 'system' ? '系统' : message.role === 'assistant' ? '助手' : '用户';
    const artifact = message.artifact_id ? `<a class="artifact-link" href="/api/artifacts/${encodeURIComponent(message.artifact_id)}" target="_blank" rel="noopener">↗ 查看完整工具结果 · ${safeText(message.artifact_id)}</a>` : '';
    return `<article class="message-card"><div class="message-meta"><strong>${safeText(role)}</strong><span>${safeText(message.id)}</span></div><pre class="message-content">${safeText(message.content)}</pre>${artifact}</article>`;
  }).join('');
  const omitted = data.omitted_message_ids.length ? `<p class="omitted"><strong>未纳入上下文：</strong>${data.omitted_message_ids.map(safeText).join(' · ')}</p>` : '';
  results.innerHTML = `<div class="result-header"><div><h2>构建结果</h2><p>会话 ${safeText(data.session_id)} · 离线估算</p></div><span class="token-pill">${data.input_tokens} tokens</span></div><section class="meter-card"><div class="meter-title"><span>输入预算使用</span><strong>${data.input_tokens} / ${budget}</strong></div><div class="meter"><i style="width:${usage}%"></i></div><div class="partitions">${partitions}</div></section>${messages}${omitted}`;
}

button.addEventListener('click', async () => {
  errorBox.hidden = true;
  let messages;
  try {
    messages = JSON.parse(messagesField.value);
    if (!Array.isArray(messages)) throw new Error('消息内容必须是 JSON 数组。');
  } catch (error) {
    errorBox.textContent = error instanceof SyntaxError ? `JSON 格式错误：${error.message}` : error.message;
    errorBox.hidden = false;
    return;
  }

  button.disabled = true;
  button.firstElementChild.textContent = '正在构建…';
  try {
    const response = await fetch('/api/context/build', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        session_id: document.querySelector('#session-id').value || 'demo-session',
        messages,
        budget: {input_tokens: Number(budgetSlider.value), output_tokens: 256},
        recent_message_count: Number(document.querySelector('#recent-count').value),
        tool_result_char_limit: Number(document.querySelector('#tool-limit').value),
        objective: document.querySelector('#objective').value.trim(),
        constraints: lines('#constraints'),
        decisions: lines('#decisions'),
        todos: lines('#todos'),
        tool_conclusions: lines('#tool-conclusions'),
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || body.detail?.message || body.detail || '构建失败。');
    renderResult(body);
  } catch (error) {
    errorBox.textContent = error.message || '无法连接本地服务，请确认 API 已启动。';
    errorBox.hidden = false;
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = '构建上下文';
  }
});

document.querySelector('#load-sample').click();
