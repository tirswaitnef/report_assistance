'use strict';

const state = { case: null, report: null, health: null, knowledge: null, busy: false, experiment: null, experimentStarting: false, experimentTimer: null, experimentCaseTitle: '' };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const stringify = (value) => typeof value === 'string' ? value : JSON.stringify(value ?? '');

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function notice(message, success = false) {
  const node = $('#notice');
  node.textContent = message;
  node.classList.toggle('success', success);
  node.classList.toggle('hidden', !message);
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  let data;
  try { data = await response.json(); } catch (_) { throw new Error(`Máy chủ trả về dữ liệu không hợp lệ (HTTP ${response.status}).`); }
  if (!response.ok) {
    const detail = data.detail || data.error || `HTTP ${response.status}`;
    const message = Array.isArray(detail) ? detail.map((item) => `${(item.loc || []).join('.')}: ${item.msg || stringify(item)}`).join('; ') : stringify(detail);
    const error = new Error(message.slice(0, 1500));
    error.status = response.status;
    throw error;
  }
  return data;
}

function safeLink(url, text, className) {
  const link = el('a', className, text);
  try {
    const parsed = new URL(url);
    if (['https:', 'http:'].includes(parsed.protocol)) {
      link.href = parsed.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
  } catch (_) { /* An invalid external URL is displayed without a link. */ }
  return link;
}

function severity(value) {
  const level = String(value || 'info').toLowerCase();
  const valid = ['critical', 'high', 'medium', 'low', 'info'].includes(level) ? level : 'info';
  return el('span', `severity ${valid}`, valid);
}

function evidenceTags(ids) {
  const holder = el('div');
  for (const id of ids || []) holder.append(el('span', 'evidence-tag', id));
  return holder;
}

function renderEvidence(evidence) {
  const card = el('article', 'evidence-card');
  card.append(el('h3', '', evidence.id || 'Bằng chứng'), el('p', '', `Nguồn: ${stringify(evidence.source || 'Chưa xác định')}`));
  if (evidence.collected_at) card.append(el('p', '', `Thu thập: ${evidence.collected_at}`));
  card.append(el('pre', '', stringify(evidence.content)));
  return card;
}

function clearReport() {
  state.report = null;
  $('#report-empty').classList.remove('hidden');
  $('#report-content').classList.add('hidden');
  $('#report-content').replaceChildren();
  $('#export-md').disabled = true;
  $('#export-json').disabled = true;
}

function setCase(data, updateEditor = true) {
  if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.findings) || !Array.isArray(data.evidence)) {
    throw new Error('JSON cần là một hồ sơ có hai mảng findings và evidence. Xem hồ sơ mẫu để biết cấu trúc.');
  }
  if (data.findings.some((item) => !item || typeof item !== 'object' || Array.isArray(item) || (item.evidence_ids !== undefined && !Array.isArray(item.evidence_ids))) || data.evidence.some((item) => !item || typeof item !== 'object' || Array.isArray(item))) {
    throw new Error('Mỗi finding và evidence phải là một đối tượng JSON; evidence_ids phải là một mảng mã bằng chứng.');
  }
  state.case = data;
  clearReport();
  $('#stat-findings').textContent = data.findings.length;
  $('#stat-evidence').textContent = data.evidence.length;
  $('#finding-tab-count').textContent = data.findings.length;
  $('#evidence-tab-count').textContent = data.evidence.length;
  $('#case-description').textContent = data.description || `${data.title || 'Hồ sơ tùy chỉnh'} · ${stringify(data.database || 'CSDL chưa xác định')}`;
  const findings = $('#input-findings');
  findings.replaceChildren();
  for (const finding of data.findings) {
    const card = el('article', 'input-finding');
    const meta = el('div', 'finding-meta');
    meta.append(severity(finding.severity), el('span', '', finding.id || '—'));
    card.append(meta, el('h3', '', finding.title || 'Finding chưa có tiêu đề'), el('p', '', finding.description || ''), evidenceTags(finding.evidence_ids));
    findings.append(card);
  }
  if (!data.findings.length) findings.append(el('p', 'empty-input', 'Chưa có findings trong hồ sơ.'));
  const evidence = $('#input-evidence');
  evidence.replaceChildren(...data.evidence.map(renderEvidence));
  if (!data.evidence.length) evidence.append(el('p', 'empty-input', 'Hồ sơ chưa cung cấp bằng chứng.'));
  if (updateEditor) $('#json-editor').value = JSON.stringify(data, null, 2);
  if (!experimentActive()) {
    $('#study-case-id').value = 'case-current';
    $('#study-cluster-id').value = 'cluster-current';
  }
  $('#generate-button').disabled = state.busy;
  updateExperimentControls();
}

