const focuslyraLearners = {
  users: [],
  currentUserId: null,
  placement: {
    languageCode: null,
    prompts: null,
    mode: 'writing',
    recorder: null,
    stream: null,
    chunks: [],
    blob: null,
  },
};

function installLearnerStyles() {
  if (document.getElementById('focuslyraLearnerStyles')) return;
  const style = document.createElement('style');
  style.id = 'focuslyraLearnerStyles';
  style.textContent = `
    .learner-switch { display:flex; align-items:center; gap:.55rem; padding:.35rem .65rem; border:1px solid #26364b; border-radius:999px; background:#0d1520; }
    .learner-switch span { font-size:.8rem; color:#8fa6c4; }
    .learner-switch select { background:transparent; color:#eef6ff; border:0; outline:0; font:inherit; cursor:pointer; }
    .learner-switch option { background:#101924; color:#eef6ff; }
    .placement-launch { margin-left:auto; white-space:nowrap; }
    .placement-overlay { position:fixed; inset:0; z-index:9999; background:rgba(2,7,13,.78); display:flex; align-items:center; justify-content:center; padding:20px; }
    .placement-overlay[hidden] { display:none; }
    .placement-modal { width:min(720px, 100%); max-height:90vh; overflow:auto; background:#111c2a; border:1px solid #2b3d54; border-radius:22px; padding:24px; box-shadow:0 24px 80px rgba(0,0,0,.45); }
    .placement-head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
    .placement-head h2 { margin:.2rem 0; }
    .placement-close { min-width:44px; }
    .placement-tabs { display:flex; gap:8px; margin:18px 0; }
    .placement-tabs button.active { background:#20344f; color:#fff; }
    .placement-panel textarea { width:100%; min-height:180px; resize:vertical; margin:12px 0; }
    .placement-record-zone { display:grid; gap:12px; justify-items:start; margin-top:16px; }
    .placement-record { width:70px; height:70px; border-radius:50%; font-size:1.5rem; }
    .placement-record.recording { outline:3px solid rgba(255,120,140,.35); }
    .placement-result { margin-top:18px; padding:16px; border:1px solid #2a4059; border-radius:16px; background:#0c1622; }
    .placement-level { font-size:2rem; font-weight:800; margin:.2rem 0 .6rem; }
    .placement-columns { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    @media (max-width:760px) {
      .learner-switch span { display:none; }
      .placement-columns { grid-template-columns:1fr; }
      .placement-launch { width:100%; margin-left:0; }
      .language-setting-row { flex-wrap:wrap; }
    }
  `;
  document.head.appendChild(style);
}

function escapePlacement(value) {
  return typeof escapeHtml === 'function' ? escapeHtml(value) : String(value || '');
}

async function loadLearnerSwitcher() {
  installLearnerStyles();
  const result = await api('/api/users');
  focuslyraLearners.users = result.users || [];
  focuslyraLearners.currentUserId = result.current_user_id;

  const actions = document.querySelector('.top-actions');
  if (!actions) return;
  let host = document.getElementById('learnerSwitch');
  if (!host) {
    host = document.createElement('label');
    host.id = 'learnerSwitch';
    host.className = 'learner-switch';
    actions.prepend(host);
  }
  host.innerHTML = `
    <span>👤 Usuário</span>
    <select aria-label="Usuário atual">
      ${focuslyraLearners.users.map(user => `<option value="${escapePlacement(user.id)}" ${user.id === result.current_user_id ? 'selected' : ''}>${escapePlacement(user.display_name)}</option>`).join('')}
    </select>`;
  const select = host.querySelector('select');
  select.addEventListener('change', async () => {
    select.disabled = true;
    try {
      await api('/api/users/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: select.value }),
      });
      window.location.reload();
    } catch (error) {
      select.disabled = false;
      window.alert(`Não foi possível trocar de usuário: ${error.message}`);
    }
  });
}

