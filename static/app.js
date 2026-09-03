const state = {
  recorder: null,
  stream: null,
  chunks: [],
  recordingBlob: null,
  currentView: 'dashboard',
  currentMode: 'speak',
};

const pageMeta = {
  dashboard: ['Focuslyra', 'One place for every language you decide to learn.'],
  study: ["Today's study", 'Speak, listen, read, write and train pronunciation in one workspace.'],
  concepts: ['Concept memory', 'One meaning, many language expressions.'],
  review: ['Adaptive review', 'Recognition and production are different skills.'],
  memory: ['Memory sources', 'Use your own worlds and projects without copying stale files.'],
  progress: ['Progress', 'Measure abilities instead of lesson completion.'],
  providers: ['AI providers', 'Local/free first. Paid intelligence is opt-in.'],
};

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response.text();
}

function setView(viewId) {
  state.currentView = viewId;
  document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === viewId));
  document.querySelectorAll('.nav-button').forEach(button => button.classList.toggle('active', button.dataset.view === viewId));
  const [title, subtitle] = pageMeta[viewId];
  document.getElementById('pageTitle').textContent = title;
  document.getElementById('pageSubtitle').textContent = subtitle;
}

function setMode(mode) {
  state.currentMode = mode;
  document.querySelectorAll('.mode-tab').forEach(button => button.classList.toggle('active', button.dataset.mode === mode));
  document.querySelectorAll('.mode-panel').forEach(panel => panel.classList.toggle('active', panel.id === `mode-${mode}`));
}

function languageProgress(language) {
  const defaults = {
    'en-GB': 78,
    'es-ES': 8,
    'ja-JP': 13,
    'it-IT': 26,
    'fr-FR': 23,
    'ar': 2,
    'de-DE': 1,
  };
  return defaults[language.code] ?? 0;
}

function renderLanguages(languages) {
  const grid = document.getElementById('languageGrid');
  grid.innerHTML = languages.map(language => {
    const progress = languageProgress(language);
    return `
      <article class="language-card">
        <div class="language-head">
          <div class="language-title"><span>${escapeHtml(language.flag)}</span>${escapeHtml(language.name)}</div>
          <span class="badge">P${escapeHtml(language.priority)} · ${escapeHtml(language.status)}</span>
        </div>
        <div class="language-progress"><i style="width:${progress}%"></i></div>
        <div class="language-meta">${escapeHtml(language.current_state)}</div>
        <div class="language-meta"><strong>Target:</strong> ${escapeHtml(language.target_variety)}</div>
      </article>`;
  }).join('');
}

function renderSources(sources) {
  const grid = document.getElementById('sourceGrid');
  grid.innerHTML = sources.map(source => `
    <article class="source-card">
      <div class="source-head">
        <div>
          <h3>${escapeHtml(source.name)}</h3>
          <span class="repo-code">${escapeHtml(source.repository)}</span>
        </div>
        <span class="badge">${source.enabled ? 'LINKED' : 'PAUSED'}</span>
      </div>
      <p>${escapeHtml(source.instructions)}</p>
      <p><strong>Mode:</strong> ${escapeHtml(source.mode)}<br><strong>Branch:</strong> ${escapeHtml(source.branch)}<br><strong>Write access:</strong> ${source.permissions?.modify_source ? 'allowed' : 'blocked'}</p>
      <button class="ghost" disabled>Repository indexing comes next</button>
    </article>`).join('');
}

function renderProviders(providers) {
  const grid = document.getElementById('providerGrid');
  grid.innerHTML = providers.map(provider => `
    <article class="provider-card">
      <div class="provider-head">
        <div>
          <h3>${escapeHtml(provider.label)}</h3>
          <span class="muted small">${escapeHtml(provider.kind)}</span>
        </div>
        <span class="provider-state ${provider.enabled ? 'on' : 'off'}">${provider.enabled ? 'ENABLED' : 'OFF'}</span>
      </div>
      <p>${escapeHtml(provider.note)}</p>
      <p><strong>Configured:</strong> ${provider.configured ? 'yes' : 'no'}<br><strong>Potentially paid:</strong> ${provider.potentially_paid ? 'yes' : 'no'}</p>
    </article>`).join('');
}

async function boot() {
  try {
    const [health, languages, sources, providers] = await Promise.all([
      api('/api/health'),
      api('/api/languages'),
      api('/api/sources'),
      api('/api/providers'),
    ]);

    document.getElementById('serverStatus').textContent = '● Local server connected';
    document.getElementById('serverStatus').style.color = '#9ee8c9';
    const badge = document.getElementById('paidAiBadge');
    badge.textContent = `Paid AI: ${health.paid_ai_allowed ? 'ON' : 'OFF'}`;
    badge.classList.toggle('safe', !health.paid_ai_allowed);
    renderLanguages(languages);
    renderSources(sources);
    renderProviders(providers);
  } catch (error) {
    document.getElementById('serverStatus').textContent = '● Server unavailable';
    document.getElementById('serverStatus').style.color = '#ff9aa7';
    console.error(error);
  }
}

