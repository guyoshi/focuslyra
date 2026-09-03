const v2 = {
  reviewItems: [],
  reviewIndex: 0,
  diagnostic: null,
  diagnosticRecorder: null,
  diagnosticStream: null,
  diagnosticChunks: [],
};

function v2Escape(value) {
  return typeof escapeHtml === 'function' ? escapeHtml(value ?? '') : String(value ?? '');
}

async function v2Api(path, options = {}) {
  if (typeof api === 'function') return api(path, options);
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body?.detail || 'Request failed');
  return body;
}

function v2ButtonBusy(button, label) {
  if (!button) return () => {};
  const old = button.textContent;
  button.disabled = true;
  button.textContent = label;
  return () => { button.disabled = false; button.textContent = old; };
}

// ---------- Review ----------
async function loadRealReview() {
  const section = document.getElementById('review');
  if (!section) return;
  section.innerHTML = '<article class="card review-card"><h2>Adaptive review</h2><p class="muted">Loading due retrieval targets…</p></article>';
  try {
    const result = await v2Api('/api/review/due?limit=30');
    v2.reviewItems = result.items || [];
    v2.reviewIndex = 0;
    renderReviewItem(result.due_count || 0);
  } catch (error) {
    section.innerHTML = `<article class="card"><h2>Adaptive review</h2><div class="feedback">${v2Escape(error.message)}</div></article>`;
  }
}

function renderReviewItem(totalDue = null) {
  const section = document.getElementById('review');
  const item = v2.reviewItems[v2.reviewIndex];
  if (!item) {
    section.innerHTML = `<article class="card review-card"><span class="badge">REVIEW</span><div class="review-visual">✓</div><h2>Nothing due right now.</h2><p class="muted">New targets appear here automatically from your real study mistakes and retrieval evidence.</p></article>`;
    return;
  }
  const left = totalDue ?? v2.reviewItems.length;
  section.innerHTML = `
    <article class="card review-card">
      <span class="badge">${v2Escape(item.flag)} ${v2Escape(item.language_name)} · ${v2Escape(item.modality)} · ${left} DUE</span>
      <h2>Retrieve this before revealing it.</h2>
      <p>${v2Escape(item.prompt)}</p>
      <div id="v2ReviewAnswer" class="answer" hidden>${v2Escape(item.answer)}</div>
      <div class="review-actions">
        <button id="v2ReviewReveal" class="primary">Reveal answer</button>
        <button data-grade="again" class="ghost" disabled>Again</button>
        <button data-grade="hard" class="ghost" disabled>Hard</button>
        <button data-grade="good" class="ghost" disabled>Good</button>
        <button data-grade="easy" class="ghost" disabled>Easy</button>
      </div>
      <p class="muted small">Current interval: ${v2Escape(item.interval_days)} day(s) · repetitions: ${v2Escape(item.repetitions)}</p>
    </article>`;
  const reveal = section.querySelector('#v2ReviewReveal');
  reveal.addEventListener('click', () => {
    section.querySelector('#v2ReviewAnswer').hidden = false;
    section.querySelectorAll('[data-grade]').forEach(button => button.disabled = false);
    reveal.disabled = true;
  });
  section.querySelectorAll('[data-grade]').forEach(button => button.addEventListener('click', async () => {
    section.querySelectorAll('button').forEach(b => b.disabled = true);
    try {
      await v2Api(`/api/review/${item.id}/grade`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({rating: button.dataset.grade}),
      });
      v2.reviewIndex += 1;
      renderReviewItem(Math.max(0, left - 1));
    } catch (error) {
      button.disabled = false;
      alert(error.message);
    }
  }));
}

