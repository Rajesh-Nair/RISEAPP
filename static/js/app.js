(function () {
  const API = '/api';
  const main = document.getElementById('main');
  const navLinks = document.querySelectorAll('.nav-links a');

  function setActiveNav(page) {
    navLinks.forEach(a => {
      a.classList.toggle('active', (a.getAttribute('data-page') || '').startsWith(page));
    });
  }

  async function api(path, options = {}) {
    const res = await fetch(API + path, {
      headers: options.headers || {},
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || err.message || res.statusText);
    }
    if (res.headers.get('content-type')?.includes('application/json')) return res.json();
    return res;
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  // --- Upload view ---
  function renderUpload() {
    setActiveNav('upload');
    main.innerHTML = `
      <h1>Upload & Process</h1>
      <div class="card">
        <h2>Upload PDF</h2>
        <p class="text-muted" style="color:var(--text-muted);margin-bottom:1rem;">Choose Policy (external) or Rules (internal), then select a PDF.</p>
        <form id="upload-form">
          <div class="form-group">
            <label>Document type</label>
            <select name="doc_type" required>
              <option value="external">Policy (external)</option>
              <option value="internal">Rules (internal)</option>
            </select>
          </div>
          <div class="form-group">
            <label>PDF file</label>
            <input type="file" name="file" accept=".pdf" required />
          </div>
          <button type="submit" class="btn btn-primary">Upload</button>
        </form>
        <div id="upload-msg"></div>
      </div>
      <div class="card">
        <h2>Run pipeline</h2>
        <p style="color:var(--text-muted);margin-bottom:0.5rem;">After upload, run each step. If already processed, you can force reprocess.</p>
        <div class="process-actions">
          <button type="button" class="btn btn-secondary" data-process="1">Process 1: Convert</button>
          <button type="button" class="btn btn-secondary" data-process="2">Process 2: Chunk & Store</button>
          <button type="button" class="btn btn-secondary" data-process="3">Process 3: Lineage</button>
        </div>
        <div id="process-msg"></div>
        <div id="force-prompt" class="force-prompt" style="display:none;">
          <span id="force-text"></span>
          <button type="button" class="btn btn-primary btn-sm" id="force-yes">Yes, force</button>
          <button type="button" class="btn btn-secondary btn-sm" id="force-cancel">Cancel</button>
        </div>
      </div>
    `;

    const form = document.getElementById('upload-form');
    const uploadMsg = document.getElementById('upload-msg');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const file = form.querySelector('input[name="file"]').files[0];
      if (!file) { uploadMsg.innerHTML = '<div class="msg msg-error">Select a PDF file.</div>'; return; }
      fd.set('file', file);
      uploadMsg.innerHTML = '<div class="msg msg-info">Uploading…</div>';
      try {
        const res = await fetch(API + '/upload', { method: 'POST', body: fd });
        const data = await res.json();
        uploadMsg.innerHTML = '<div class="msg msg-success">Uploaded: ' + escapeHtml(data.path) + '</div>';
        form.reset();
      } catch (err) {
        uploadMsg.innerHTML = '<div class="msg msg-error">' + escapeHtml(err.message) + '</div>';
      }
    });

    let pendingForce = null;
    document.querySelectorAll('[data-process]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const num = btn.getAttribute('data-process');
        const processMsg = document.getElementById('process-msg');
        const forcePrompt = document.getElementById('force-prompt');
        const forceText = document.getElementById('force-text');
        const forceYes = document.getElementById('force-yes');
        const forceCancel = document.getElementById('force-cancel');
        forcePrompt.style.display = 'none';
        processMsg.innerHTML = '<div class="msg msg-info">Running process ' + num + '…</div>';
        try {
          const body = pendingForce === num ? { force: true } : { force: false };
          const res = await fetch(API + '/process/' + num, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          const data = await res.json();
          if (data.status === 'already_processed' && data.force_available) {
            processMsg.innerHTML = '<div class="msg msg-warning">' + escapeHtml(data.message) + '</div>';
            forceText.textContent = 'Force reprocess?';
            pendingForce = num;
            forcePrompt.style.display = 'flex';
          } else {
            processMsg.innerHTML = '<div class="msg msg-success">Process ' + num + ' completed.</div>';
            pendingForce = null;
          }
        } catch (err) {
          processMsg.innerHTML = '<div class="msg msg-error">' + escapeHtml(err.message) + '</div>';
          pendingForce = null;
        }
      });
    });
    document.getElementById('force-yes').addEventListener('click', () => {
      const btn = document.querySelector('[data-process="' + pendingForce + '"]');
      if (btn) btn.click();
    });
    document.getElementById('force-cancel').addEventListener('click', () => {
      document.getElementById('force-prompt').style.display = 'none';
      pendingForce = null;
    });
  }

  // --- Documents list ---
  function renderDocuments(type) {
    setActiveNav('documents');
    const typeLabel = type === 'external' ? 'External (policy)' : type === 'internal' ? 'Internal (rules)' : 'All';
    main.innerHTML = `
      <h1>Documents</h1>
      <div class="tabs">
        <button type="button" class="tab ${!type ? 'active' : ''}" data-type="">All</button>
        <button type="button" class="tab ${type === 'external' ? 'active' : ''}" data-type="external">External (policy)</button>
        <button type="button" class="tab ${type === 'internal' ? 'active' : ''}" data-type="internal">Internal (rules)</button>
      </div>
      <div id="doc-list">Loading…</div>
    `;
    document.querySelectorAll('.tab').forEach(t => {
      t.addEventListener('click', () => { location.hash = '#documents' + (t.getAttribute('data-type') ? '/' + t.getAttribute('data-type') : ''); });
    });
    const listEl = document.getElementById('doc-list');
    api('/documents' + (type ? '?doc_type=' + type : ''))
      .then(docs => {
        if (!docs.length) { listEl.innerHTML = '<p class="msg msg-info">No documents.</p>'; return; }
        listEl.innerHTML = '<div class="table-wrap"><table><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Actions</th></tr></thead><tbody></tbody></table></div>';
        const tbody = listEl.querySelector('tbody');
        docs.forEach(d => {
          const status = [];
          if (d.converted_at) status.push('<span class="badge badge-ok">Converted</span>'); else status.push('<span class="badge badge-pending">Not converted</span>');
          if (d.chunked_at) status.push('<span class="badge badge-ok">Chunked</span>'); else status.push('<span class="badge badge-pending">Not chunked</span>');
          const row = document.createElement('tr');
          row.innerHTML = `
            <td>${escapeHtml(d.name)}</td>
            <td><span class="badge badge-${d.doc_type}">${escapeHtml(d.doc_type)}</span></td>
            <td>${status.join(' ')}</td>
            <td>
              <a href="#view/${d.id}" class="btn btn-primary btn-sm">View</a>
              ${d.has_pdf ? '<a href="' + API + '/documents/' + d.id + '/content?format=pdf" class="btn btn-secondary btn-sm" download>Download PDF</a>' : ''}
            </td>
          `;
          tbody.appendChild(row);
        });
      })
      .catch(err => { listEl.innerHTML = '<div class="msg msg-error">' + escapeHtml(err.message) + '</div>'; });
  }

  // --- View document (content + chunks) ---
  function renderView(id) {
    setActiveNav('documents');
    main.innerHTML = '<div class="loading">Loading document…</div>';
    Promise.all([
      api('/documents').then(docs => docs.find(x => x.id === parseInt(id, 10))),
      api('/documents/' + id + '/chunks').catch(() => []),
    ]).then(([doc, chunks]) => {
      if (!doc) { main.innerHTML = '<div class="msg msg-error">Document not found.</div>'; return; }
      renderViewWithDoc(doc, chunks);
    }).catch(e => {
      main.innerHTML = '<div class="msg msg-error">' + escapeHtml(e.message) + '</div>';
    });
  }

  function renderViewWithDoc(doc, chunks) {
    const docId = doc.id;
    const name = doc.name || 'Document ' + docId;
    const formatTabs = [];
    if (doc.has_html) formatTabs.push('<button type="button" class="tab format-tab active" data-format="html">HTML</button>');
    if (doc.has_md) formatTabs.push('<button type="button" class="tab format-tab" data-format="md">Markdown</button>');
    main.innerHTML = `
      <div class="breadcrumb">
        <a href="#documents">Documents</a> → ${escapeHtml(name)}
      </div>
      <h1>${escapeHtml(name)}</h1>
      <div class="card">
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.75rem;margin-bottom:1rem;">
          ${formatTabs.join('')}
          ${doc.has_pdf ? '<a href="' + API + '/documents/' + docId + '/content?format=pdf" class="btn btn-secondary btn-sm" download>Download PDF</a>' : ''}
        </div>
        <div class="content-panel">
          <iframe id="content-frame" title="Document content" src="${API}/documents/${docId}/content?format=${doc.has_html ? 'html' : 'md'}"></iframe>
        </div>
      </div>
      <div class="card">
        <h2>Chunks & linked lineage</h2>
        <div id="chunks-container">Loading chunks…</div>
      </div>
    `;
    const frame = document.getElementById('content-frame');
    document.querySelectorAll('.format-tab').forEach(t => {
      t.addEventListener('click', () => {
        document.querySelectorAll('.format-tab').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        frame.src = API + '/documents/' + docId + '/content?format=' + t.getAttribute('data-format');
      });
    });

    const container = document.getElementById('chunks-container');
    if (!chunks || !chunks.length) {
      container.innerHTML = '<p class="msg msg-info">No chunks for this document. Run Process 2 to chunk.</p>';
      return;
    }
    container.innerHTML = '<ul class="chunk-list"></ul>';
    const ul = container.querySelector('ul');
    chunks.forEach(c => {
      const li = document.createElement('li');
      li.className = 'chunk-item';
      const linksHtml = (c.linked_chunk_ids || []).map(linkedId =>
        '<a href="#compare/' + escapeHtml(c.chunk_id) + '/' + escapeHtml(linkedId) + '" class="btn btn-primary btn-sm">View linked chunk ' + escapeHtml(linkedId) + '</a>'
      ).join(' ');
      li.innerHTML = `
        <strong>Chunk ${c.chunk_index}</strong> (${escapeHtml(c.chunk_id)})
        <div class="chunk-preview">${escapeHtml(c.content_preview || '')}</div>
        ${linksHtml ? '<div class="chunk-links">' + linksHtml + '</div>' : '<div class="chunk-links"><span style="color:var(--text-muted);">No linked chunks</span></div>'}
      `;
      ul.appendChild(li);
    });
  }

  // --- Side-by-side compare ---
  function renderCompare(chunkId, linkedChunkId) {
    setActiveNav('documents');
    main.innerHTML = '<div class="loading">Loading chunks…</div>';
    Promise.all([
      api('/chunks/' + chunkId),
      api('/chunks/' + linkedChunkId),
    ]).then(([left, right]) => {
      const leftDoc = left.document ? left.document.name + ' (' + left.document.doc_type + ')' : 'Chunk ' + chunkId;
      const rightDoc = right.document ? right.document.name + ' (' + right.document.doc_type + ')' : 'Chunk ' + linkedChunkId;
      main.innerHTML = `
        <div class="breadcrumb">
          <a href="#documents">Documents</a> →
          <a href="#view/${left.document_id}">${escapeHtml(leftDoc)}</a> →
          Chunk ${escapeHtml(chunkId)} ↔
          <a href="#view/${right.document_id}">${escapeHtml(rightDoc)}</a> (${escapeHtml(linkedChunkId)})
        </div>
        <h1>Linked chunks</h1>
        <div class="compare-layout">
          <div class="compare-pane">
            <h3>${escapeHtml(leftDoc)} — Chunk ${escapeHtml(chunkId)}</h3>
            <div class="pane-content">${escapeHtml(left.content)}</div>
          </div>
          <div class="compare-pane">
            <h3>${escapeHtml(rightDoc)} — Chunk ${escapeHtml(linkedChunkId)}</h3>
            <div class="pane-content">${escapeHtml(right.content)}</div>
          </div>
        </div>
      `;
    }).catch(err => {
      main.innerHTML = '<div class="msg msg-error">' + escapeHtml(err.message) + '</div>';
    });
  }

  // --- Router ---
  function route() {
    const hash = (location.hash || '#upload').slice(1);
    const parts = hash.split('/');
    const page = parts[0] || 'upload';
    if (page === 'upload') {
      renderUpload();
    } else if (page === 'documents') {
      const type = parts[1] || '';
      renderDocuments(type === 'external' || type === 'internal' ? type : null);
    } else if (page === 'view' && parts[1]) {
      renderView(parts[1]);
    } else if (page === 'compare' && parts[1] && parts[2]) {
      renderCompare(parts[1], parts[2]);
    } else {
      renderUpload();
    }
  }

  window.addEventListener('hashchange', route);
  route();
})();