async function loadCase(id) {
  if (!id) return;
  try {
    $('#generate-button').disabled = true;
    setCase(await api(`/api/cases/${encodeURIComponent(id)}`));
    if (!experimentActive()) {
      $('#study-case-id').value = id;
      $('#study-cluster-id').value = id;
    }
    notice('');
  } catch (error) {
    state.case = null;
    $('#generate-button').disabled = true;
    updateExperimentControls();
    notice(`Không tải được hồ sơ: ${error.message}`);
  }
}

function syncMode() {
  const grounding = $('#grounding-toggle').checked;
  const rag = $('#rag-toggle').checked;
  $$('.mode-pills button').forEach((button) => button.classList.toggle('selected', String(grounding) === button.dataset.grounding && String(rag) === button.dataset.rag));
}

function setBusy(busy) {
  state.busy = busy;
  for (const selector of ['#case-select', '#import-button', '#apply-json', '#provider-select', '#grounding-toggle', '#rag-toggle']) $(selector).disabled = busy;
  $$('.mode-pills button').forEach((button) => { button.disabled = busy; });
  $('#generate-button').disabled = busy || !state.case;
  $('#generate-button').lastChild.textContent = busy ? ' Đang phân tích…' : 'Sinh báo cáo';
  $('#report-loading').classList.toggle('hidden', !busy);
  if (busy) {
    $('#report-empty').classList.add('hidden');
    $('#report-content').classList.add('hidden');
    $('#export-md').disabled = true;
    $('#export-json').disabled = true;
  }
  updateExperimentControls();
}

function citationCard(source) {
  const card = el('div', 'citation');
  card.append(safeLink(source.url, `${source.id || source.source_id || 'OWASP'} · ${source.title || 'OWASP guidance'}`, ''));
  if (source.section) card.append(el('small', '', source.section));
  if (source.text) {
    const details = el('details');
    details.append(el('summary', '', 'Xem đoạn hướng dẫn được truy xuất'), el('p', '', source.text));
    card.append(details);
  }
  return card;
}

function reportFinding(finding) {
  const card = el('article', 'report-finding');
  const heading = el('div', 'findings-heading');
  heading.append(severity(finding.severity), el('span', 'small-label', finding.id), el('span', `report-status ${finding.status === 'supported' ? 'supported' : 'needs-review'}`, finding.status === 'supported' ? 'Có liên kết bằng chứng' : 'Cần kiểm tra thêm'));
  card.append(heading, el('h3', '', finding.title));
  if (finding.asset) card.append(el('div', 'report-meta', `Tài sản: ${stringify(finding.asset)}`));
  card.append(el('p', 'analysis', finding.analysis || 'Chưa có phân tích.'));
  if (finding.claims?.length) {
    card.append(el('h4', 'report-section-label', 'Phân tích & liên kết bằng chứng'));
    for (const claim of finding.claims) {
      const row = el('div', 'claim');
      const text = el('div');
      text.append(el('span', '', claim.text), evidenceTags(claim.evidence_ids));
      row.append(el('span', 'claim-bullet', '↳'), text);
      card.append(row);
    }
  }
  if (finding.evidence?.length) {
    const details = el('details', 'evidence-details');
    details.append(el('summary', '', `Kiểm tra bằng chứng gốc (${finding.evidence.length})`));
    for (const item of finding.evidence) details.append(renderEvidence(item));
    card.append(details);
  }
  if (finding.remediation?.length) {
    card.append(el('h4', 'report-section-label', 'Khuyến nghị remediation'));
    for (const [index, remediation] of finding.remediation.entries()) {
      const item = el('div', 'remediation-card');
      item.append(el('h4', '', `${index + 1}. ${remediation.action || 'Khuyến nghị'}`));
      if (remediation.rationale) item.append(el('p', '', remediation.rationale));
      if (remediation.verification) {
        const verification = el('p');
        verification.append(el('strong', '', 'Xác minh: '), document.createTextNode(remediation.verification));
        item.append(verification);
      }
      if (remediation.owasp_refs?.length) item.append(evidenceTags(remediation.owasp_refs));
      card.append(item);
    }
  }
  if (finding.owasp?.length) {
    card.append(el('h4', 'report-section-label', 'Nguồn OWASP được truy xuất'));
    for (const source of finding.owasp) card.append(citationCard(source));
  }
  for (const warning of finding.warnings || []) card.append(el('div', 'report-warning', stringify(warning)));
  return card;
}