function ensurePlacementModal() {
  let overlay = document.getElementById('placementOverlay');
  if (overlay) return overlay;
  overlay = document.createElement('div');
  overlay.id = 'placementOverlay';
  overlay.className = 'placement-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `
    <section class="placement-modal" role="dialog" aria-modal="true" aria-labelledby="placementTitle">
      <div class="placement-head">
        <div>
          <span class="badge">NIVELAMENTO</span>
          <h2 id="placementTitle">Descobrir meu nível</h2>
          <p id="placementNote" class="muted"></p>
        </div>
        <button type="button" class="ghost placement-close" aria-label="Fechar">✕</button>
      </div>
      <div class="placement-tabs">
        <button type="button" class="ghost placement-tab active" data-placement-mode="writing">✍ Escrever</button>
        <button type="button" class="ghost placement-tab" data-placement-mode="speaking">🎙 Falar</button>
      </div>
      <div class="placement-panel" data-placement-panel="writing">
        <p id="placementWritingPrompt" class="prompt"></p>
        <textarea id="placementText" placeholder="Escreva sem tradutor. O limite do que você consegue também é informação útil."></textarea>
        <button id="placementAnalyseText" type="button" class="primary">Avaliar meu nível</button>
      </div>
      <div class="placement-panel" data-placement-panel="speaking" hidden>
        <p id="placementSpeakingPrompt" class="prompt"></p>
        <div class="placement-record-zone">
          <button id="placementRecord" type="button" class="record-button placement-record">🎙</button>
          <p id="placementRecordStatus" class="muted">Grave até sentir que mostrou o que consegue fazer.</p>
          <audio id="placementPlayback" controls hidden></audio>
          <button id="placementAnalyseSpeech" type="button" class="primary" hidden>Avaliar gravação</button>
        </div>
      </div>
      <div id="placementResult" class="placement-result" hidden></div>
    </section>`;
  document.body.appendChild(overlay);

  overlay.querySelector('.placement-close').addEventListener('click', closePlacement);
  overlay.addEventListener('click', event => { if (event.target === overlay) closePlacement(); });
  overlay.querySelectorAll('.placement-tab').forEach(button => button.addEventListener('click', () => setPlacementMode(button.dataset.placementMode)));
  overlay.querySelector('#placementAnalyseText').addEventListener('click', analysePlacementText);
  overlay.querySelector('#placementRecord').addEventListener('click', togglePlacementRecording);
  overlay.querySelector('#placementAnalyseSpeech').addEventListener('click', analysePlacementSpeech);
  return overlay;
}

function setPlacementMode(mode) {
  focuslyraLearners.placement.mode = mode;
  const overlay = ensurePlacementModal();
  overlay.querySelectorAll('.placement-tab').forEach(button => button.classList.toggle('active', button.dataset.placementMode === mode));
  overlay.querySelectorAll('.placement-panel').forEach(panel => { panel.hidden = panel.dataset.placementPanel !== mode; });
  overlay.querySelector('#placementResult').hidden = true;
}

function stopPlacementStream() {
  focuslyraLearners.placement.stream?.getTracks?.().forEach(track => track.stop());
  focuslyraLearners.placement.stream = null;
}

function closePlacement() {
  const overlay = ensurePlacementModal();
  if (focuslyraLearners.placement.recorder?.state === 'recording') focuslyraLearners.placement.recorder.stop();
  stopPlacementStream();
  overlay.hidden = true;
}

async function openPlacement(languageCode) {
  const overlay = ensurePlacementModal();
  focuslyraLearners.placement.languageCode = languageCode;
  focuslyraLearners.placement.blob = null;
  focuslyraLearners.placement.chunks = [];
  const resultBox = overlay.querySelector('#placementResult');
  resultBox.hidden = true;
  overlay.querySelector('#placementText').value = '';
  overlay.querySelector('#placementPlayback').hidden = true;
  overlay.querySelector('#placementAnalyseSpeech').hidden = true;
  overlay.querySelector('#placementRecordStatus').textContent = 'Grave até sentir que mostrou o que consegue fazer.';
  overlay.hidden = false;
  overlay.querySelector('#placementTitle').textContent = 'Preparando nivelamento…';

  try {
    const prompts = await api(`/api/placement/${encodeURIComponent(languageCode)}`);
    focuslyraLearners.placement.prompts = prompts;
    overlay.querySelector('#placementTitle').textContent = `${prompts.language_name} · descobrir meu nível`;
    overlay.querySelector('#placementNote').textContent = prompts.note || '';
    overlay.querySelector('#placementWritingPrompt').textContent = prompts.writing_prompt || '';
    overlay.querySelector('#placementSpeakingPrompt').textContent = prompts.speaking_prompt || '';
    setPlacementMode('writing');
  } catch (error) {
    overlay.querySelector('#placementTitle').textContent = 'Nivelamento indisponível';
    resultBox.hidden = false;
    resultBox.textContent = error.message;
  }
}

async function refreshLearnerLanguagesAfterPlacement() {
  try {
    const languages = await api('/api/languages');
    if (typeof state !== 'undefined') state.languages = languages;
    if (typeof renderLanguages === 'function') renderLanguages(languages);
    if (typeof renderLanguageSettings === 'function') renderLanguageSettings(languages);
    enhancePlacementButtons();
  } catch (error) {
    console.warn('Could not refresh learner languages after placement:', error);
  }
}

function renderPlacementResult(result, transcript = '') {
  const overlay = ensurePlacementModal();
  const box = overlay.querySelector('#placementResult');
  const strengths = (result.strengths || []).map(item => `<li>${escapePlacement(item)}</li>`).join('');
  const gaps = (result.gaps || []).map(item => `<li>${escapePlacement(item)}</li>`).join('');
  box.hidden = false;
  box.innerHTML = `
    <span class="muted small">Nível estimado · confiança ${escapePlacement(result.confidence || 'low')}</span>
    <div class="placement-level">${escapePlacement(result.cefr_estimate || '?')}</div>
    ${transcript ? `<p class="muted small"><strong>Whisper ouviu:</strong> ${escapePlacement(transcript)}</p>` : ''}
    <p>${escapePlacement(result.summary || '')}</p>
    <div class="placement-columns">
      <div><strong>Pontos que já aparecem</strong>${strengths ? `<ul>${strengths}</ul>` : '<p class="muted small">Amostra curta para listar forças.</p>'}</div>
      <div><strong>Próximos alvos</strong>${gaps ? `<ul>${gaps}</ul>` : '<p class="muted small">Sem lacunas específicas suficientes nesta amostra.</p>'}</div>
    </div>
    <p><strong>Próximo passo:</strong> ${escapePlacement(result.next_step || '')}</p>
    <p class="muted small">O nível foi salvo no perfil para as próximas atividades. Não é uma certificação oficial.</p>`;
  refreshLearnerLanguagesAfterPlacement();
}

async function analysePlacementText() {
  const overlay = ensurePlacementModal();
  const button = overlay.querySelector('#placementAnalyseText');
  const text = overlay.querySelector('#placementText').value.trim();
  const resultBox = overlay.querySelector('#placementResult');
  if (!text) {
    resultBox.hidden = false;
    resultBox.textContent = 'Escreva pelo menos o que você conseguir antes de avaliar.';
    return;
  }
  button.disabled = true;
  button.textContent = 'Analisando localmente…';
  resultBox.hidden = false;
  resultBox.textContent = 'Qwen está estimando o nível a partir desta amostra…';
  try {
    const response = await api(`/api/placement/${encodeURIComponent(focuslyraLearners.placement.languageCode)}/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    renderPlacementResult(response.placement);
  } catch (error) {
    resultBox.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Avaliar meu nível';
  }
}

