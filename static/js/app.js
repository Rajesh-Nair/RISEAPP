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
  function getViewParams() {
    const hash = (location.hash || '').slice(1);
    const q = hash.indexOf('?');
    if (q < 0) return {};
    const params = {};
    hash.slice(q + 1).split('&').forEach(p => {
      const [k, v] = p.split('=');
      if (k && v) params[decodeURIComponent(k)] = decodeURIComponent(v);
    });
    return params;
  }

  function renderView(id) {
    setActiveNav('documents');
    main.innerHTML = '<div class="loading">Loading document…</div>';
    const params = getViewParams();
    const highlightChunkId = params.highlight || params.hl;

    api('/documents/' + id + '/content-annotated?format=md').then(data => {
      const doc = data.document;
      if (!doc) { main.innerHTML = '<div class="msg msg-error">Document not found.</div>'; return; }
      renderViewWithDoc(doc, data.content, data.chunks || [], data.format || 'md', highlightChunkId);
    }).catch(() => {
      // Fallback: fetch doc + chunks, use HTML iframe when MD not available
      Promise.all([
        api('/documents').then(docs => docs.find(x => x.id === parseInt(id, 10))),
        api('/documents/' + id + '/chunks').catch(() => []),
      ]).then(([doc, chunks]) => {
        if (!doc) { main.innerHTML = '<div class="msg msg-error">Document not found.</div>'; return; }
        const fmt = doc.has_md ? 'md' : 'html';
        fetch(API + '/documents/' + id + '/content?format=' + fmt).then(r => r.ok ? r.text() : '')
          .then(content => renderViewWithDoc(doc, content || '', chunks, fmt, highlightChunkId))
          .catch(() => renderViewWithDoc(doc, '', chunks, fmt, highlightChunkId));
      }).catch(e => {
        main.innerHTML = '<div class="msg msg-error">' + escapeHtml(e.message) + '</div>';
      });
    });
  }

  function escapeAttr(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML.replace(/"/g, '&quot;');
  }

  function injectChunkLinks(content, chunks) {
    if (!chunks || chunks.length === 0) return content;
    const positions = [];
    let searchStart = 0;
    for (const c of chunks.sort((a, b) => a.chunk_index - b.chunk_index)) {
      let start, end, segment;
      if (c.start_offset != null && c.end_offset != null) {
        start = c.start_offset;
        end = Math.min(c.end_offset, content.length);
        segment = content.slice(start, end);
      } else {
        const needle = ((c.content || c.content_preview || '').replace(/…$/, '')).trim();
        if (!needle || needle.length < 20) continue;
        const pos = content.indexOf(needle, searchStart);
        if (pos < 0) continue;
        start = pos;
        end = pos + needle.length;
        segment = needle;
        searchStart = end;
      }
      if (start >= end) continue;
      const linked = (c.linked_docs || [])[0] || (c.linked_chunk_ids || [])[0];
      const linkedDocId = linked && linked.document_id != null ? linked.document_id : (linked ? String(linked).split('_')[0] : null);
      const linkedChunkId = linked && linked.chunk_id ? linked.chunk_id : (linked || null);
      positions.push({ start, end, segment, chunk: c, linkedDocId, linkedChunkId });
    }
    const sorted = positions.sort((a, b) => b.start - a.start);
    let result = content;
    for (const p of sorted) {
      const attrs = [
        'class="chunk-link"',
        'data-chunk-id="' + escapeAttr(p.chunk.chunk_id) + '"',
      ];
      if (p.linkedChunkId) attrs.push('data-linked-chunk-id="' + escapeAttr(p.linkedChunkId) + '"');
      if (p.linkedDocId) attrs.push('data-linked-doc-id="' + escapeAttr(String(p.linkedDocId)) + '"');
      const span = '<span ' + attrs.join(' ') + '>' + escapeHtml(p.segment) + '</span>';
      result = result.slice(0, p.start) + span + result.slice(p.end);
    }
    return result;
  }

  function renderViewWithDoc(doc, content, chunks, format, highlightChunkId) {
    const docId = doc.id;
    const name = doc.name || 'Document ' + docId;
    const formatTabs = [];
    if (doc.has_md) formatTabs.push('<button type="button" class="tab format-tab active" data-format="md">Markdown</button>');
    if (doc.has_html) formatTabs.push('<button type="button" class="tab format-tab" data-format="html">HTML</button>');

    const useMdWithChunks = format === 'md' && chunks && chunks.length > 0;
    const contentHtml = useMdWithChunks
      ? (typeof marked !== 'undefined' ? marked.parse(injectChunkLinks(content, chunks)) : escapeHtml(content))
      : null;

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
        <div class="content-panel ${format === 'html' ? 'content-panel-html' : ''}">
          ${useMdWithChunks
            ? '<div id="content-body" class="md-body content-with-chunks content-panel-body"></div>'
            : format === 'html'
              ? '<iframe id="content-frame" title="Document content"></iframe>'
              : '<iframe id="content-frame" title="Document content" src="' + API + '/documents/' + docId + '/content?format=md"></iframe>'}
        </div>
        ${chunks && chunks.length > 0 && chunks.some(c => (c.linked_docs && c.linked_docs.length) || (c.linked_chunk_ids && c.linked_chunk_ids.length))
          ? '<div class="card card-related"><h2>Related chunks</h2><p class="text-muted" style="margin:0 0 0.5rem 0;font-size:0.9rem;">Click a chunk link in the document above to view related doc side-by-side. Or use:</p><div id="related-chunks-list" class="related-chunks-list"></div></div>'
          : ''}
      </div>
    `;

    if (useMdWithChunks && contentHtml) {
      const contentBody = document.getElementById('content-body');
      contentBody.innerHTML = contentHtml;
      contentBody.querySelectorAll('.chunk-link').forEach(span => {
        span.addEventListener('click', function () {
          const linkedDocId = this.getAttribute('data-linked-doc-id');
          const linkedChunkId = this.getAttribute('data-linked-chunk-id');
          if (linkedDocId && linkedChunkId) {
            location.hash = '#side-by-side/' + docId + '/' + encodeURIComponent(this.getAttribute('data-chunk-id')) + '/' + linkedDocId + '/' + encodeURIComponent(linkedChunkId);
          }
        });
      });
      if (highlightChunkId) {
        const el = contentBody.querySelector('.chunk-link[data-chunk-id="' + escapeAttr(highlightChunkId) + '"]');
        if (el) {
          el.classList.add('chunk-highlighted');
          el.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
      }
    } else if (format === 'html') {
      fetch(API + '/documents/' + docId + '/content?format=html').then(r => r.text()).then(html => {
        const frame = document.getElementById('content-frame');
        const darkStyle = '<style>body,html{background:#0d1117 !important;color:#b8c5d6 !important;font-family:inherit;}</style>';
        frame.srcdoc = '<html><head>' + darkStyle + '</head><body>' + html + '</body></html>';
      });
    }

    document.querySelectorAll('.format-tab').forEach(t => {
      t.addEventListener('click', () => {
        const fmt = t.getAttribute('data-format');
        document.querySelectorAll('.format-tab').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        const panel = document.querySelector('.content-panel');
        panel.classList.toggle('content-panel-html', fmt === 'html');
        if (fmt === 'md') {
          api('/documents/' + docId + '/content-annotated?format=md').then(data => {
            const useChunks = data.chunks && data.chunks.length;
            const html = useChunks && typeof marked !== 'undefined'
              ? marked.parse(injectChunkLinks(data.content, data.chunks))
              : escapeHtml(data.content);
            panel.innerHTML = '<div id="content-body" class="md-body content-with-chunks content-panel-body"></div>';
            const body = document.getElementById('content-body');
            body.innerHTML = html;
            body.querySelectorAll('.chunk-link').forEach(span => {
              span.addEventListener('click', function () {
                const linkedDocId = this.getAttribute('data-linked-doc-id');
                const linkedChunkId = this.getAttribute('data-linked-chunk-id');
                if (linkedDocId && linkedChunkId) {
                  location.hash = '#side-by-side/' + docId + '/' + encodeURIComponent(this.getAttribute('data-chunk-id')) + '/' + linkedDocId + '/' + encodeURIComponent(linkedChunkId);
                }
              });
            });
          });
        } else {
          panel.innerHTML = '<iframe id="content-frame" title="Document content"></iframe>';
          fetch(API + '/documents/' + docId + '/content?format=html').then(r => r.text()).then(html => {
            const frame = document.getElementById('content-frame');
            const darkStyle = '<style>body,html{background:#0d1117 !important;color:#b8c5d6 !important;font-family:inherit;}</style>';
            frame.srcdoc = '<html><head>' + darkStyle + '</head><body>' + html + '</body></html>';
          });
        }
      });
    });

    const relatedList = document.getElementById('related-chunks-list');
    if (relatedList && chunks && chunks.length > 0) {
      const links = [];
      chunks.forEach(c => {
        const linkedDocs = c.linked_docs || [];
        const linkedIds = c.linked_chunk_ids || [];
        const targets = linkedDocs.length > 0 ? linkedDocs : linkedIds.map(id => ({ chunk_id: id, document_id: String(id).split('_')[0], name: id }));
        targets.forEach(t => {
          const linkedDocId = t.document_id != null ? t.document_id : String(t).split('_')[0];
          const linkedChunkId = t.chunk_id || t;
          const href = '#side-by-side/' + docId + '/' + encodeURIComponent(c.chunk_id) + '/' + linkedDocId + '/' + encodeURIComponent(linkedChunkId);
          links.push('<a href="' + href + '" class="btn btn-primary btn-sm related-chunk-btn">' + escapeHtml(c.chunk_id) + ' → ' + escapeHtml(linkedChunkId) + '</a>');
        });
      });
      relatedList.innerHTML = links.length > 0 ? links.join(' ') : '<span style="color:var(--text-muted);">No linked chunks. Run Process 3 for lineage.</span>';
    }
  }

  function renderSideBySide(docId1, chunkId1, docId2, chunkId2) {
    setActiveNav('documents');
    main.innerHTML = '<div class="loading">Loading documents…</div>';
    Promise.all([
      api('/documents/' + docId1 + '/content-annotated?format=md'),
      api('/documents/' + docId2 + '/content-annotated?format=md'),
    ]).then(([data1, data2]) => {
      const doc1 = data1.document;
      const doc2 = data2.document;
      if (!doc1 || !doc2) {
        main.innerHTML = '<div class="msg msg-error">Document not found.</div>';
        return;
      }
      const useChunks1 = data1.chunks && data1.chunks.length;
      const useChunks2 = data2.chunks && data2.chunks.length;
      const html1 = useChunks1 && typeof marked !== 'undefined'
        ? marked.parse(injectChunkLinks(data1.content, data1.chunks))
        : escapeHtml(data1.content);
      const html2 = useChunks2 && typeof marked !== 'undefined'
        ? marked.parse(injectChunkLinks(data2.content, data2.chunks))
        : escapeHtml(data2.content);
      main.innerHTML = `
        <div class="breadcrumb">
          <a href="#documents">Documents</a> →
          <a href="#view/${docId1}">${escapeHtml(doc1.name)}</a> ↔
          <a href="#view/${docId2}">${escapeHtml(doc2.name)}</a>
        </div>
        <h1>Linked documents</h1>
        <div class="side-by-side-layout">
          <div class="side-by-side-pane">
            <h3>${escapeHtml(doc1.name)}</h3>
            <div class="side-by-side-scroll content-with-chunks" id="pane-left"></div>
          </div>
          <div class="side-by-side-pane">
            <h3>${escapeHtml(doc2.name)}</h3>
            <div class="side-by-side-scroll content-with-chunks" id="pane-right"></div>
          </div>
        </div>
      `;
      const paneLeft = document.getElementById('pane-left');
      const paneRight = document.getElementById('pane-right');
      paneLeft.innerHTML = html1;
      paneRight.innerHTML = html2;

      function alignChunks(clickedEl, clickedPane, otherPane, linkedChunkId) {
        const otherEl = otherPane.querySelector('.chunk-link[data-chunk-id="' + escapeAttr(linkedChunkId) + '"]');
        if (!otherEl) return;
        document.querySelectorAll('.chunk-link.chunk-aligned').forEach(el => el.classList.remove('chunk-aligned'));
        document.querySelectorAll('.chunk-link.chunk-highlighted').forEach(el => el.classList.remove('chunk-highlighted'));
        clickedEl.classList.add('chunk-aligned');
        otherEl.classList.add('chunk-aligned');
        const clickedRect = clickedEl.getBoundingClientRect();
        const clickedPaneRect = clickedPane.getBoundingClientRect();
        const offsetInView = clickedRect.top - clickedPaneRect.top;
        const targetScrollTop = otherEl.offsetTop - offsetInView;
        otherPane.scrollTo({ top: Math.max(0, targetScrollTop), behavior: 'smooth' });
      }

      function setupChunkClick(span, myDocId, otherDocId) {
        span.addEventListener('click', function (e) {
          e.preventDefault();
          const cid = this.getAttribute('data-chunk-id');
          const linkedDocId = this.getAttribute('data-linked-doc-id');
          const linkedChunkId = this.getAttribute('data-linked-chunk-id');
          if (!linkedDocId || !linkedChunkId) return;
          if (linkedDocId === String(otherDocId)) {
            const clickedPane = this.closest('.side-by-side-scroll');
            const otherPane = clickedPane === paneLeft ? paneRight : paneLeft;
            alignChunks(this, clickedPane, otherPane, linkedChunkId);
          } else {
            location.hash = '#side-by-side/' + myDocId + '/' + encodeURIComponent(cid) + '/' + linkedDocId + '/' + encodeURIComponent(linkedChunkId);
          }
        });
      }

      paneLeft.querySelectorAll('.chunk-link').forEach(span => setupChunkClick(span, docId1, docId2));
      paneRight.querySelectorAll('.chunk-link').forEach(span => setupChunkClick(span, docId2, docId1));

      const el1 = paneLeft.querySelector('.chunk-link[data-chunk-id="' + escapeAttr(chunkId1) + '"]');
      const el2 = paneRight.querySelector('.chunk-link[data-chunk-id="' + escapeAttr(chunkId2) + '"]');
      if (el1 && el2) {
        el1.classList.add('chunk-highlighted');
        el2.classList.add('chunk-highlighted');
        el1.scrollIntoView({ block: 'center', behavior: 'smooth' });
        setTimeout(function () {
          const rect1 = el1.getBoundingClientRect();
          const paneRect1 = paneLeft.getBoundingClientRect();
          const offsetInView = rect1.top - paneRect1.top;
          const targetScrollTop = el2.offsetTop - offsetInView;
          paneRight.scrollTo({ top: Math.max(0, targetScrollTop), behavior: 'smooth' });
          el1.classList.remove('chunk-highlighted');
          el2.classList.remove('chunk-highlighted');
          el1.classList.add('chunk-aligned');
          el2.classList.add('chunk-aligned');
        }, 300);
      } else if (el1) {
        el1.classList.add('chunk-highlighted');
        el1.scrollIntoView({ block: 'center', behavior: 'smooth' });
      } else if (el2) {
        el2.classList.add('chunk-highlighted');
        el2.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    }).catch(err => {
      main.innerHTML = '<div class="msg msg-error">' + escapeHtml(err.message) + '</div>';
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
    const viewId = parts[1] ? parts[1].split('?')[0] : null;
    if (page === 'upload') {
      renderUpload();
    } else if (page === 'documents') {
      const type = parts[1] || '';
      renderDocuments(type === 'external' || type === 'internal' ? type : null);
    } else if (page === 'view' && viewId) {
      renderView(viewId);
    } else if (page === 'side-by-side' && parts[1] && parts[2] && parts[3] && parts[4]) {
      renderSideBySide(parts[1], decodeURIComponent(parts[2]), parts[3], decodeURIComponent(parts[4]));
    } else if (page === 'compare' && parts[1] && parts[2]) {
      renderCompare(parts[1], parts[2]);
    } else {
      renderUpload();
    }
  }

  window.addEventListener('hashchange', route);
  route();
})();