function renderReport(report) {
  state.report = report;
  const container = $('#report-content');
  container.replaceChildren();
  const intro = el('div', 'report-intro');
  intro.append(el('h3', '', report.title || 'Báo cáo kiểm thử bảo mật CSDL'));
  const meta = el('div', 'report-meta');
  const providerName = report.provider === 'template' ? 'Template demo' : (report.provenance?.llm_backend === 'gemini' || state.health?.llm_backend === 'gemini' ? 'Gemini' : 'LLM');
  meta.append(el('span', '', stringify(report.database)), el('span', '', providerName), el('span', '', `Grounding ${report.mode?.grounding ? 'ON' : 'OFF'}`), el('span', '', `RAG ${report.mode?.rag ? 'ON' : 'OFF'}`));
  intro.append(meta);
  const counters = el('div', 'report-counters');
  for (const [value, label] of [[report.summary?.total ?? report.findings?.length ?? 0, 'Findings'], [report.summary?.confirmed ?? 0, 'Có liên kết bằng chứng'], [report.summary?.needs_review ?? 0, 'Cần kiểm tra thêm']]) {
    const counter = el('div');
    counter.append(el('strong', '', value), document.createTextNode(label));
    counters.append(counter);
  }
  intro.append(counters);
  const provenance = report.provenance || {};
  const generation = provenance.generation || {};
  const requestedModel = generation.model_requested || provenance.model;
  const resolvedModel = generation.model_resolved;
  if (requestedModel) intro.append(el('p', 'model-provenance', `Model yêu cầu: ${requestedModel}`));
  if (report.provider === 'llm') intro.append(el('p', 'model-provenance', `Model API trả về: ${resolvedModel || 'API không cung cấp phiên bản cụ thể'}`));
  const usage = generation.usage;
  if (usage) {
    const input = usage.promptTokenCount ?? usage.prompt_tokens ?? usage.input_tokens;
    const output = usage.candidatesTokenCount ?? usage.completion_tokens ?? usage.output_tokens;
    const total = usage.totalTokenCount ?? usage.total_tokens;
    const values = [[input, 'đầu vào'], [output, 'đầu ra'], [total, 'tổng']].filter(([value]) => typeof value === 'number').map(([value, label]) => `${label}: ${value}`);
    if (values.length) intro.append(el('p', 'model-provenance', `Tokens API ghi nhận · ${values.join(' · ')}`));
  }
  container.append(intro);
  if (report.provider === 'template') container.append(el('div', 'report-warning', 'Bản demo dùng template và luật có sẵn. Nội dung chưa được chuyên gia xác nhận và không phải kết quả thực nghiệm đánh giá LLM.'));
  for (const warning of report.warnings || []) container.append(el('div', 'report-warning', stringify(warning)));
  for (const finding of report.findings || []) container.append(reportFinding(finding));
  const evaluation = el('section', 'evaluation-panel');
  evaluation.append(el('h4', '', 'Kiểm tra cấu trúc báo cáo'), el('p', '', 'Kiểm tra độ bao phủ findings và liên kết trích dẫn. Tính đúng đắn của phân tích và remediation cần được chuyên gia chấm riêng.'));
  const button = el('button', 'button button-light quality-button', 'Kiểm tra liên kết & độ bao phủ');
  button.addEventListener('click', () => evaluateReport(button, evaluation));
  evaluation.append(button);
  container.append(evaluation);
  $('#report-empty').classList.add('hidden');
  container.classList.remove('hidden');
  $('#export-md').disabled = !report.markdown;
  $('#export-json').disabled = false;
}