async function togglePlacementRecording() {
  const overlay = ensurePlacementModal();
  const record = overlay.querySelector('#placementRecord');
  const status = overlay.querySelector('#placementRecordStatus');
  if (focuslyraLearners.placement.recorder?.state === 'recording') {
    focuslyraLearners.placement.recorder.stop();
    record.classList.remove('recording');
    record.textContent = '🎙';
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    focuslyraLearners.placement.stream = stream;
    focuslyraLearners.placement.chunks = [];
    const recorder = new MediaRecorder(stream);
    focuslyraLearners.placement.recorder = recorder;
    recorder.addEventListener('dataavailable', event => { if (event.data.size) focuslyraLearners.placement.chunks.push(event.data); });
    recorder.addEventListener('stop', () => {
      const blob = new Blob(focuslyraLearners.placement.chunks, { type: recorder.mimeType || 'audio/webm' });
      focuslyraLearners.placement.blob = blob;
      const playback = overlay.querySelector('#placementPlayback');
      playback.src = URL.createObjectURL(blob);
      playback.hidden = false;
      overlay.querySelector('#placementAnalyseSpeech').hidden = false;
      status.textContent = 'Gravação pronta. Pode ouvir antes de enviar.';
      stopPlacementStream();
    });
    recorder.start();
    record.classList.add('recording');
    record.textContent = '■';
    status.textContent = 'Gravando… pressione novamente para parar.';
  } catch (error) {
    status.textContent = `Erro no microfone: ${error.message}`;
  }
}

async function analysePlacementSpeech() {
  const overlay = ensurePlacementModal();
  const button = overlay.querySelector('#placementAnalyseSpeech');
  const resultBox = overlay.querySelector('#placementResult');
  const blob = focuslyraLearners.placement.blob;
  if (!blob) return;
  button.disabled = true;
  button.textContent = 'Transcrevendo + analisando…';
  resultBox.hidden = false;
  resultBox.textContent = 'Whisper está transcrevendo e Qwen vai estimar o nível…';
  try {
    const form = new FormData();
    form.append('file', blob, 'focuslyra-placement.webm');
    form.append('language_code', focuslyraLearners.placement.languageCode);
    form.append('activity', 'placement speaking sample');
    form.append('activity_id', 'placement');
    const saved = await api('/api/recordings', { method: 'POST', body: form });
    const response = await api(`/api/placement/${encodeURIComponent(focuslyraLearners.placement.languageCode)}/recording/${encodeURIComponent(saved.recording.id)}`, { method: 'POST' });
    renderPlacementResult(response.placement, response.transcript?.text || '');
  } catch (error) {
    resultBox.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Avaliar gravação';
  }
}

function enhancePlacementButtons() {
  document.querySelectorAll('.language-setting-row').forEach(row => {
    if (row.querySelector('.placement-launch')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ghost placement-launch';
    button.textContent = '🎯 Nivelar idioma';
    button.addEventListener('click', () => openPlacement(row.dataset.code));
    row.appendChild(button);
  });
}

function watchLanguageSettings() {
  const host = document.getElementById('languageSettingsGrid');
  if (!host) return;
  new MutationObserver(enhancePlacementButtons).observe(host, { childList: true, subtree: true });
  enhancePlacementButtons();
}

loadLearnerSwitcher().catch(error => console.warn('Learner switcher unavailable:', error));
watchLanguageSettings();
ensurePlacementModal();
