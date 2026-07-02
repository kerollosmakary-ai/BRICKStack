/* === Core State === */
const state = {
  sessionId: 'demo-' + Date.now().toString(36),
  messages: [],
  showThoughts: false,
  ws: null,
  codeBlockId: 0
};

/* === DOM Refs === */
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sidebar = document.getElementById('sidebar');
const statusBadge = document.getElementById('status-badge');
const fileTree = document.getElementById('file-tree');

/* === WebSocket (stub — works offline via demo mode) === */
function connectWS() {
  // In production: wss://your-api.com/ws?session=${state.sessionId}
  console.log('WS connected (demo mode)');
}
connectWS();

/* === Send === */
function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  addBubble('user', text);
  input.value = '';
  showTyping(true);

  // Demo: simulate agent response after 1.5s
  setTimeout(() => {
    showTyping(false);
    demoResponse(text);
  }, 1500);
}

// Send on Shift+Enter
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && e.shiftKey) { e.preventDefault(); sendMessage(); }
});

/* === Bubble Renderer === */
function addBubble(role, content, rawMarkdown) {
  const div = document.createElement('div');
  div.className = `bubble ${role}`;

  if (role === 'assistant') {
    // Parse markdown into rich HTML
    const html = DOMPurify.sanitize(marked.parse(content));
    div.innerHTML = html;

    // Wrap code blocks with locked UI
    div.querySelectorAll('pre code').forEach((codeEl) => {
      const pre = codeEl.parentElement;
      const lang = (codeEl.className.match(/language-(\w+)/) || [])[1] || '';
      wrapCodeBlock(pre, codeEl.textContent, lang);
    });
  } else {
    div.textContent = content;
  }

  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  state.messages.push({ role, content });
}

/* === Locked Code Block Wrapper === */
function wrapCodeBlock(preEl, code, lang) {
  const id = ++state.codeBlockId;
  const wrap = document.createElement('div');
  wrap.className = 'code-block';
  wrap.dataset.blockId = id;
  wrap.dataset.source = code;

  wrap.innerHTML = `
    <div class="header">
      <span>${lang || 'code'}</span>
      <span class="badge" id="badge-${id}">🔒 Locked</span>
      <div class="actions">
        <button onclick="editCodeBlock(${id})">✏️ Edit</button>
        <button onclick="copyCode(${id})">📋 Copy</button>
      </div>
    </div>
    <pre><code class="hljs language-${lang}">${escapeHtml(code)}</code></pre>
    <div class="editor" id="editor-${id}" style="display:none">
      <textarea id="ta-${id}">${escapeHtml(code)}</textarea>
      <div class="save-row">
        <button class="btn-save" onclick="saveCodeBlock(${id})">✅ Save & Re-run</button>
        <button class="btn-cancel" onclick="cancelEdit(${id})">Cancel</button>
      </div>
    </div>
  `;

  preEl.parentElement.replaceChild(wrap, preEl);
  hljs.highlightElement(wrap.querySelector('code'));
}

/* === Edit / Save / Cancel === */
function editCodeBlock(id) {
  const wrap = document.querySelector(`[data-block-id="${id}"]`);
  wrap.querySelector('pre').style.display = 'none';
  wrap.querySelector('.editor').style.display = 'block';
  document.getElementById(`badge-${id}`).textContent = '🔓 Editing';
  document.getElementById(`badge-${id}`).className = 'badge editing';
}

function saveCodeBlock(id) {
  const wrap = document.querySelector(`[data-block-id="${id}"]`);
  const newCode = document.getElementById(`ta-${id}`).value;
  wrap.dataset.source = newCode;
  wrap.querySelector('code').textContent = newCode;
  wrap.querySelector('pre').style.display = 'block';
  wrap.querySelector('.editor').style.display = 'none';
  document.getElementById(`badge-${id}`).textContent = '🔒 Locked';
  document.getElementById(`badge-${id}`).className = 'badge';
  hljs.highlightElement(wrap.querySelector('code'));

  // Simulate re-run
  showTyping(true);
  setTimeout(() => {
    showTyping(false);
    addOutputBlock(`▶ Re-run output:\n${simulateRun(newCode)}`);
  }, 1000);
}

function cancelEdit(id) {
  const wrap = document.querySelector(`[data-block-id="${id}"]`);
  document.getElementById(`ta-${id}`).value = wrap.dataset.source;
  wrap.querySelector('pre').style.display = 'block';
  wrap.querySelector('.editor').style.display = 'none';
  document.getElementById(`badge-${id}`).textContent = '🔒 Locked';
  document.getElementById(`badge-${id}`).className = 'badge';
}