// ---------- Concepts ----------
async function loadRealConcepts() {
  const panel = document.getElementById('memory-concepts');
  if (!panel) return;
  try {
    const concepts = await v2Api('/api/concepts');
    panel.innerHTML = `
      <article class="card">
        <div class="section-heading compact"><div><h2>Global concept memory</h2><p>One meaning, reusable across every language.</p></div><span class="badge">${concepts.length} CONCEPTS</span></div>
        <div class="form-grid">
          <label>Meaning / label<input id="v2ConceptLabel" placeholder="dog, deadline, freedom…"></label>
          <label>Emoji / visual<input id="v2ConceptVisual" placeholder="🐕"></label>
        </div>
        <button id="v2AddConcept" class="primary">Add concept</button>
        <div id="v2ConceptMessage" class="feedback" hidden></div>
      </article>
      <div id="v2ConceptGrid" class="source-grid"></div>`;
    renderConceptGrid(concepts);
    panel.querySelector('#v2AddConcept').addEventListener('click', async event => {
      const restore = v2ButtonBusy(event.currentTarget, 'Saving…');
      const label = panel.querySelector('#v2ConceptLabel').value.trim();
      const visual = panel.querySelector('#v2ConceptVisual').value.trim();
      const message = panel.querySelector('#v2ConceptMessage');
      try {
        if (!label) throw new Error('Give the concept a meaning/label first.');
        await v2Api('/api/concepts', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({label, visual, visual_kind: visual ? 'emoji' : 'none'}),
        });
        await loadRealConcepts();
      } catch (error) {
        message.hidden = false; message.textContent = error.message;
      } finally { restore(); }
    });
  } catch (error) {
    panel.innerHTML = `<article class="card"><div class="feedback">${v2Escape(error.message)}</div></article>`;
  }
}

function renderConceptGrid(concepts) {
  const grid = document.getElementById('v2ConceptGrid');
  if (!grid) return;
  if (!concepts.length) {
    grid.innerHTML = '<article class="card"><p class="muted">No concepts yet. Add one above, then let Qwen enrich it across your languages.</p></article>';
    return;
  }
  grid.innerHTML = concepts.map(concept => {
    const expressions = Object.entries(concept.expressions || {}).map(([code, value]) => {
      const text = typeof value === 'object' ? value.text : value;
      const reading = typeof value === 'object' ? (value.reading || value.transliteration || '') : '';
      return `<div><small>${v2Escape(code)}</small><strong>${v2Escape(text || '')}</strong>${reading ? `<small>${v2Escape(reading)}</small>` : ''}</div>`;
    }).join('');
    return `<article class="card source-card">
      <div class="source-head"><div><div class="concept-visual" style="font-size:3rem">${v2Escape(concept.visual || '◌')}</div><h3>${v2Escape(concept.label)}</h3></div><span class="badge">#${concept.id}</span></div>
      <div class="concept-words">${expressions || '<span class="muted small">Not enriched yet.</span>'}</div>
      <button class="ghost v2-enrich-concept" data-id="${concept.id}">🧠 Enrich across languages</button>
    </article>`;
  }).join('');
  grid.querySelectorAll('.v2-enrich-concept').forEach(button => button.addEventListener('click', async () => {
    const restore = v2ButtonBusy(button, 'Qwen is enriching…');
    try { await v2Api(`/api/concepts/${button.dataset.id}/enrich`, {method:'POST'}); await loadRealConcepts(); }
    catch (error) { alert(error.message); restore(); }
  }));
}