async function evaluateReport(button, panel) {
  button.disabled = true;
  button.textContent = 'Đang kiểm tra…';
  try {
    const result = await api('/api/evaluate', { method: 'POST', body: JSON.stringify({ report_id: state.report.id }) });
    panel.querySelector('.evaluation-grid')?.remove();
    panel.querySelector('.eval-notes')?.remove();
    const grid = el('div', 'evaluation-grid');
    for (const [key, label] of [['citation_validity', 'ID trích dẫn tồn tại'], ['evidence_coverage', 'Claim có ID bằng chứng'], ['finding_coverage', 'Bao phủ finding ID']]) {
      const item = el('div', 'eval-item');
      const value = typeof result[key] === 'number' ? `${Math.round(result[key] * 100)}%` : 'N/A';
      item.append(el('strong', '', value), el('span', '', label));
      grid.append(item);
    }
    panel.append(grid);
    const notes = el('ul', 'eval-notes');
    for (const note of result.notes || []) notes.append(el('li', '', stringify(note)));
    notes.append(el('li', '', 'Tỷ lệ khẳng định không được hỗ trợ về ngữ nghĩa: chưa đo; cần nhãn chuyên gia.'));
    panel.append(notes);
    button.textContent = 'Kiểm tra lại';
  } catch (error) {
    notice(`Không kiểm tra được báo cáo: ${error.message}`);
    button.textContent = 'Thử kiểm tra lại';
  } finally { button.disabled = false; }
}

async function generate() {
  if (!state.case || state.busy) return;
  notice('');
  setBusy(true);
  try {
    const report = await api('/api/reports', { method: 'POST', body: JSON.stringify({ case: state.case, grounding: $('#grounding-toggle').checked, rag: $('#rag-toggle').checked, provider: $('#provider-select').value }) });
    renderReport(report);
  } catch (error) {
    notice(`Không sinh được báo cáo: ${error.message}`);
    if (state.report) renderReport(state.report);
    else $('#report-empty').classList.remove('hidden');
  } finally { setBusy(false); }
}

function download(content, type, extension) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = el('a');
  link.href = url;
  link.download = `security-report-${String(state.report?.id || 'draft').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80)}.${extension}`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderKnowledge(data) {
  state.knowledge = data;
  const container = $('#knowledge-sources');
  container.replaceChildren();
  for (const source of data.sources || []) {
    const card = el('article', 'panel knowledge-card');
    card.append(el('div', 'knowledge-icon', '▤'), el('h2', '', source.title || source.id), el('p', '', source.description || 'Hướng dẫn OWASP dùng làm nguồn tham chiếu cho truy xuất và gợi ý remediation.'), safeLink(source.url, 'Mở tài liệu gốc ↗'));
    const meta = el('div', 'knowledge-meta');
    meta.append(el('span', '', `${source.chunks ?? '—'} đoạn hướng dẫn`), el('span', '', `Phiên bản: ${source.revision || 'Chưa xác định'}`));
    card.append(meta);
    container.append(card);
  }
  if (!data.sources?.length) container.append(el('p', 'empty-input', 'Thư viện chưa có dữ liệu. Kiểm tra cấu hình corpus của máy chủ.'));
  $('#stat-chunks').textContent = data.chunks ?? state.health?.corpus_chunks ?? '—';
}

function updateProviderHint() {
  $('#provider-hint').textContent = $('#provider-select').value === 'llm'
    ? `${state.health?.llm_backend === 'gemini' ? 'Gemini API' : 'LLM'} nhận findings và ngữ cảnh được chọn; mỗi lần sinh có thể dùng quota/tính phí. Chỉ gửi bằng chứng đã khử dữ liệu nhạy cảm.`
    : state.health?.llm_configured ? 'Template dùng để kiểm tra luồng xử lý; không đại diện năng lực Gemini/LLM.' : 'Chưa có cấu hình Gemini. Trên máy cá nhân, chạy: py -3.12 run.py --configure-gemini rồi khởi động lại web. Template vẫn dùng được.';
}

function experimentActive() {
  return state.experimentStarting || ['queued', 'running'].includes(state.experiment?.status);
}

