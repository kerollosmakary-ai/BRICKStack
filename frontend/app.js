/* BRICKStack Frontend */

(function() {
  'use strict';

  const state = {
    ws: null, connected: false, reconnectAttempts: 0, maxReconnect: 5,
    messages: [], currentTaskId: null, streamingBuffers: new Map(),
    editingCode: null, fileTree: [],
    agentStatus: { planner: 'idle', coder: 'idle', terminal: 'idle', reviewer: 'idle', writer: 'idle' }
  };

  const els = {
    chatInput: $('chat-input'), sendBtn: $('send-btn'), messages: $('messages'),
    chatContainer: $('chat-container'), fileTree: $('file-tree'),
    connectionStatus: $('connection-status'), sidebar: $('sidebar'),
    menuToggle: $('menu-toggle'), toggleSidebar: $('toggle-sidebar'),
    clearChat: $('clear-chat'), newChat: $('new-chat'),
  };

  function $(id) { return document.getElementById(id); }

  // ── WebSocket ──────────────────────────────────────────────────
  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host.includes('localhost:8000') ? 'localhost:8000' : window.location.host;
    const url = `${protocol}//${host}/ws`;

    updateConnection('connecting', 'Connecting...');

    try {
      state.ws = new WebSocket(url);
    } catch (e) {
      updateConnection('offline', 'Failed to connect');
      return;
    }

    state.ws.onopen = () => {
      state.connected = true; state.reconnectAttempts = 0;
      updateConnection('online', 'Connected');
      els.sendBtn.disabled = !els.chatInput.value.trim();
      send({ type: 'list_files', task_id: 'system' });
    };

    state.ws.onmessage = (event) => {
      try { handleMessage(JSON.parse(event.data)); } catch (e) { console.error('Invalid message:', event.data); }
    };

    state.ws.onclose = () => {
      state.connected = false;
      updateConnection('offline', 'Disconnected');
      els.sendBtn.disabled = true;
      if (state.reconnectAttempts < state.maxReconnect) {
        state.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, state.reconnectAttempts), 10000);
        updateConnection('connecting', `Reconnecting in ${delay/1000}s...`);
        setTimeout(connect, delay);
      } else {
        updateConnection('offline', 'Connection failed. Refresh to retry.');
      }
    };

    state.ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      updateConnection('offline', 'Connection error');
    };
  }

  function send(data) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) { console.warn('WebSocket not ready'); return false; }
    state.ws.send(JSON.stringify(data));
    return true;
  }

  function updateConnection(status, text) {
    const dot = els.connectionStatus.querySelector('.status-dot');
    const label = els.connectionStatus.querySelector('.status-label');
    dot.className = 'status-dot ' + status;
    label.textContent = text;
  }

  // ── Message Handling ───────────────────────────────────────────
  function handleMessage(msg) {
    const type = msg.type;
    const taskId = msg.task_id || msg.taskId || 'unknown';

    switch (type) {
      case 'thought': renderThought(msg); updateAgentStatus(msg.agent, 'done'); break;
      case 'code': renderCodeChunk(msg); updateAgentStatus('coder', 'running'); break;
      case 'terminal': renderTerminal(msg); updateAgentStatus('terminal', 'done'); break;
      case 'assistant': renderAssistantChunk(msg); updateAgentStatus('writer', 'running'); break;
      case 'review': renderReview(msg); updateAgentStatus('reviewer', 'done'); break;
      case 'file_tree': renderFileTree(msg.files || []); break;
      case 'done': finishTask(taskId); break;
      case 'error': renderError(msg); finishTask(taskId); break;
      default: console.log('Unknown type:', type, msg);
    }
  }

  // ── Rendering ──────────────────────────────────────────────────
  function createEl(className, html) {
    const el = document.createElement('div');
    el.className = 'msg ' + className;
    el.innerHTML = html;
    return el;
  }

  function scrollToBottom() { els.chatContainer.scrollTo({ top: els.chatContainer.scrollHeight, behavior: 'smooth' }); }
  function removeWelcome() { const w = els.messages.querySelector('.welcome'); if (w) w.remove(); }

  function renderUserMessage(text) {
    removeWelcome();
    els.messages.appendChild(createEl('user', `
      <div class="msg-avatar">U</div>
      <div class="msg-content">${escapeHtml(text)}</div>
    `));
    scrollToBottom();
  }

  function renderThought(msg) {
    const agent = msg.agent || 'AI';
    const content = msg.content || '';
    els.messages.appendChild(createEl('thought', `
      <div class="msg-content">${escapeHtml(agent)}: ${escapeHtml(content.substring(0, 200))}</div>
    `));
    scrollToBottom();
  }

  function renderCodeChunk(msg) {
    const taskId = msg.task_id;
    const chunk = msg.chunk || '';

    let container = state.streamingBuffers.get('code-' + taskId);

    if (!container) {
      removeWelcome();
      const el = createEl('ai', `
        <div class="msg-avatar">C</div>
        <div class="msg-content" style="width:100%; max-width:100%; padding:0; background:transparent; border:none;">
          <div class="code-block" id="code-${taskId}">
            <div class="code-header">
              <span class="code-lang">Python</span>
              <div class="code-actions">
                <button class="code-btn" onclick="copyCode('${taskId}')">Copy</button>
                <button class="code-btn" onclick="editCode('${taskId}')">Edit</button>
                <button class="code-btn" onclick="rerunCode('${taskId}')">Run</button>
              </div>
            </div>
            <div class="code-content"><pre><code id="code-text-${taskId}"></code><span class="streaming-cursor"></span></pre></div>
          </div>
        </div>
      `);
      els.messages.appendChild(el);
      container = {
        element: el.querySelector('#code-text-' + taskId),
        text: '', taskId: taskId,
      };
      state.streamingBuffers.set('code-' + taskId, container);
    }

    container.text += chunk;
    container.element.textContent = container.text;
    scrollToBottom();
  }

  function renderTerminal(msg) {
    const content = msg.content || '';
    const isError = content.includes('Error') || content.includes('Traceback');
    els.messages.appendChild(createEl('ai', `
      <div class="msg-avatar">T</div>
      <div class="msg-content" style="width:100%; max-width:100%; padding:0; background:transparent; border:none;">
        <div class="terminal-block">
          <div class="terminal-header">
            <div class="terminal-dots"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span></div>
            <span class="terminal-title">Terminal</span>
          </div>
          <div class="terminal-content ${isError ? 'error' : ''}">${escapeHtml(content)}</div>
        </div>
      </div>
    `));
    scrollToBottom();
  }

  function renderAssistantChunk(msg) {
    const taskId = msg.task_id;
    const chunk = msg.chunk || '';

    let container = state.streamingBuffers.get('assistant-' + taskId);

    if (!container) {
      const el = createEl('ai', `
        <div class="msg-avatar">A</div>
        <div class="msg-content" id="assistant-${taskId}"><span class="streaming-cursor"></span></div>
      `);
      els.messages.appendChild(el);
      container = {
        element: el.querySelector('.msg-content'),
        text: '', taskId: taskId,
      };
      state.streamingBuffers.set('assistant-' + taskId, container);
    }

    container.text += chunk;
    container.element.innerHTML = simpleMarkdown(container.text) + '<span class="streaming-cursor"></span>';
    scrollToBottom();
  }

  function renderReview(msg) {
    const review = msg.review || msg.content || {};
    const ok = review.review_ok || false;
    const issues = review.issues || [];
    els.messages.appendChild(createEl('ai', `
      <div class="msg-avatar">R</div>
      <div class="msg-content">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
          <span style="font-size:12px; font-weight:600; color:${ok ? 'var(--success)' : 'var(--warning)'};">
            ${ok ? 'Review Passed' : 'Issues Found'}
          </span>
        </div>
        ${issues.length > 0 ? `
          <ul style="margin:0; padding-left:18px; font-size:13px;">
            ${issues.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
          </ul>
        ` : '<p style="font-size:13px; color:var(--text-secondary); margin:0;">No issues detected.</p>'}
      </div>
    `));
    scrollToBottom();
  }

  function renderError(msg) {
    els.messages.appendChild(createEl('error', `
      <div class="msg-avatar">!</div>
      <div class="msg-content">
        <strong style="font-size:13px; color:var(--error);">Error</strong>
        <p style="margin:6px 0 0; font-size:13px; color:var(--text-secondary);">${escapeHtml(msg.content || 'Unknown error')}</p>
      </div>
    `));
    scrollToBottom();
  }

  function renderFileTree(files) {
    state.fileTree = files;
    if (files.length === 0) {
      els.fileTree.innerHTML = '<div class="empty-state">No files</div>';
      return;
    }
    els.fileTree.innerHTML = files.map(f => `
      <div class="file-item">
        <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
          <polyline points="13 2 13 9 20 9"/>
        </svg>
        <span class="file-name">${escapeHtml(f)}</span>
      </div>
    `).join('');
  }

  function updateAgentStatus(agent, status) {
    if (!agent) return;
    state.agentStatus[agent] = status;
    const el = document.getElementById('status-' + agent);
    if (el) { el.textContent = status; el.className = 'agent-status ' + status; }
  }

  function resetAgentStatus() {
    Object.keys(state.agentStatus).forEach(agent => {
      state.agentStatus[agent] = 'idle';
      const el = document.getElementById('status-' + agent);
      if (el) { el.textContent = 'idle'; el.className = 'agent-status'; }
    });
  }

  function finishTask(taskId) {
    state.streamingBuffers.forEach((buf, key) => {
      if (key.includes(taskId) || key.endsWith(taskId)) {
        const cursor = buf.element.parentElement?.querySelector('.streaming-cursor');
        if (cursor) cursor.remove();
      }
    });
    state.streamingBuffers.delete('code-' + taskId);
    state.streamingBuffers.delete('assistant-' + taskId);
    setTimeout(resetAgentStatus, 500);
  }

  // ── Markdown ─────────────────────────────────────────────────
  function simpleMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/^\d+\. (.*$)/gim, '<li>$1</li>');
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>(<h[123]>)/g, '$1');
    html = html.replace(/(<\/h[123]>)<\/p>/g, '$1');
    return html;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ── Actions ───────────────────────────────────────────────────
  function sendMessage() {
    const text = els.chatInput.value.trim();
    if (!text || !state.connected) return;

    const taskId = 'task-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
    state.currentTaskId = taskId;

    renderUserMessage(text);

    send({
      type: 'user_message', content: text, task_id: taskId,
      user_id: 'web-user', session_context: {}
    });

    els.chatInput.value = '';
    els.chatInput.style.height = 'auto';
    els.sendBtn.disabled = true;

    showTypingIndicator();
    resetAgentStatus();
    updateAgentStatus('planner', 'running');
  }

  function showTypingIndicator() {
    const el = document.createElement('div');
    el.className = 'msg ai';
    el.id = 'typing-indicator';
    el.innerHTML = `
      <div class="msg-avatar">...</div>
      <div class="msg-content">
        <div class="typing-indicator"><span></span><span></span><span></span></div>
      </div>
    `;
    els.messages.appendChild(el);
    scrollToBottom();
  }

  function hideTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
  }

  // ── Global functions ───────────────────────────────────────────
  window.copyCode = function(taskId) {
    const code = state.streamingBuffers.get('code-' + taskId)?.text || '';
    navigator.clipboard.writeText(code).then(() => {
      const btn = document.querySelector(`#code-${taskId} .code-btn`);
      if (btn) { btn.textContent = 'Copied'; btn.classList.add('copied'); setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000); }
    });
  };

  window.editCode = function(taskId) {
    const block = document.querySelector('#code-' + taskId);
    if (!block) return;
    const contentDiv = block.querySelector('.code-content');
    const currentCode = state.streamingBuffers.get('code-' + taskId)?.text || '';
    contentDiv.innerHTML = `<textarea class="code-edit" id="edit-${taskId}">${escapeHtml(currentCode)}</textarea>`;
    const actions = block.querySelector('.code-actions');
    actions.innerHTML = `
      <button class="code-btn" onclick="saveCode('${taskId}')">Save & Run</button>
      <button class="code-btn" onclick="cancelEdit('${taskId}', '${escapeHtml(currentCode).replace(/'/g, "\\'")}')">Cancel</button>
    `;
    state.editingCode = taskId;
  };

  window.saveCode = function(taskId) {
    const textarea = document.querySelector('#edit-' + taskId);
    if (!textarea) return;
    const newCode = textarea.value;
    let buf = state.streamingBuffers.get('code-' + taskId);
    if (!buf) {
      buf = { text: newCode, element: null, taskId };
      state.streamingBuffers.set('code-' + taskId, buf);
    } else { buf.text = newCode; }
    const block = document.querySelector('#code-' + taskId);
    const contentDiv = block.querySelector('.code-content');
    contentDiv.innerHTML = `<pre><code id="code-text-${taskId}">${escapeHtml(newCode)}</code></pre>`;
    const actions = block.querySelector('.code-actions');
    actions.innerHTML = `
      <button class="code-btn" onclick="copyCode('${taskId}')">Copy</button>
      <button class="code-btn" onclick="editCode('${taskId}')">Edit</button>
      <button class="code-btn" onclick="rerunCode('${taskId}')">Run</button>
    `;
    state.editingCode = null;
    send({ type: 'edit_code', code: newCode, task_id: 'rerun-' + Date.now(), content: 'Re-running edited code' });
    updateAgentStatus('terminal', 'running');
  };

  window.cancelEdit = function(taskId, originalCode) {
    const block = document.querySelector('#code-' + taskId);
    const contentDiv = block.querySelector('.code-content');
    contentDiv.innerHTML = `<pre><code id="code-text-${taskId}">${originalCode}</code></pre>`;
    const actions = block.querySelector('.code-actions');
    actions.innerHTML = `
      <button class="code-btn" onclick="copyCode('${taskId}')">Copy</button>
      <button class="code-btn" onclick="editCode('${taskId}')">Edit</button>
      <button class="code-btn" onclick="rerunCode('${taskId}')">Run</button>
    `;
    state.editingCode = null;
  };

  window.rerunCode = function(taskId) {
    const code = state.streamingBuffers.get('code-' + taskId)?.text || '';
    if (!code) return;
    send({ type: 'edit_code', code: code, task_id: 'rerun-' + Date.now(), content: 'Re-running code' });
    updateAgentStatus('terminal', 'running');
  };

  // ── Event Listeners ────────────────────────────────────────────
  els.sendBtn.addEventListener('click', sendMessage);
  els.chatInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  els.chatInput.addEventListener('input', () => {
    els.sendBtn.disabled = !els.chatInput.value.trim() || !state.connected;
    els.chatInput.style.height = 'auto';
    els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 100) + 'px';
  });
  els.clearChat.addEventListener('click', () => {
    els.messages.innerHTML = buildWelcome();
    bindSuggestions();
    state.messages = [];
    state.streamingBuffers.clear();
  });
  els.newChat.addEventListener('click', () => els.clearChat.click());
  els.menuToggle.addEventListener('click', () => els.sidebar.classList.toggle('open'));
  els.toggleSidebar.addEventListener('click', () => els.sidebar.classList.toggle('collapsed'));

  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && els.sidebar.classList.contains('open')) {
      if (!els.sidebar.contains(e.target) && !els.menuToggle.contains(e.target)) {
        els.sidebar.classList.remove('open');
      }
    }
  });

  function buildWelcome() {
    return `
      <div class="welcome">
        <div class="welcome-logo">
          <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
            <rect x="6" y="6" width="36" height="36" rx="4"/>
            <path d="M6 18h36M18 42V18"/>
          </svg>
        </div>
        <h2>BRICKStack</h2>
        <p>AI-powered coding pipeline. Write, execute, and review code.</p>
        <div class="suggestions">
          <button class="suggestion" data-prompt="Write a Python function to reverse a string">
            <span class="suggestion-label">Reverse a string</span>
            <span class="suggestion-desc">Python function</span>
          </button>
          <button class="suggestion" data-prompt="Build a CLI calculator with add, subtract, multiply, divide">
            <span class="suggestion-label">CLI Calculator</span>
            <span class="suggestion-desc">Python script</span>
          </button>
          <button class="suggestion" data-prompt="Create a Flask API with CRUD endpoints for a todo list">
            <span class="suggestion-label">Flask API</span>
            <span class="suggestion-desc">REST endpoints</span>
          </button>
          <button class="suggestion" data-prompt="Write a web scraper using requests and BeautifulSoup">
            <span class="suggestion-label">Web Scraper</span>
            <span class="suggestion-desc">Data extraction</span>
          </button>
        </div>
      </div>
    `;
  }

  function bindSuggestions() {
    document.querySelectorAll('.suggestion').forEach(btn => {
      btn.addEventListener('click', () => {
        els.chatInput.value = btn.dataset.prompt;
        els.sendBtn.disabled = false;
        els.chatInput.focus();
      });
    });
  }

  // ── Mobile Keyboard ────────────────────────────────────────────
  function handleKeyboard() {
    const vh = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    const isOpen = vh < window.innerHeight * 0.75;
    document.body.classList.toggle('keyboard-open', isOpen);
    if (isOpen) setTimeout(() => els.chatContainer.scrollTo({ top: els.chatContainer.scrollHeight, behavior: 'smooth' }), 100);
  }
  if (window.visualViewport) window.visualViewport.addEventListener('resize', handleKeyboard);
  window.addEventListener('resize', handleKeyboard);

  els.chatContainer.addEventListener('click', (e) => {
    if (e.target === els.chatContainer || e.target === els.messages) els.chatInput.focus();
  });

  // ── Initialize ─────────────────────────────────────────────────
  bindSuggestions();
  connect();
  setTimeout(() => els.chatInput.focus(), 100);
})();