function copyCode(id) {
  const wrap = document.querySelector(`[data-block-id="${id}"]`);
  navigator.clipboard.writeText(wrap.dataset.source);
}

/* === Output Block === */
function addOutputBlock(text) {
  const div = document.createElement('div');
  div.className = 'output-block';
  div.innerHTML = `<div class="header">▶ Output</div><pre>${escapeHtml(text)}</pre>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

/* === Agent Thoughts === */
function addThought(agent, status) {
  const div = document.createElement('div');
  div.className = `thoughts ${state.showThoughts ? 'visible' : ''}`;
  div.textContent = `🧠 ${agent}: ${status}`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function renderThoughts() {
  document.querySelectorAll('.thoughts').forEach(el => {
    el.classList.toggle('visible', state.showThoughts);
  });
}

/* === Typing Indicator === */
function showTyping(show) {
  let el = document.querySelector('.typing');
  if (show) {
    if (!el) {
      el = document.createElement('div');
      el.className = 'typing';
      el.innerHTML = '<span></span><span></span><span></span>';
      chat.appendChild(el);
    }
    statusBadge.textContent = '🔶 Working';
    statusBadge.className = 'badge badge-working';
  } else {
    if (el) el.remove();
    statusBadge.textContent = '🟢 Ready';
    statusBadge.className = 'badge badge-ready';
  }
  chat.scrollTop = chat.scrollHeight;
}

/* === Sidebar === */
function toggleSidebar() {
  sidebar.classList.toggle('hidden');
}

/* === Toolbar helpers === */
function wrapSelection(before, after = before) {
  const start = input.selectionStart, end = input.selectionEnd;
  const text = input.value;
  input.value = text.slice(0, start) + before + text.slice(start, end) + after + text.slice(end);
  input.focus();
  input.selectionStart = input.selectionEnd = end + before.length;
}
function insertAtCursor(text) {
  const pos = input.selectionStart;
  input.value = input.value.slice(0, pos) + text + input.value.slice(pos);
  input.focus();
}

/* === Demo Mode === */
function demoResponse(question) {
  const q = question.toLowerCase();
  addThought('Planner', 'Analyzing request...');
  setTimeout(() => {
    addThought('Architect', 'Designing solution structure...');
  }, 300);
  setTimeout(() => {
    addThought('Coder', 'Writing code...');
  }, 600);
  setTimeout(() => {
    addThought('Terminal', 'Running in sandbox...');
  }, 900);

  const code = `import os
import sys

def main():
    path = "."
    files = [f for f in os.listdir(path) if os.path.isfile(f)]
    print(f"Found {len(files)} files in current directory")
    for f in files:
        size = os.path.getsize(f)
        print(f"  {f} ({size} bytes)")

if __name__ == "__main__":
    main()`;

  setTimeout(() => {
    const md = `Here's a Python script that counts files in the current directory:

\`\`\`python
${code}
\`\`\`

When you run it:

\`\`\`
Found 8 files
  main.py (320 bytes)
  requirements.txt (45 bytes)
  README.md (1280 bytes)
  ...
\`\`\`

**Explanation:** The script uses \`os.listdir()\` to get all entries, filters for files only with \`os.path.isfile()\`, then prints each filename with its size.`;
    addBubble('assistant', md);
  }, 1500);
}

function simulateRun(code) {
  // Extract print statements from code for demo
  const prints = code.match(/print\([^)]+\)/g) || [];
  return prints.map(p => {
    // Simple eval of print expressions for demo
    if (p.includes('len(files)')) return 'Found 8 files in current directory';
    if (p.includes('f} (')) return '  main.py (320 bytes)';
    if (p.includes('{f}')) return '';
    return p.replace(/^print\(['"]?(.*?)['"]?\)$/, '$1');
  }).filter(Boolean).join('\n');
}

/* === Helpers === */
function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* === PWA: Register Service Worker === */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then(() => {
      console.log('SW registered');
    });
  });
}

/* === Keyboard shortcut === */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') sidebar.classList.add('hidden');
});

/* === Boot message === */
setTimeout(() => {
  addBubble('system', '🧱 BRICKStack Studio ready — 3 agents online (Architect, Coder, Terminal)');
}, 300);