function updateExperimentControls() {
  if (!$('#experiment-start')) return;
  const active = experimentActive();
  const repeats = Number($('#experiment-repeats').value);
  const configured = Boolean(state.health?.llm_configured);
  const backend = state.health?.llm_backend === 'gemini' ? 'Gemini' : 'LLM';
  $('#experiment-call-count').textContent = Number.isInteger(repeats) ? repeats * 4 : '—';
  $('#experiment-case').textContent = state.case ? `${state.case.title || 'Hồ sơ tùy chỉnh'} · ${state.case.findings.length} findings` : 'Chưa chọn hồ sơ. Mở Báo cáo bảo mật để chọn hoặc nhập JSON.';
  $('#experiment-model').textContent = configured ? `${backend} · ${state.health.llm_model || 'model từ server'} · đã cấu hình, chưa xác minh kết nối` : 'Gemini chưa được cấu hình. Chạy py -3.12 run.py --configure-gemini ở Terminal rồi mở lại web.';
  $('#experiment-start').disabled = active || state.busy || !configured || !state.case;
  $('#experiment-start').textContent = active ? 'Thực nghiệm đang chạy…' : `Chạy thực nghiệm ${backend}`;
  $('#experiment-repeats').disabled = active || state.busy;
  $('#experiment-seed').disabled = active || state.busy;
  for (const selector of ['#study-case-id', '#study-cluster-id', '#study-split', '#study-engine-version']) $(selector).disabled = active || state.busy;
  $('#experiment-download').disabled = !state.experiment?.download_ready;
}

function renderExperiment(data) {
  state.experiment = data;
  const labels = { queued: 'Đang chờ', running: 'Đang chạy', completed: 'Đã hoàn thành', completed_with_errors: 'Hoàn thành, có lượt lỗi', failed: 'Thực nghiệm gặp lỗi' };
  const completed = Number(data.completed || 0);
  const failed = Number(data.failed || 0);
  const total = Number(data.total || 0);
  $('#experiment-status').textContent = `${labels[data.status] || data.status} · ${completed}/${total} đã xử lý · ${failed} lỗi`;
  const current = data.current;
  $('#experiment-current').textContent = current ? `Đang xử lý ${current.condition} · lần lặp ${current.repeat}` : (state.experimentCaseTitle ? `Hồ sơ của lượt này: ${state.experimentCaseTitle}` : '');
  $('#experiment-progress').max = Math.max(1, total);
  $('#experiment-progress').value = Math.min(total, completed);
  const rows = $('#experiment-runs');
  rows.replaceChildren();
  for (const run of data.runs || []) {
    const row = el('tr');
    const condition = `G${run.grounding ? '1' : '0'}R${run.rag ? '1' : '0'}`;
    const statuses = { completed: 'Hoàn thành', failed: 'Lỗi', pending: 'Đang chờ', running: 'Đang chạy', not_attempted: 'Chưa thực hiện' };
    const status = statuses[run.status] || String(run.status || '—');
    const values = [run.blind_id || '—', condition, run.repeat ?? '—', status, typeof run.latency_seconds === 'number' ? `${run.latency_seconds.toFixed(2)} s` : '—'];
    for (const value of values) row.append(el('td', '', value));
    rows.append(row);
    if (run.error) {
      const errorRow = el('tr');
      const cell = el('td', 'experiment-run-error', stringify(run.error));
      cell.colSpan = 5;
      errorRow.append(cell);
      rows.append(errorRow);
    }
  }
  $('#experiment-results').classList.remove('hidden');
  updateExperimentControls();
}

async function pollExperiment(id) {
  if (state.experimentTimer) clearTimeout(state.experimentTimer);
  try {
    const data = await api(`/api/experiments/${encodeURIComponent(id)}`);
    renderExperiment(data);
    $('#experiment-error').textContent = '';
    if (['queued', 'running'].includes(data.status)) state.experimentTimer = setTimeout(() => pollExperiment(id), 2000);
  } catch (error) {
    if (error.status === 404) {
      try { localStorage.removeItem('db-security-experiment-id'); } catch (_) { /* Optional progress recovery. */ }
      state.experiment = null;
      $('#experiment-error').textContent = 'Không tìm thấy thực nghiệm đã lưu trên máy chủ này. Kiểm tra bộ ZIP đã tải hoặc chọn hồ sơ để tạo lượt mới.';
      updateExperimentControls();
      return;
    }
    $('#experiment-error').textContent = `Chưa đọc được tiến độ: ${error.message}. Đang thử kết nối lại; không tạo thực nghiệm mới.`;
    state.experimentTimer = setTimeout(() => pollExperiment(id), 4000);
  }
}

