(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const state = { route: 'home', agents: [], projects: [], project: null, conversation: null, voices: [] };
  const titles = {
    home: ['INTELLIGENCE OPERATIONS', 'Command center'], chat: ['AI STUDIO', 'Chat'],
    voice: ['AI STUDIO', 'Live voice'], agents: ['AGENT INTELLIGENCE', 'Agent center'],
    research: ['GLOBAL INTELLIGENCE', 'Research center'], workspace: ['DEVELOPMENT', 'Workspace'],
    more: ['TITAN ECOSYSTEM', 'More'], skills: ['LEARNING SYSTEM', 'Skill factory'],
    models: ['MODEL INTELLIGENCE', 'Models & translation'], workflows: ['AUTONOMOUS EXECUTION', 'Workflows'],
    security: ['TRUST ARCHITECTURE', 'Security center']
  };

  async function api(path, options = {}) {
    const config = { ...options, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) } };
    const response = await fetch(path, config);
    const type = response.headers.get('content-type') || '';
    const body = type.includes('json') ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof body === 'object' ? body.detail : body;
      throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
    }
    return body;
  }
  const json = method => (path, data) => api(path, { method, body: JSON.stringify(data) });
  const post = json('POST'), put = json('PUT'), patch = json('PATCH');
  function esc(value) { const node = document.createElement('div'); node.textContent = String(value ?? ''); return node.innerHTML; }
  function toast(message, error = false) { const el = $('#toast'); el.textContent = message; el.className = `toast${error ? ' error' : ''}`; el.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.hidden = true; }, 5000); }
  function status(value) { return `<span class="status ${esc(value)}">${esc(String(value || 'unknown').replaceAll('_', ' '))}</span>`; }
  function empty(text) { return `<div class="empty">${esc(text)}</div>`; }
  function busy(form, value = true) { $$('button,input,textarea,select', form).forEach(el => { el.disabled = value; }); }
  function setNotice(text) { const el = $('#notice'); el.textContent = text || ''; el.hidden = !text; }
  function fmtDate(value) { if (!value) return 'n/a'; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString(); }

  async function navigate(route) {
    if (!titles[route]) route = 'home';
    state.route = route;
    if (location.hash !== `#${route}`) history.replaceState(null, '', `#${route}`);
    $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.route === route));
    $('#route-eyebrow').textContent = titles[route][0]; $('#route-title').textContent = titles[route][1];
    const template = $(`#${route}-template`);
    const view = $('#view'); view.replaceChildren(template.content.cloneNode(true));
    $$('[data-go]', view).forEach(button => button.addEventListener('click', () => navigate(button.dataset.go)));
    setNotice('');
    try { await loaders[route](); } catch (error) { toast(error.message, true); }
  }

  const loaders = {
    async home() {
      const [system, capabilities] = await Promise.all([api('/api/v1/system'), api('/api/v1/capabilities')]);
      $('#env-label').textContent = system.environment; $('#mode-badge').textContent = system.environment.toUpperCase();
      const labels = { agents: 'Registered agents', research_tasks: 'Research tasks', projects: 'Projects', workflows: 'Workflow runs' };
      $('#metrics').innerHTML = Object.entries(system.counts).map(([key, value]) => `<div class="metric"><strong>${esc(value)}</strong><span>${esc(labels[key])}</span></div>`).join('');
      const groups = [['implemented', '✓', ''], ['partial', '◐', 'partial'], ['blocked', '×', 'blocked']];
      $('#capability-list').innerHTML = groups.flatMap(([key, icon, cls]) => {
        const value = capabilities[key];
        const entries = Array.isArray(value) ? value.map(x => [x.replaceAll('_', ' '), 'Verified in development core']) : Object.entries(value).map(([x, y]) => [x.replaceAll('_', ' '), y]);
        return entries.map(([name, detail]) => `<div class="capability-item ${cls}"><span class="capability-icon">${icon}</span><div><strong>${esc(name)}</strong><small>${esc(detail)}</small></div></div>`);
      }).join('');
    },

    async research() {
      const [history, connectors] = await Promise.all([api('/api/v1/research/tasks'), api('/api/v1/research/connectors')]);
      $('#research-history').innerHTML = history.length ? history.map(task => `<div class="list-item clickable" data-research="${task.id}"><strong>${esc(task.query)}</strong><div class="list-meta">${status(task.status)}<span>${fmtDate(task.created_at)}</span></div></div>`).join('') : empty('No research tasks yet. Run the first real query.');
      $$('[data-research]').forEach(el => el.addEventListener('click', () => showResearch(el.dataset.research)));
      $('#connector-list').innerHTML = connectors.map(c => `<div class="list-item"><strong>${esc(c.id)} ${status(c.access)}</strong><p>Version ${esc(c.version)} · ${esc(c.content_trust)}</p></div>`).join('');
      $('#research-form').addEventListener('submit', async event => {
        event.preventDefault(); const form = event.currentTarget; busy(form);
        const connectors = $$('input[name=connector]:checked', form).map(x => x.value);
        if (!connectors.length) { toast('Select at least one connector', true); busy(form, false); return; }
        const active = $('#research-active'); active.hidden = false; active.innerHTML = '<section class="panel"><h3>Research running…</h3><p class="muted">Retrieving and verifying official source records.</p></section>';
        try {
          const task = await post('/api/v1/research/tasks', { query: $('#research-query').value, connectors, max_results: Number($('#research-limit').value), wait: true });
          await showResearch(task.id); await loaders.researchHistoryOnly();
        } catch (error) { active.innerHTML = `<section class="panel"><h3>Research failed</h3><p>${esc(error.message)}</p></section>`; }
        finally { busy(form, false); }
      });
    },

    async agents() {
      state.agents = await api('/api/v1/agents');
      $('#agent-select').innerHTML = state.agents.filter(a => a.status === 'active').map(agent => `<label class="check"><input type="checkbox" value="${agent.id}">${esc(agent.name)}</label>`).join('');
      $('#agent-grid').innerHTML = state.agents.map(agent => `<article class="agent-card"><div class="section-head"><span class="subtle">${esc(agent.role)}</span>${status(agent.status)}</div><h3>${esc(agent.name)}</h3><p>${esc(agent.description)}</p><div class="list-meta"><span>v${esc(agent.version)}</span><span>${agent.tool_permissions.length} tools</span><span>${agent.timeout_seconds}s timeout</span></div>${agent.status === 'tested' ? `<button class="secondary small approve-agent" data-id="${agent.id}">Approve tested agent</button>` : ''}</article>`).join('');
      $$('.approve-agent').forEach(button => button.addEventListener('click', async () => { await post(`/api/v1/agents/${button.dataset.id}/approve`, {}); toast('Agent approved'); await loaders.agents(); }));
      $('#orchestration-form').addEventListener('submit', async event => {
        event.preventDefault(); const form = event.currentTarget;
        const ids = $$('input[type=checkbox]:checked', $('#agent-select')).map(x => x.value);
        if (!ids.length) return toast('Select at least one active agent', true);
        busy(form); const output = $('#orchestration-results'); output.hidden = false; output.innerHTML = '<section class="panel">Agents are executing concurrently…</section>';
        try {
          const result = await post('/api/v1/orchestrations', { objective: $('#agent-objective').value, agent_ids: ids });
          output.innerHTML = `<section class="panel"><div class="section-head"><h3>Execution evidence</h3><span class="subtle">${esc(result.batch_id)}</span></div>${result.tasks.map(taskCard).join('')}</section>`;
        } catch (error) { output.innerHTML = `<section class="panel">${esc(error.message)}</section>`; }
        finally { busy(form, false); }
      });
      $('#new-agent-button').addEventListener('click', () => $('#agent-dialog').showModal());
      $('[data-close=agent-dialog]').addEventListener('click', () => $('#agent-dialog').close());
      $('#agent-form').addEventListener('submit', async event => {
        event.preventDefault(); const form = event.currentTarget; busy(form);
        const fields = new FormData(form);
        try {
          const agent = await post('/api/v1/agents', { name: fields.get('name'), description: fields.get('description'), instructions: fields.get('instructions'), role: fields.get('role'), tool_permissions: ['research.github', 'knowledge.read'], input_schema: { type: 'object' }, output_schema: { type: 'object' } });
          const tested = await post(`/api/v1/agents/${agent.id}/test`, {});
          $('#agent-dialog').close(); toast(tested.status === 'tested' ? 'Contract sandbox passed. Approve from the registry.' : 'Agent tests failed');
          await loaders.agents();
        } catch (error) { toast(error.message, true); } finally { busy(form, false); }
      });
    },

    async chat() {
      const conversations = await api('/api/v1/conversations');
      $('#conversation-list').innerHTML = conversations.length ? conversations.map(c => `<div class="list-item clickable" data-chat="${c.id}"><strong>${esc(c.title)}</strong><p>${c.pinned ? '📌 ' : ''}${fmtDate(c.updated_at)}</p></div>`).join('') : empty('No conversations.');
      $$('[data-chat]').forEach(el => el.addEventListener('click', () => openConversation(el.dataset.chat)));
      $('#new-chat').addEventListener('click', async () => { const c = await post('/api/v1/conversations', { title: 'New chat' }); await loaders.chat(); await openConversation(c.id); });
      $('#message-form').addEventListener('submit', async event => {
        event.preventDefault(); if (!state.conversation) return toast('Create or select a chat first', true);
        const form = event.currentTarget, input = $('#message-input'), content = input.value;
        const controller = new AbortController(); state.chatController = controller;
        busy(form); $('#stop-chat').disabled = false;
        try {
          appendMessage({ role: 'user', content }); input.value = '';
          const response = await fetch(`/api/v1/conversations/${state.conversation.id}/messages/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, route: 'chat' }), signal: controller.signal });
          if (!response.ok) { const error = await response.json(); throw new Error(error.detail || `HTTP ${response.status}`); }
          const article = document.createElement('article'); article.className = 'message assistant'; $('#messages').appendChild(article);
          const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', full = '';
          while (true) {
            const { value, done } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n'); buffer = events.pop();
            for (const block of events) {
              const line = block.split('\n').find(x => x.startsWith('data:')); if (!line) continue;
              const data = JSON.parse(line.slice(5).trim());
              if (data.delta) { full += data.delta; article.textContent = full; $('#messages').scrollTop = $('#messages').scrollHeight; }
              if (data.error) throw new Error(data.detail || data.error);
              if (data.done) { const small = document.createElement('small'); small.textContent = `${data.provider}${data.is_mock ? ' · EXPLICIT MOCK' : ''}`; article.appendChild(small); }
            }
          }
          $('#chat-title').textContent = content.slice(0, 80);
        } catch (error) { if (error.name === 'AbortError') toast('Generation stopped; received partial text is preserved'); else appendMessage({ role: 'assistant', content: `Error: ${error.message}`, status: 'failed' }); }
        finally { busy(form, false); $('#stop-chat').disabled = true; state.chatController = null; input.focus(); }
      });
      $('#stop-chat').addEventListener('click', () => state.chatController?.abort());
      $('#export-chat').addEventListener('click', async () => {
        if (!state.conversation) return;
        const text = await api(`/api/v1/conversations/${state.conversation.id}/export`);
        download(`${state.conversation.title.slice(0, 40)}.md`, text, 'text/markdown');
      });
      if (conversations[0]) await openConversation(conversations[0].id);
    },

    async voice() {
      const status = await api('/api/v1/voice/status');
      const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
      $('#voice-support').textContent = `Backend: ${status.backend_status}. Browser recognition: ${Speech ? 'available' : 'unavailable'}. Speech synthesis: ${'speechSynthesis' in window ? 'available' : 'unavailable'}. Microphone capture: ${navigator.mediaDevices?.getUserMedia ? 'available' : 'unavailable'}.`;
      initVoice(Speech);
    },

    async workspace() {
      state.projects = await api('/api/v1/projects');
      $('#project-list').innerHTML = state.projects.length ? state.projects.map(p => `<button class="chip ${state.project?.id === p.id ? 'active' : ''}" data-project="${p.id}">${esc(p.name)}</button>`).join('') : empty('No projects yet.');
      $$('[data-project]').forEach(el => el.addEventListener('click', () => selectProject(el.dataset.project)));
      $('#new-project').addEventListener('click', async () => {
        const name = prompt('Project name', 'Verified AI Project'); if (!name) return;
        const project = await post('/api/v1/projects', { name, description: 'Created from TITAN workspace', template: 'python' });
        state.project = project; await loaders.workspace(); await selectProject(project.id);
      });
      $('#new-file').addEventListener('click', () => { $('#file-path').disabled = false; $('#file-path').value = ''; $('#code-editor').disabled = false; $('#code-editor').value = ''; $('#save-file').disabled = false; $('#file-path').focus(); });
      $('#save-file').addEventListener('click', async () => {
        if (!state.project) return; const path = $('#file-path').value;
        await put(`/api/v1/projects/${state.project.id}/file`, { path, content: $('#code-editor').value }); toast('File written atomically'); await selectProject(state.project.id);
      });
      $('#terminal-form').addEventListener('submit', async event => {
        event.preventDefault(); if (!state.project) return;
        const form = event.currentTarget, command = $('#terminal-command').value.trim();
        const argv = command.split(/\s+/).filter(Boolean);
        if (!$('#terminal-approval').checked) return toast('Approve the exact command first', true);
        busy(form); $('#terminal-output').textContent = `$ ${command}\n\nExecuting…`;
        try {
          const result = await post('/api/v1/terminal/execute', { project_id: state.project.id, argv, approved: true, timeout_seconds: 15 });
          $('#terminal-output').textContent = `$ ${command}\n\nStatus: ${result.status}\n${result.error || ''}\n${result.output || '(no output)'}`;
        } catch (error) { $('#terminal-output').textContent = error.message; }
        finally { busy(form, false); $('#terminal-approval').checked = false; }
      });
      if (!state.project && state.projects[0]) await selectProject(state.projects[0].id);
      else if (state.project) await selectProject(state.project.id);
    },

    async more() {},

    async skills() {
      const skills = await api('/api/v1/skills');
      $('#skill-grid').innerHTML = skills.length ? skills.map(skill => `<article class="skill-card"><div class="section-head"><span class="subtle">v${esc(skill.version)}</span>${status(skill.status)}</div><h3>${esc(skill.name)}</h3><p>${esc(skill.description)}</p><p>Handler: <code>${esc(skill.handler)}</code> · Executions: ${skill.execution_count}</p><div class="button-row">${skill.status === 'draft' || skill.status === 'test_failed' ? `<button class="secondary small" data-skill-test="${skill.id}">Run sandbox test</button>` : ''}${skill.status === 'tested' ? `<button class="primary small" data-skill-approve="${skill.id}">Approve</button>` : ''}${skill.status === 'active' ? `<button class="primary small" data-skill-run="${skill.id}">Execute</button><button class="secondary small" data-skill-disable="${skill.id}">Disable</button>` : ''}</div><div id="skill-result-${skill.id}"></div></article>`).join('') : empty('No skills yet. Create a draft above.');
      $('#skill-form').addEventListener('submit', async event => { event.preventDefault(); const f = new FormData(event.currentTarget); await post('/api/v1/skills', { name: f.get('name'), description: f.get('description'), handler: f.get('handler') }); toast('Draft skill created'); await loaders.skills(); });
      $$('[data-skill-test]').forEach(b => b.addEventListener('click', async () => { const result = await post(`/api/v1/skills/${b.dataset.skillTest}/test`, {}); toast(result.test_results.passed ? 'Sandbox tests passed' : 'Sandbox tests failed'); await loaders.skills(); }));
      $$('[data-skill-approve]').forEach(b => b.addEventListener('click', async () => { await post(`/api/v1/skills/${b.dataset.skillApprove}/approve`, {}); await loaders.skills(); }));
      $$('[data-skill-disable]').forEach(b => b.addEventListener('click', async () => { await post(`/api/v1/skills/${b.dataset.skillDisable}/disable`, {}); await loaders.skills(); }));
      $$('[data-skill-run]').forEach(b => b.addEventListener('click', async () => {
        const skill = skills.find(s => s.id === b.dataset.skillRun); const samples = { text_stats: { text: 'Verified TITAN skill execution' }, source_summary: { sources: ['https://github.com/NousResearch/hermes-agent'] }, json_keys: { value: { verified: true, source: 'api' } } };
        const result = await post(`/api/v1/skills/${skill.id}/execute`, { input: samples[skill.handler] });
        $(`#skill-result-${skill.id}`).innerHTML = `<pre class="result-box">${esc(JSON.stringify(result.output, null, 2))}</pre>`;
      }));
    },

    async models() {
      const [providers, evaluations] = await Promise.all([api('/api/v1/models/providers'), api('/api/v1/models/evaluations')]);
      $('#provider-list').innerHTML = providers.map(p => `<div class="list-item"><strong>${esc(p.name)}</strong><div class="list-meta">${status(p.available ? 'active' : 'blocked')}${p.mock ? '<span>MOCK</span>' : ''}</div><p>${esc(p.note)}</p></div>`).join('');
      $('#model-calls').innerHTML = evaluations.calls.length ? evaluations.calls.slice(0, 20).map(call => `<div class="list-item"><strong>${esc(call.provider)} / ${esc(call.model)}</strong><div class="list-meta">${status(call.success ? 'succeeded' : 'failed')}<span>${esc(call.task_type)}</span><span>${Math.round(call.latency_ms)} ms</span><span>${call.input_tokens + call.output_tokens} tokens</span>${call.is_mock ? '<span>MOCK</span>' : ''}</div></div>`).join('') : empty('No inference calls recorded.');
      $('#translate-form').addEventListener('submit', async event => { event.preventDefault(); const form = event.currentTarget; busy(form); const f = new FormData(form); try { const result = await post('/api/v1/translate', { source_language: f.get('source'), target_language: f.get('target'), text: f.get('text') }); const box = $('#translation-result'); box.hidden = false; box.innerHTML = `<strong>${esc(result.target_language)}</strong><p>${esc(result.text)}</p><div class="list-meta">${status(result.is_mock ? 'mock' : 'succeeded')}<span>${esc(result.provider)}</span>${result.is_mock ? '<span>NOT A VERIFIED TRANSLATION</span>' : ''}</div>`; } finally { busy(form, false); } });
    },

    async workflows() {
      const workflows = await api('/api/v1/workflows');
      $('#workflow-list').innerHTML = workflows.length ? workflows.map(w => `<div class="list-item"><strong>${esc(w.name)}</strong><p>${w.definition.steps.length} typed steps</p><button class="primary small" data-run-workflow="${w.id}">Run workflow</button></div>`).join('') : empty('No workflows registered.');
      $('#create-workflow').addEventListener('click', async () => { await post('/api/v1/workflows', { name: `Verified workflow ${new Date().toLocaleTimeString()}`, steps: [{ id: 'analyze', type: 'text_stats', config: { text: 'Research before building. Verify every important result.' } }, { id: 'left', type: 'delay', depends_on: ['analyze'], config: { seconds: 0.1 } }, { id: 'right', type: 'delay', depends_on: ['analyze'], config: { seconds: 0.1 } }, { id: 'model', type: 'model', depends_on: ['left', 'right'], config: { prompt: 'Provide a concise execution summary.', provider: 'mock' } }] }); await loaders.workflows(); });
      $$('[data-run-workflow]').forEach(b => b.addEventListener('click', async () => { b.disabled = true; const run = await post(`/api/v1/workflows/${b.dataset.runWorkflow}/runs?wait=true`, {}); $('#workflow-runs').innerHTML = `<section class="panel"><div class="section-head"><h3>Run ${esc(run.id)}</h3>${status(run.status)}</div><pre class="result-box">${esc(JSON.stringify(run.checkpoints, null, 2))}</pre>${run.error ? `<p class="error">${esc(run.error)}</p>` : ''}${run.status === 'failed' || run.status === 'cancelled' ? `<button class="secondary" data-resume="${run.id}">Resume</button>` : ''}</section>`; $$('[data-resume]').forEach(r => r.addEventListener('click', async () => { const resumed = await post(`/api/v1/workflows/runs/${r.dataset.resume}/resume`, {}); toast(`Run ${resumed.status}`); })); }));
    },

    async security() {
      const [facts, audits] = await Promise.all([api('/api/v1/security/center'), api('/api/v1/audit')]);
      $('#security-facts').innerHTML = Object.entries(facts).map(([key, value]) => `<div class="capability-item ${value === false || value === 'not_implemented' ? 'blocked' : ''}"><span class="capability-icon">${value === true ? '✓' : '◐'}</span><div><strong>${esc(key.replaceAll('_', ' '))}</strong><small>${esc(value)}</small></div></div>`).join('');
      $('#audit-list').innerHTML = audits.length ? audits.map(log => `<div class="list-item"><strong>${esc(log.action)}</strong><div class="list-meta">${status(log.status)}<span>${fmtDate(log.created_at)}</span><span>Correlation ${esc(log.correlation_id)}</span></div></div>`).join('') : empty('No audit events recorded.');
    }
  };

  loaders.researchHistoryOnly = async () => {
    const history = await api('/api/v1/research/tasks'); const list = $('#research-history'); if (!list) return;
    list.innerHTML = history.map(task => `<div class="list-item clickable" data-research="${task.id}"><strong>${esc(task.query)}</strong><div class="list-meta">${status(task.status)}<span>${fmtDate(task.created_at)}</span></div></div>`).join('');
    $$('[data-research]').forEach(el => el.addEventListener('click', () => showResearch(el.dataset.research)));
  };

  async function showResearch(id) {
    const data = await api(`/api/v1/research/tasks/${id}`); const active = $('#research-active'); active.hidden = false;
    active.innerHTML = `<section class="panel"><div class="section-head"><div><p class="eyebrow">RESEARCH REPORT</p><h3>${esc(data.task.query)}</h3></div>${status(data.task.status)}</div><div class="button-row"><button class="secondary small" id="download-report">Export report</button><button class="secondary small" id="convert-project">Research → Project</button><button class="secondary small" id="convert-skill">Research → Skill</button><button class="secondary small" id="convert-agent">Research → Agent</button></div><h4>Source coverage</h4><div class="list">${data.sources.map(s => `<div class="list-item"><strong>${esc(s.connector)} ${status(s.status)}</strong><p>${esc(s.error || s.endpoint || '')}</p></div>`).join('')}</div><h4>Findings & source records</h4><div class="list">${data.documents.length ? data.documents.map(d => `<article class="list-item"><strong>${esc(d.title)}</strong><div class="list-meta">${status(d.verification_status)}<span>${fmtDate(d.retrieved_at)}</span></div><p>${esc(d.content)}</p><a class="source-link" href="${esc(d.url)}" target="_blank" rel="noopener noreferrer">${esc(d.url)}</a></article>`).join('') : empty('No documents retrieved. See source failures.')}</div></section>`;
    active.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    $('#download-report').addEventListener('click', async () => download(`research-${id}.md`, await api(`/api/v1/research/tasks/${id}/report`), 'text/markdown'));
    $('#convert-project').addEventListener('click', async () => { const p = await post(`/api/v1/research/tasks/${id}/convert/project`, {}); state.project = p; toast('Real project created with research report'); navigate('workspace'); });
    $('#convert-skill').addEventListener('click', async () => { await post(`/api/v1/research/tasks/${id}/convert/skill`, {}); toast('Draft skill created and sandbox tested'); navigate('skills'); });
    $('#convert-agent').addEventListener('click', async () => { await post(`/api/v1/research/tasks/${id}/convert/agent`, {}); toast('Draft agent created and contract tested'); navigate('agents'); });
  }

  function taskCard(task) { return `<article class="list-item"><div class="section-head"><strong>${esc(state.agents.find(a => a.id === task.agent_id)?.name || task.agent_id)}</strong>${status(task.status)}</div><p>${esc(task.result?.text || task.error || 'No output')}</p><div class="list-meta"><span>${Math.round(task.duration_ms || 0)} ms</span><span>Attempts ${task.attempts}</span>${task.result?.is_mock ? '<span>EXPLICIT MOCK</span>' : ''}</div></article>`; }
  async function openConversation(id) {
    const data = await api(`/api/v1/conversations/${id}`); state.conversation = data.conversation;
    $('#chat-title').textContent = data.conversation.title; $('#export-chat').disabled = false;
    $('#messages').innerHTML = ''; data.messages.forEach(appendMessage); if (!data.messages.length) $('#messages').innerHTML = empty('No messages yet.');
  }
  function appendMessage(message) {
    const emptyEl = $('#messages .empty'); if (emptyEl) emptyEl.remove();
    const article = document.createElement('article'); article.className = `message ${message.role}`;
    article.textContent = message.content;
    const small = document.createElement('small'); small.textContent = message.role === 'user' ? 'You' : `${message.provider || 'System'}${message.is_mock ? ' · EXPLICIT MOCK' : ''}`; article.appendChild(small);
    $('#messages').appendChild(article); $('#messages').scrollTop = $('#messages').scrollHeight;
  }
  async function selectProject(id) {
    state.project = state.projects.find(p => p.id === id) || state.project;
    $$('[data-project]').forEach(el => el.classList.toggle('active', el.dataset.project === id));
    const files = await api(`/api/v1/projects/${id}/files`);
    $('#file-list').innerHTML = files.length ? files.filter(f => f.type === 'file').map(f => `<div class="list-item clickable" data-file="${esc(f.path)}"><strong>${esc(f.path)}</strong><p>${f.size} bytes</p></div>`).join('') : empty('Empty project. Create a file.');
    $$('[data-file]').forEach(el => el.addEventListener('click', async () => { const data = await api(`/api/v1/projects/${id}/file?path=${encodeURIComponent(el.dataset.file)}`); $('#file-path').value = data.path; $('#code-editor').value = data.content; $('#editor-title').textContent = data.path; }));
    $('#file-path').disabled = false; $('#code-editor').disabled = false; $('#new-file').disabled = false; $('#save-file').disabled = false; $('#terminal-command').disabled = false; $('#terminal-form button').disabled = false;
  }
  function download(name, text, type) { const url = URL.createObjectURL(new Blob([text], { type })); const a = document.createElement('a'); a.href = url; a.download = name.replace(/[^a-z0-9._-]/gi, '-'); a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

  function initVoice(Speech) {
    let stream = null, context = null, animation = null, recognition = null;
    const micButton = $('#mic-button'), canvas = $('#waveform'), ctx = canvas.getContext('2d');
    function drawIdle() { ctx.fillStyle = '#0d1219'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.strokeStyle = '#263140'; ctx.beginPath(); ctx.moveTo(0, 90); ctx.lineTo(800, 90); ctx.stroke(); }
    drawIdle();
    async function startMic() {
      if (stream) { stopMic(); return; }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true }); context = new AudioContext(); const analyser = context.createAnalyser(); analyser.fftSize = 1024; context.createMediaStreamSource(stream).connect(analyser); const data = new Uint8Array(analyser.fftSize);
        micButton.classList.add('recording'); $('#mic-state').textContent = 'Microphone live · tap to stop';
        function draw() { analyser.getByteTimeDomainData(data); ctx.fillStyle = '#0d1219'; ctx.fillRect(0, 0, 800, 180); ctx.strokeStyle = '#56c8ef'; ctx.lineWidth = 2; ctx.beginPath(); data.forEach((v, i) => { const x = i / (data.length - 1) * 800, y = v / 255 * 180; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke(); animation = requestAnimationFrame(draw); } draw();
      } catch (error) { toast(`Microphone unavailable: ${error.message}`, true); }
    }
    function stopMic() { if (animation) cancelAnimationFrame(animation); animation = null; stream?.getTracks().forEach(t => t.stop()); stream = null; context?.close(); context = null; micButton.classList.remove('recording'); $('#mic-state').textContent = 'Microphone off'; drawIdle(); }
    micButton.addEventListener('click', startMic);
    $('#speech-to-text').addEventListener('click', () => {
      if (!Speech) return toast('Speech recognition is not supported by this browser', true);
      if (recognition) { recognition.stop(); return; }
      recognition = new Speech(); recognition.lang = navigator.language.startsWith('bn') ? 'bn-BD' : 'en-US'; recognition.interimResults = true; recognition.continuous = true;
      recognition.onresult = event => { let text = ''; for (const result of event.results) text += result[0].transcript; $('#voice-transcript').value = text; };
      recognition.onerror = event => toast(`Recognition error: ${event.error}`, true); recognition.onend = () => { recognition = null; $('#speech-to-text').textContent = 'Start speech recognition'; };
      recognition.start(); $('#speech-to-text').textContent = 'Stop speech recognition';
    });
    $('#speak-transcript').addEventListener('click', () => { const text = $('#voice-transcript').value; if (!text) return toast('Enter or recognize text first', true); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = /[\u0980-\u09FF]/.test(text) ? 'bn-BD' : 'en-US'; speechSynthesis.speak(utterance); });
    $('#stop-voice').addEventListener('click', () => { stopMic(); recognition?.stop(); recognition = null; speechSynthesis.cancel(); });
    window.addEventListener('beforeunload', stopMic, { once: true });
  }

  $$('.nav-item').forEach(button => button.addEventListener('click', () => navigate(button.dataset.route)));
  $('#refresh').addEventListener('click', () => navigate(state.route));
  window.addEventListener('hashchange', () => navigate(location.hash.slice(1)));
  navigate(location.hash.slice(1) || 'home');
})();