// ---------- Memory / RAG ----------
async function loadMemorySourcesV2() {
  const grid = document.getElementById('sourceGrid');
  if (!grid) return;
  try {
    const [sources, status] = await Promise.all([v2Api('/api/sources'), v2Api('/api/memory/index-status')]);
    const byId = Object.fromEntries((status || []).map(item => [item.source_id, item]));
    grid.innerHTML = sources.map(source => {
      const indexed = byId[source.id];
      return `<article class="source-card">
        <div class="source-head"><div><h3>${v2Escape(source.name)}</h3><span class="repo-code">${v2Escape(source.repository)}</span></div><span class="badge">${indexed ? 'INDEXED' : 'NOT INDEXED'}</span></div>
        <p>${v2Escape(source.instructions || '')}</p>
        <p class="muted small">${indexed ? `${indexed.files} files · ${indexed.chunks} chunks · ${String(indexed.commit_sha || '').slice(0,8)}` : 'Sync + index once, then Focuslyra can retrieve relevant excerpts for lessons.'}</p>
        <button class="primary v2-index-source" data-id="${v2Escape(source.id)}">${indexed ? '↻ Re-index source' : 'Index source'}</button>
      </article>`;
    }).join('') + `
      <article class="card">
        <h3>Test memory retrieval</h3>
        <div class="calendar-actions"><input id="v2MemoryQuery" placeholder="Hyde, Tinkos, teleporter…"><button id="v2MemorySearch" class="ghost">Search</button></div>
        <div id="v2MemoryResults"></div>
      </article>`;
    grid.querySelectorAll('.v2-index-source').forEach(button => button.addEventListener('click', async () => {
      const restore = v2ButtonBusy(button, 'Syncing + indexing…');
      try { await v2Api(`/api/memory/sources/${encodeURIComponent(button.dataset.id)}/index`, {method:'POST'}); await loadMemorySourcesV2(); }
      catch (error) { alert(error.message); restore(); }
    }));
    grid.querySelector('#v2MemorySearch')?.addEventListener('click', async () => {
      const q = grid.querySelector('#v2MemoryQuery').value.trim();
      if (!q) return;
      const result = await v2Api(`/api/memory/search?q=${encodeURIComponent(q)}&limit=5`);
      grid.querySelector('#v2MemoryResults').innerHTML = (result.results || []).map(item => `<div class="feedback"><strong>${v2Escape(item.source_id)} · ${v2Escape(item.path)}</strong><p>${v2Escape(String(item.content || '').slice(0,700))}</p></div>`).join('') || '<p class="muted">No indexed match.</p>';
    });
  } catch (error) { grid.innerHTML = `<div class="feedback">${v2Escape(error.message)}</div>`; }
}

// ---------- Progress ----------
async function loadRealProgress() {
  const section = document.getElementById('progress');
  if (!section) return;
  section.innerHTML = '<article class="card"><h2>Evidence-based progress</h2><p class="muted">Calculating from your actual sessions…</p></article>';
  try {
    const [progress, latest] = await Promise.all([v2Api('/api/progress'), v2Api('/api/diagnostic/latest')]);
    section.innerHTML = `
      <article class="card">
        <div class="section-heading compact"><div><h2>Evidence map</h2><p>Ability signals, not lesson-completion theatre.</p></div><span class="badge">${progress.totals.sessions} SESSIONS</span></div>
        <div class="language-grid">${progress.languages.map(renderProgressLanguage).join('')}</div>
        <p class="muted small">${v2Escape(progress.warning)}</p>
      </article>
      <article class="card" id="v2DiagnosticHost">
        <div class="section-heading compact"><div><h2>🇬🇧 English deep diagnostic</h2><p>Speaking, retrieval, grammar, writing, blind RP listening and RP pronunciation.</p></div><span class="badge">${latest.attempt ? 'BASELINE SAVED' : 'NOT RUN'}</span></div>
        <button id="v2StartDiagnostic" class="primary">${latest.attempt ? 'Run a new diagnostic' : 'Start diagnostic'}</button>
        ${latest.attempt ? renderDiagnosticSummary(latest.attempt.summary) : ''}
      </article>`;
    section.querySelector('#v2StartDiagnostic').addEventListener('click', startDiagnosticUI);
  } catch (error) { section.innerHTML = `<article class="card"><div class="feedback">${v2Escape(error.message)}</div></article>`; }
}

function renderProgressLanguage(language) {
  const skills = Object.entries(language.skills || {}).slice(0,8).map(([skill, score]) => `<div><span>${v2Escape(skill.replaceAll('_',' '))}</span><i style="--score:${score}%"></i><b>${score}</b></div>`).join('');
  return `<article class="language-card">
    <div class="language-head"><div class="language-title"><span>${v2Escape(language.flag)}</span>${v2Escape(language.name)}</div><span class="badge">${language.overall_evidence_score ?? '—'}</span></div>
    <p class="muted small">${language.sessions_7d} sessions / 7d · evidence confidence ${language.evidence_confidence}%</p>
    <div class="progress-list">${skills || '<span class="muted small">Not enough evidence yet.</span>'}</div>
  </article>`;
}

// ---------- Diagnostic ----------
async function startDiagnosticUI() {
  const attempt = await v2Api('/api/diagnostic/english/start', {method:'POST'});
  v2.diagnostic = attempt;
  localStorage.setItem('focuslyraDiagnosticAttempt', String(attempt.id));
  renderDiagnosticAttempt();
}