async function startExperiment() {
  if (experimentActive() || !state.case || !state.health?.llm_configured || state.busy) return;
  const repeats = Number($('#experiment-repeats').value);
  const seed = Number($('#experiment-seed').value);
  const study = { case_id: $('#study-case-id').value.trim(), cluster_id: $('#study-cluster-id').value.trim(), split: $('#study-split').value, engine_version: $('#study-engine-version').value.trim() || 'unknown' };
  if (!Number.isInteger(repeats) || repeats < 1 || repeats > 5 || !Number.isInteger(seed) || seed < 0 || seed > 2147483647) {
    $('#experiment-error').textContent = 'Chọn 1–5 lần lặp và seed là số nguyên từ 0 đến 2147483647.';
    return;
  }
  if (![study.case_id, study.cluster_id].every((id) => /^[A-Za-z0-9_-]{1,80}$/.test(id)) || !['pilot', 'development', 'test'].includes(study.split)) {
    $('#experiment-error').textContent = 'Mã case/cluster chỉ gồm chữ, số, dấu - hoặc _, tối đa 80 ký tự. Chọn đúng nhóm dữ liệu trước khi chạy.';
    return;
  }
  state.experimentStarting = true;
  $('#experiment-error').textContent = '';
  updateExperimentControls();
  try {
    const result = await api('/api/experiments', { method: 'POST', body: JSON.stringify({ case: state.case, repeats, seed, provider: 'llm', study }) });
    try { localStorage.setItem('db-security-experiment-id', result.id); } catch (_) { /* Store only an ID, never credentials or evidence. */ }
    state.experimentCaseTitle = state.case.title || 'Hồ sơ tùy chỉnh';
    renderExperiment({ ...result, completed: 0, failed: 0, runs: [], download_ready: false });
    state.experimentStarting = false;
    await pollExperiment(result.id);
  } catch (error) {
    $('#experiment-error').textContent = `Không bắt đầu được thực nghiệm: ${error.message}`;
  } finally {
    state.experimentStarting = false;
    updateExperimentControls();
  }
}

async function downloadExperiment() {
  if (!state.experiment?.download_ready) return;
  const button = $('#experiment-download');
  button.disabled = true;
  try {
    const response = await fetch(`/api/experiments/${encodeURIComponent(state.experiment.id)}/download`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = el('a');
    link.href = url;
    link.download = `research-${String(state.experiment.id).replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80)}.zip`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    $('#experiment-error').textContent = `Không tải được dữ liệu: ${error.message}`;
  } finally { updateExperimentControls(); }
}

function bindEvents() {
  $$('.nav-item').forEach((button) => button.addEventListener('click', () => {
    $$('.nav-item').forEach((item) => item.classList.toggle('active', item === button));
    $$('.view').forEach((view) => view.classList.toggle('hidden', view.id !== `${button.dataset.view}-view`));
    $('#page-label').textContent = button.textContent.trim();
    notice('');
    window.scrollTo({ top: 0, behavior: 'auto' });
  }));
  $$('.input-tab').forEach((button) => button.addEventListener('click', () => {
    $$('.input-tab').forEach((item) => { item.classList.toggle('active', item === button); item.setAttribute('aria-selected', String(item === button)); });
    $$('.input-content').forEach((view) => view.classList.toggle('hidden', view.id !== `input-${button.dataset.input}`));
  }));
  $('#case-select').addEventListener('change', (event) => loadCase(event.target.value));
  $('#import-button').addEventListener('click', () => $('#import-file').click());
  $('#import-file').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 1_000_000) throw new Error('Chỉ nhập tệp JSON nhỏ hơn 1 MB.');
      const data = JSON.parse(await file.text());
      setCase(data);
      $('#case-select').value = '';
      notice('Đã nhập hồ sơ JSON. Kiểm tra findings và bằng chứng trước khi sinh báo cáo.', true);
    } catch (error) { notice(`Không nhập được tệp: ${error.message}`); }
    finally { event.target.value = ''; }
  });
  $('#apply-json').addEventListener('click', () => {
    try {
      setCase(JSON.parse($('#json-editor').value));
      $('#case-select').value = '';
      notice('Đã áp dụng hồ sơ JSON.', true);
    } catch (error) { notice(`JSON không hợp lệ: ${error.message}`); }
  });
  $$('.mode-pills button').forEach((button) => button.addEventListener('click', () => {
    $('#grounding-toggle').checked = button.dataset.grounding === 'true';
    $('#rag-toggle').checked = button.dataset.rag === 'true';
    syncMode();
  }));
  $('#grounding-toggle').addEventListener('change', syncMode);
  $('#rag-toggle').addEventListener('change', syncMode);
  $('#provider-select').addEventListener('change', updateProviderHint);
  $('#experiment-repeats').addEventListener('change', updateExperimentControls);
  $('#experiment-start').addEventListener('click', startExperiment);
  $('#experiment-download').addEventListener('click', downloadExperiment);
  $('#experiment-select-case').addEventListener('click', () => $('.nav-item[data-view="workspace"]').click());
  $('#generate-button').addEventListener('click', generate);
  $('#export-md').addEventListener('click', () => { if (state.report?.markdown) download(state.report.markdown, 'text/markdown;charset=utf-8', 'md'); });
  $('#export-json').addEventListener('click', () => { if (state.report) download(JSON.stringify(state.report, null, 2), 'application/json;charset=utf-8', 'json'); });
}