async function startRecording() {
  const status = document.getElementById('recordStatus');
  if (!navigator.mediaDevices?.getUserMedia) {
    status.textContent = 'This browser does not expose microphone recording.';
    return;
  }

  state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  state.chunks = [];
  state.recordingBlob = null;
  state.recorder = new MediaRecorder(state.stream);

  state.recorder.addEventListener('dataavailable', event => {
    if (event.data.size > 0) state.chunks.push(event.data);
  });

  state.recorder.addEventListener('stop', () => {
    state.recordingBlob = new Blob(state.chunks, { type: state.recorder.mimeType || 'audio/webm' });
    const playback = document.getElementById('recordingPlayback');
    playback.src = URL.createObjectURL(state.recordingBlob);
    playback.hidden = false;
    document.getElementById('saveRecording').hidden = false;
    status.textContent = 'Recorded locally. Listen, then save it to Focuslyra.';
    state.stream.getTracks().forEach(track => track.stop());
  });

  state.recorder.start();
  const button = document.getElementById('recordButton');
  button.classList.add('recording');
  button.textContent = '■';
  status.textContent = 'Recording… press again to stop.';
}

function stopRecording() {
  if (state.recorder?.state === 'recording') {
    state.recorder.stop();
  }
  const button = document.getElementById('recordButton');
  button.classList.remove('recording');
  button.textContent = '🎙';
}

async function saveRecording() {
  if (!state.recordingBlob) return;
  const button = document.getElementById('saveRecording');
  const feedback = document.getElementById('recordFeedback');
  button.disabled = true;
  button.textContent = 'Saving…';

  const form = new FormData();
  form.append('file', state.recordingBlob, 'speaking.webm');
  form.append('language_code', 'es-ES');
  form.append('activity', 'hotel-roleplay');

  try {
    const result = await api('/api/recordings', { method: 'POST', body: form });
    feedback.hidden = false;
    feedback.className = 'feedback good';
    feedback.innerHTML = `<strong>Saved.</strong><br>${escapeHtml(result.recording.relative_audio_path)}<br><span class="muted small">AI transcription and pronunciation analysis will attach to this same recording in a later phase.</span>`;
    button.textContent = '✓ Saved';
  } catch (error) {
    feedback.hidden = false;
    feedback.className = 'feedback';
    feedback.textContent = `Could not save recording: ${error.message}`;
    button.disabled = false;
    button.textContent = 'Try save again';
  }
}

async function saveWriting() {
  const text = document.getElementById('writingInput').value.trim();
  const resultBox = document.getElementById('writingResult');
  if (!text) {
    resultBox.hidden = false;
    resultBox.textContent = 'Write something first. The messy first draft is useful data.';
    return;
  }

  try {
    const result = await api('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language_code: 'es-ES',
        mode: 'writing',
        writing: text,
        metadata: { exercise: 'describe-morning' },
      }),
    });
    resultBox.hidden = false;
    resultBox.className = 'feedback good';
    resultBox.innerHTML = `<strong>Original saved.</strong> Session #${result.session_id}.<br><span class="muted small">AI correction will later create a separate natural version without overwriting this text.</span>`;
  } catch (error) {
    resultBox.hidden = false;
    resultBox.textContent = `Could not save: ${error.message}`;
  }
}

document.querySelectorAll('.nav-button').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
document.querySelectorAll('.mode-tab').forEach(button => button.addEventListener('click', () => setMode(button.dataset.mode)));

document.getElementById('startSession').addEventListener('click', () => setView('study'));
document.getElementById('quickTen').addEventListener('click', () => {
  setView('study');
  document.getElementById('pageSubtitle').textContent = '10-minute mode: one useful speaking task + short review. No backlog.';
});
document.getElementById('makeInteresting').addEventListener('click', () => {
  setView('study');
  document.getElementById('pageSubtitle').textContent = 'Same learning targets, different wrapper: roleplay mode selected.';
});
document.getElementById('switchActivity').addEventListener('click', () => {
  const modes = ['speak', 'listen', 'write', 'read', 'pronounce'];
  const next = modes[(modes.indexOf(state.currentMode) + 1) % modes.length];
  setMode(next);
});

document.getElementById('recordButton').addEventListener('click', async () => {
  try {
    if (state.recorder?.state === 'recording') stopRecording();
    else await startRecording();
  } catch (error) {
    document.getElementById('recordStatus').textContent = `Microphone error: ${error.message}`;
  }
});
document.getElementById('saveRecording').addEventListener('click', saveRecording);
document.getElementById('saveWriting').addEventListener('click', saveWriting);
document.getElementById('reviewReveal').addEventListener('click', () => document.getElementById('reviewAnswer').hidden = false);
document.getElementById('demoListen').addEventListener('click', () => {
  const box = document.getElementById('listenDemoResult');
  box.hidden = false;
  box.innerHTML = '<strong>Flow:</strong> play audio → learner answers → reveal transcript → compare → create evidence event. Generated/cached audio comes in the speech phase.';
});

boot();