function renderDiagnosticSummary(summary) {
  if (!summary) return '';
  const dimensions = Object.entries(summary.dimensions || {}).map(([key,value]) => `<div><span>${v2Escape(key.replaceAll('_',' '))}</span><strong>${value == null ? '—' : `${Math.round(value)}%`}</strong></div>`).join('');
  return `<div class="feedback good"><p>${v2Escape(summary.overall_summary || '')}</p><div class="learning-scores">${dimensions}</div>${(summary.priority_gaps || []).length ? `<strong>Priority gaps</strong><ul>${summary.priority_gaps.map(x=>`<li>${v2Escape(x)}</li>`).join('')}</ul>`:''}</div>`;
}

function renderDiagnosticAttempt() {
  const host = document.getElementById('v2DiagnosticHost');
  const attempt = v2.diagnostic;
  if (!host || !attempt) return;
  const parts = attempt.parts || {};
  host.innerHTML = `
    <div class="section-heading compact"><div><h2>English diagnostic · #${attempt.id}</h2><p>Complete the sections in any order. Your original responses are preserved.</p></div><span class="badge">${Object.keys(parts).length}/6 DONE</span></div>
    <div id="v2DiagnosticTasks">${attempt.tasks.map(task => renderDiagnosticTask(task, Boolean(parts[task.id]))).join('')}</div>
    <button id="v2FinaliseDiagnostic" class="primary">Build my ability map</button>
    <div id="v2DiagnosticMessage" class="feedback" hidden></div>`;
  wireDiagnosticTasks(host);
  host.querySelector('#v2FinaliseDiagnostic').addEventListener('click', async event => {
    const restore = v2ButtonBusy(event.currentTarget, 'Building ability map…');
    try {
      v2.diagnostic = await v2Api(`/api/diagnostic/${attempt.id}/finalise`, {method:'POST'});
      localStorage.removeItem('focuslyraDiagnosticAttempt');
      host.innerHTML = `<h2>Diagnostic complete</h2>${renderDiagnosticSummary(v2.diagnostic.summary)}<button class="ghost" id="v2ReloadProgress">Back to Progress</button>`;
      host.querySelector('#v2ReloadProgress').addEventListener('click', loadRealProgress);
    } catch (error) {
      const box = host.querySelector('#v2DiagnosticMessage'); box.hidden=false; box.textContent=error.message; restore();
    }
  });
}

function renderDiagnosticTask(task, done) {
  const badge = done ? '✓ DONE' : task.kind.toUpperCase();
  let input = '';
  if (task.kind === 'text' || task.kind === 'listening') input = `<textarea class="diag-text" placeholder="Your answer…"></textarea><button class="primary diag-submit-text">Submit section</button>`;
  if (task.kind === 'listening') input = `<button class="ghost diag-play">▶ Play blind listening</button>${input}`;
  if (task.kind === 'speech' || task.kind === 'pronunciation') input = `${task.reference_text ? `<div class="feedback"><strong>${v2Escape(task.reference_text)}</strong></div><button class="ghost diag-play-reference">🔊 Hear reference</button>`:''}<button class="record-button diag-record">🎙</button><p class="muted diag-status">Press to record.</p><audio class="diag-playback" controls hidden></audio><button class="primary diag-submit-audio" hidden>${task.kind === 'pronunciation' ? 'Assess pronunciation' : 'Analyse speaking'}</button>`;
  return `<article class="card diag-task" data-id="${v2Escape(task.id)}" data-kind="${v2Escape(task.kind)}">
    <div class="source-head"><h3>${v2Escape(task.title)}</h3><span class="badge">${badge}</span></div><p>${v2Escape(task.prompt)}</p>${input}<div class="feedback diag-result" hidden></div>
  </article>`;
}