async function init() {
  bindEvents();
  const results = await Promise.allSettled([api('/api/health'), api('/api/cases'), api('/api/knowledge')]);
  const [health, cases, knowledge] = results;
  if (health.status === 'fulfilled') {
    state.health = health.value;
    $('#connection-dot').classList.remove('pending');
    $('#connection-status').textContent = health.value.llm_configured ? `${health.value.llm_backend === 'gemini' ? 'Gemini' : 'LLM'} đã cấu hình · chưa xác minh kết nối` : 'API hoạt động · Gemini chưa cấu hình';
    $('#stat-chunks').textContent = health.value.corpus_chunks ?? '—';
    const option = $('#provider-select option[value="llm"]');
    if (health.value.llm_configured) {
      option.disabled = false;
      option.textContent = `${health.value.llm_backend === 'gemini' ? 'Gemini API' : 'LLM'} · ${health.value.llm_model || 'model đã cấu hình'}`;
      $('#provider-select').value = 'llm';
    }
  } else {
    $('#connection-dot').classList.remove('pending');
    $('#connection-dot').classList.add('offline');
    $('#connection-status').textContent = 'API chưa kết nối';
  }
  updateProviderHint();
  updateExperimentControls();
  if (knowledge.status === 'fulfilled') renderKnowledge(knowledge.value);
  else $('#knowledge-sources').append(el('p', 'empty-input', `Không tải được thư viện: ${knowledge.reason.message}`));
  if (cases.status === 'fulfilled') {
    const list = Array.isArray(cases.value) ? cases.value : cases.value.cases || [];
    const select = $('#case-select');
    select.replaceChildren();
    const custom = el('option', '', 'Hồ sơ tùy chỉnh / nhập JSON');
    custom.value = '';
    select.append(custom);
    for (const item of list) {
      const option = el('option', '', item.title || item.id);
      option.value = item.id;
      select.append(option);
    }
    if (list.length) {
      select.value = list[0].id;
      await loadCase(list[0].id);
    } else $('#case-description').textContent = 'Chưa có hồ sơ mẫu. Nhập findings bằng JSON để bắt đầu.';
  } else {
    $('#case-select').replaceChildren(el('option', '', 'Không tải được hồ sơ'));
    notice(`Không tải được dữ liệu: ${cases.reason.message}`);
  }
  try {
    const savedId = localStorage.getItem('db-security-experiment-id');
    if (savedId && /^[A-Za-z0-9_-]{1,100}$/.test(savedId)) {
      state.experiment = { id: savedId, status: 'queued', download_ready: false };
      updateExperimentControls();
      await pollExperiment(savedId);
    }
  } catch (_) { /* Progress recovery is optional when browser storage is disabled. */ }
}

init().catch((error) => notice(`Không khởi tạo được giao diện: ${error.message}`));