function wireDiagnosticTasks(host) {
  host.querySelectorAll('.diag-task').forEach(card => {
    const task = v2.diagnostic.tasks.find(item => item.id === card.dataset.id);
    card.querySelector('.diag-play')?.addEventListener('click', () => {
      if (typeof speakLocally === 'function') speakLocally(task.audio_text, 'en-GB', 'listening');
      else if (typeof browserSpeakFallback === 'function') browserSpeakFallback(task.audio_text, 'en-GB');
    });
    card.querySelector('.diag-play-reference')?.addEventListener('click', () => {
      if (typeof speakLocally === 'function') speakLocally(task.reference_text, 'en-GB', 'reference');
    });
    card.querySelector('.diag-submit-text')?.addEventListener('click', async event => {
      const text = card.querySelector('.diag-text').value.trim(); if (!text) return;
      const restore = v2ButtonBusy(event.currentTarget, 'Analysing…');
      try {
        v2.diagnostic = await v2Api(`/api/diagnostic/${v2.diagnostic.id}/text/${task.id}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text,prompt:task.prompt})});
        renderDiagnosticAttempt();
      } catch (error) { card.querySelector('.diag-result').hidden=false; card.querySelector('.diag-result').textContent=error.message; restore(); }
    });
    const record = card.querySelector('.diag-record');
    if (record) wireDiagnosticRecording(card, task);
  });
}

function wireDiagnosticRecording(card, task) {
  const record = card.querySelector('.diag-record');
  const status = card.querySelector('.diag-status');
  const playback = card.querySelector('.diag-playback');
  const submit = card.querySelector('.diag-submit-audio');
  let blob = null;
  record.addEventListener('click', async () => {
    if (v2.diagnosticRecorder?.state === 'recording') { v2.diagnosticRecorder.stop(); record.textContent='🎙'; return; }
    try {
      v2.diagnosticStream = await navigator.mediaDevices.getUserMedia({audio:true});
      v2.diagnosticChunks=[];
      v2.diagnosticRecorder = new MediaRecorder(v2.diagnosticStream);
      v2.diagnosticRecorder.ondataavailable = event => { if (event.data.size) v2.diagnosticChunks.push(event.data); };
      v2.diagnosticRecorder.onstop = () => {
        blob = new Blob(v2.diagnosticChunks, {type:v2.diagnosticRecorder.mimeType || 'audio/webm'});
        playback.src=URL.createObjectURL(blob); playback.hidden=false; submit.hidden=false; status.textContent='Recorded. Listen once, then submit.';
        v2.diagnosticStream.getTracks().forEach(track=>track.stop());
      };
      v2.diagnosticRecorder.start(); record.textContent='■'; status.textContent='Recording…';
    } catch (error) { status.textContent=error.message; }
  });
  submit.addEventListener('click', async () => {
    if (!blob) return;
    const restore = v2ButtonBusy(submit, 'Processing locally…');
    const form = new FormData(); form.append('file', blob, 'diagnostic.webm'); form.append('language_code','en-GB'); form.append('activity',task.prompt); form.append('activity_id',`diagnostic-${task.id}`); if(task.reference_text) form.append('reference_text',task.reference_text); if(task.target_feature) form.append('target_feature',task.target_feature);
    try {
      const saved = await v2Api('/api/recordings',{method:'POST',body:form});
      let result;
      if (task.kind === 'pronunciation') {
        result = await v2Api(`/api/pronunciation/assess/${saved.recording.id}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reference_text:task.reference_text,language_code:'en-GB',target_feature:task.target_feature})});
      } else {
        result = await v2Api(`/api/learning/analyse-recording/${saved.recording.id}`, {method:'POST'});
      }
      v2.diagnostic = await v2Api(`/api/diagnostic/${v2.diagnostic.id}/part/${task.id}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result})});
      renderDiagnosticAttempt();
    } catch (error) { card.querySelector('.diag-result').hidden=false; card.querySelector('.diag-result').textContent=error.message; restore(); }
  });
}

// ---------- Calendar planner ----------
async function injectCalendarPlanner() {
  const panel = document.getElementById('settings-calendar');
  if (!panel || document.getElementById('v2CalendarPlanner')) return;
  const box = document.createElement('article');
  box.id = 'v2CalendarPlanner'; box.className='card';
  panel.insertBefore(box, panel.querySelector('.calendar-grid') || panel.firstChild);
  try {
    const settings = await v2Api('/api/calendar/plan-settings');
    box.innerHTML = `<h3>🧠 Adaptive planner → Google Calendar</h3><p class="muted">Use the duration Focuslyra actually decides you need, rather than a fixed 45-minute event.</p>
      <div class="calendar-form-grid">
        <label>Automatic<select id="v2CalAuto"><option value="false" ${!settings.auto_schedule?'selected':''}>Off</option><option value="true" ${settings.auto_schedule?'selected':''}>On</option></select></label>
        <label>Plan mode<select id="v2CalMode"><option value="normal" ${settings.mode==='normal'?'selected':''}>Normal</option><option value="minimum" ${settings.mode==='minimum'?'selected':''}>Minimum day</option></select></label>
        <label>From<input id="v2CalStart" type="time" value="${v2Escape(settings.window_start)}"></label>
        <label>Until<input id="v2CalEnd" type="time" value="${v2Escape(settings.window_end)}"></label>
        <label>Days ahead<input id="v2CalDays" type="number" min="0" max="7" value="${settings.days_ahead}"></label>
      </div><div class="calendar-actions"><button id="v2SaveCalPlan" class="ghost">Save planner settings</button><button id="v2ScheduleToday" class="primary">Schedule today's adaptive plan</button></div><div id="v2CalPlanMessage" class="feedback" hidden></div>`;
    box.querySelector('#v2SaveCalPlan').addEventListener('click', async event => {
      const restore=v2ButtonBusy(event.currentTarget,'Saving…'); try { await v2Api('/api/calendar/plan-settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({auto_schedule:box.querySelector('#v2CalAuto').value==='true',mode:box.querySelector('#v2CalMode').value,window_start:box.querySelector('#v2CalStart').value,window_end:box.querySelector('#v2CalEnd').value,days_ahead:Number(box.querySelector('#v2CalDays').value)})}); const m=box.querySelector('#v2CalPlanMessage');m.hidden=false;m.className='feedback good';m.textContent='Adaptive scheduling preferences saved.';} catch(e){alert(e.message);} finally{restore();}
    });
    box.querySelector('#v2ScheduleToday').addEventListener('click', async event => {
      const restore=v2ButtonBusy(event.currentTarget,'Finding a slot…'); const m=box.querySelector('#v2CalPlanMessage'); try { const result=await v2Api('/api/calendar/schedule-plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target_date:localDateString(),mode:box.querySelector('#v2CalMode').value,window_start:box.querySelector('#v2CalStart').value,window_end:box.querySelector('#v2CalEnd').value})}); m.hidden=false;m.className='feedback good';m.textContent=result.existing?'Today already has a Focuslyra adaptive session.':`Scheduled ${result.plan.total_minutes} minutes from today's real plan.`;} catch(e){m.hidden=false;m.textContent=e.message;} finally{restore();}
    });
  } catch (error) { box.innerHTML=`<h3>Adaptive planner</h3><div class="feedback">${v2Escape(error.message)}</div>`; }
}

async function maybeAutoSchedule() {
  try { const settings=await v2Api('/api/calendar/plan-settings'); if(settings.auto_schedule) await v2Api('/api/calendar/auto-plan',{method:'POST'}); } catch (_) {}
}

function phase2Boot() {
  document.querySelector('[data-view="review"]')?.addEventListener('click', loadRealReview);
  document.querySelector('[data-view="progress"]')?.addEventListener('click', loadRealProgress);
  document.querySelector('[data-view="memory"]')?.addEventListener('click', loadMemorySourcesV2);
  document.querySelector('[data-memory-tab="concepts"]')?.addEventListener('click', loadRealConcepts);
  document.querySelector('[data-memory-tab="sources"]')?.addEventListener('click', loadMemorySourcesV2);
  document.querySelector('[data-settings-tab="calendar"]')?.addEventListener('click', injectCalendarPlanner);
  maybeAutoSchedule();
  const saved = Number(localStorage.getItem('focuslyraDiagnosticAttempt') || 0);
  if (saved) v2Api(`/api/diagnostic/${saved}`).then(attempt => { v2.diagnostic=attempt; }).catch(()=>localStorage.removeItem('focuslyraDiagnosticAttempt'));
}

phase2Boot();
