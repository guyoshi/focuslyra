const studyRuntime = {
  plan: null,
  index: 0,
  activity: null,
  recordingBlob: null,
  recorder: null,
  stream: null,
  chunks: [],
};

function learningScoreLabel(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return '';
  return `${Math.max(0, Math.min(100, Math.round(number)))}%`;
}

function voiceProfile(languageCode) {
  return window.FocuslyraVoice?.getProfile?.(languageCode) || {};
}

function preferredVoice(languageCode, purpose = 'default') {
  return window.FocuslyraVoice?.getVoice?.(languageCode, purpose) || null;
}

function browserSpeakFallback(text, languageCode, voiceName = null, speed = null) {
  if (!text || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = languageCode || 'en-GB';
  utterance.rate = Number(speed || voiceProfile(languageCode).speed || 0.92);
  const voices = window.speechSynthesis.getVoices();
  const named = voiceName ? voices.find(voice => voice.name === voiceName) : null;
  const exact = voices.find(voice => voice.lang?.toLowerCase() === utterance.lang.toLowerCase());
  const base = (languageCode || '').split('-')[0].toLowerCase();
  const fallback = voices.find(voice => voice.lang?.toLowerCase().startsWith(`${base}-`));
  if (named || exact || fallback) utterance.voice = named || exact || fallback;
  window.speechSynthesis.speak(utterance);
}

async function speakLocally(text, languageCode, purpose = 'default', audioUrl = null) {
  if (!text) return;
  if (audioUrl) {
    const audio = new Audio(audioUrl);
    await audio.play();
    return;
  }
  const profile = voiceProfile(languageCode);
  const selectedVoice = preferredVoice(languageCode, purpose);
  const speed = Number(profile.speed || 1.0);
  try {
    const status = await api('/api/tts/status');
    const canUseKokoro = status.configured && (status.supported_languages || []).includes(languageCode);
    if (canUseKokoro && profile.engine !== 'browser') {
      const result = await api('/api/tts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language_code: languageCode, voice: selectedVoice, speed, purpose }),
      });
      const audio = new Audio(result.url);
      await audio.play();
      return;
    }
  } catch (error) {
    console.warn('Persistent TTS unavailable, using system voice:', error);
  }
  browserSpeakFallback(text, languageCode, selectedVoice, speed);
}

function renderLearningFeedback(container, result, languageCode, transcriptText = '') {
  const analysis = result?.analysis || {};
  const strengths = Array.isArray(analysis.strengths) ? analysis.strengths : [];
  const corrections = Array.isArray(analysis.corrections) ? analysis.corrections : [];
  const patterns = Array.isArray(analysis.patterns_to_revisit) ? analysis.patterns_to_revisit : [];
  const scores = analysis.scores && typeof analysis.scores === 'object' ? analysis.scores : {};

  const scoresHtml = Object.entries(scores).map(([key, value]) => `
    <div class="learning-score"><span>${escapeHtml(key.replaceAll('_', ' '))}</span><strong>${escapeHtml(learningScoreLabel(value))}</strong></div>`).join('');
  const correctionsHtml = corrections.slice(0, 5).map(item => `
    <div class="learning-correction">
      <span class="muted small">${escapeHtml(item.category || 'correction')}</span>
      <div><del>${escapeHtml(item.original || '')}</del></div>
      <div><strong>${escapeHtml(item.natural || '')}</strong></div>
      <div class="muted small">${escapeHtml(item.reason || '')}</div>
    </div>`).join('');
  const strengthsHtml = strengths.slice(0, 4).map(item => `<li>${escapeHtml(item)}</li>`).join('');
  const patternsHtml = patterns.slice(0, 5).map(item => {
    const label = typeof item === 'object' ? (item.item || item.pattern || '') : item;
    return `<span>${escapeHtml(label)}</span>`;
  }).join('');

  container.hidden = false;
  container.className = 'feedback good learning-feedback';
  container.innerHTML = `
    <div class="learning-feedback-head">
      <div><strong>Analysed locally · Session #${escapeHtml(result.session_id || '')}</strong>
      <div class="muted small">${escapeHtml(analysis.model || 'local model')} · evidence saved</div></div>
    </div>
    ${transcriptText ? `<div class="learning-transcript"><span class="muted small">Local transcript</span><p>${escapeHtml(transcriptText)}</p></div>` : ''}
    <p>${escapeHtml(analysis.summary || 'Analysis completed.')}</p>
    ${scoresHtml ? `<div class="learning-scores">${scoresHtml}</div>` : ''}
    ${strengthsHtml ? `<div class="learning-block"><strong>What worked</strong><ul>${strengthsHtml}</ul></div>` : ''}
    ${correctionsHtml ? `<div class="learning-block"><strong>Useful corrections</strong>${correctionsHtml}</div>` : ''}
    ${patternsHtml ? `<div class="learning-block"><strong>Saved for future retrieval</strong><div class="target-list">${patternsHtml}</div></div>` : ''}
    <button type="button" class="primary continue-plan">Continue today's plan →</button>`;
  container.querySelector('.continue-plan')?.addEventListener('click', nextPlannedActivity);
}

function renderPronunciationFeedback(container, response) {
  const a = response?.assessment || {};
  const scores = a.scores || {};
  const scoreHtml = Object.entries(scores).filter(([, value]) => value !== null).map(([key, value]) => `
    <div class="learning-score"><span>${escapeHtml(key.replaceAll('_', ' '))}</span><strong>${escapeHtml(learningScoreLabel(value))}</strong></div>`).join('');
  const notes = (a.feedback || []).map(item => `<li>${escapeHtml(item)}</li>`).join('');
  container.hidden = false;
  container.className = 'feedback good learning-feedback';
  container.innerHTML = `
    <strong>Controlled pronunciation assessment · Session #${escapeHtml(a.session_id || '')}</strong>
    <div class="learning-transcript"><span class="muted small">Reference</span><p>${escapeHtml(a.reference_text || '')}</p>
    <span class="muted small">Whisper heard</span><p>${escapeHtml(a.heard_text || '')}</p></div>
    <div class="learning-scores">${scoreHtml}</div>
    ${notes ? `<div class="learning-block"><strong>What to change</strong><ul>${notes}</ul></div>` : ''}
    <p class="muted small">${escapeHtml(a.warning || '')}</p>
    <button type="button" class="primary continue-plan">Continue today's plan →</button>`;
  container.querySelector('.continue-plan')?.addEventListener('click', nextPlannedActivity);
}

function plannerSlot() {
  return studyRuntime.plan?.activities?.[studyRuntime.index] || null;
}

function updatePlanSidebar() {
  const side = document.querySelector('.study-side');
  if (!side || !studyRuntime.plan) return;
  const activities = studyRuntime.plan.activities || [];
  const rows = activities.map((item, index) => `
    <div class="activity ${index === studyRuntime.index ? 'current-plan-item' : ''}">
      <span>${escapeHtml(item.flag || '')} ${escapeHtml(item.language_name || item.language_code)} · ${escapeHtml(item.modality)}</span>
      <strong>${escapeHtml(item.minutes)}m</strong>
    </div>`).join('');
  side.innerHTML = `
    <h3>Today's plan</h3>
    <p class="muted small">${escapeHtml(studyRuntime.plan.total_minutes)} minutes · planned from priority, recency and your evidence.</p>
    <div class="plan-list">${rows}</div>
    <hr />
    <h3>Attention rescue</h3>
    <p class="muted">Bored? Keep the learning target and change the wrapper.</p>
    <button id="switchActivityDynamic" class="ghost full">🎲 Change this activity</button>
    <hr />
    <div id="localLearningStatus"></div>`;
  side.querySelector('#switchActivityDynamic')?.addEventListener('click', changeCurrentActivity);
  injectLearningEngineStatus(true);
}

function activityBadge(activity) {
  return `${activity.flag || ''} ${String(activity.language_name || activity.language_code || '').toUpperCase()} · ${String(activity.modality || '').toUpperCase()} · ${activity.minutes || 5} MIN`;
}

function setDynamicPanel(mode, html) {
  setMode(mode);
  const panel = document.getElementById(`mode-${mode}`);
  panel.innerHTML = html;
  return panel;
}

function commonHeader(activity) {
  return `
    <span class="badge">${escapeHtml(activityBadge(activity))}</span>
    <h2>${escapeHtml(activity.title || 'Study')}</h2>
    <p class="prompt">${escapeHtml(activity.instructions || '')}</p>`;
}

function renderActivity(activity) {
  studyRuntime.activity = activity;
  studyRuntime.recordingBlob = null;
  state.currentLanguageCode = activity.language_code;
  document.getElementById('pageSubtitle').textContent = `${activity.flag || ''} ${activity.language_name} · ${activity.target_variety || ''} · activity ${studyRuntime.index + 1}/${studyRuntime.plan?.activities?.length || 1}`;
  updatePlanSidebar();

  if (activity.modality === 'write') return renderWriteActivity(activity);
  if (activity.modality === 'listen') return renderListenActivity(activity);
  if (activity.modality === 'read') return renderReadActivity(activity);
  if (activity.modality === 'pronounce') return renderPronounceActivity(activity);
  return renderSpeakActivity(activity);
}

function recordingControls(activity, pronunciation = false) {
  return `
    <div class="recording-zone">
      <button class="record-button dynamic-record" aria-label="Record audio">🎙</button>
      <p class="dynamic-record-status muted">Press to record. Press again to stop.</p>
      <audio class="dynamic-recording-playback" controls hidden></audio>
      <button class="primary dynamic-save-recording" hidden>${pronunciation ? 'Assess pronunciation' : 'Save + analyse'}</button>
    </div>
    <div class="dynamic-feedback feedback" hidden></div>`;
}

function renderSpeakActivity(activity) {
  const panel = setDynamicPanel('speak', `${commonHeader(activity)}<p class="prompt activity-question">${escapeHtml(activity.prompt || '')}</p>${recordingControls(activity)}`);
  wireRecording(panel, activity, false);
}

function renderWriteActivity(activity) {
  const panel = setDynamicPanel('write', `${commonHeader(activity)}
    <p class="prompt activity-question">${escapeHtml(activity.prompt || '')}</p>
    <textarea class="dynamic-text-response" placeholder="${escapeHtml(activity.placeholder || 'Write your answer…')}"></textarea>
    <button class="primary dynamic-submit-text">Submit + analyse</button>
    <div class="dynamic-feedback feedback" hidden></div>`);
  wireTextSubmission(panel, activity, 'writing');
}

function renderListenActivity(activity) {
  const panel = setDynamicPanel('listen', `${commonHeader(activity)}
    <button class="primary dynamic-play-audio">▶ Play audio</button>
    <p class="prompt activity-question">${escapeHtml(activity.prompt || 'What did you understand?')}</p>
    <textarea class="dynamic-text-response" placeholder="${escapeHtml(activity.placeholder || 'Answer after listening…')}"></textarea>
    <button class="primary dynamic-submit-text">Submit listening answer</button>
    <button class="ghost dynamic-reveal-transcript" type="button">Reveal transcript after my attempt</button>
    <div class="dynamic-transcript feedback" hidden></div>
    <div class="dynamic-feedback feedback" hidden></div>`);
  panel.querySelector('.dynamic-play-audio').addEventListener('click', () => speakLocally(activity.audio_text, activity.language_code, 'listening', activity.audio?.url));
  panel.querySelector('.dynamic-reveal-transcript').addEventListener('click', () => {
    const box = panel.querySelector('.dynamic-transcript');
    box.hidden = false;
    box.innerHTML = `<span class="muted small">Transcript</span><p>${escapeHtml(activity.audio_text || '')}</p>`;
  });
  wireTextSubmission(panel, activity, 'listening-response');
}

function renderReadActivity(activity) {
  const direction = state.languages?.find(item => item.code === activity.language_code)?.writing_direction === 'rtl' ? 'rtl' : 'ltr';
  const panel = setDynamicPanel('read', `${commonHeader(activity)}
    <div class="feedback reading-passage" dir="${direction}">${escapeHtml(activity.input_text || '')}</div>
    <p class="prompt activity-question">${escapeHtml(activity.prompt || '')}</p>
    <textarea class="dynamic-text-response" placeholder="${escapeHtml(activity.placeholder || 'Your answer…')}"></textarea>
    <button class="primary dynamic-submit-text">Submit comprehension answer</button>
    <div class="dynamic-feedback feedback" hidden></div>`);
  wireTextSubmission(panel, activity, 'reading-response');
}

function renderPronounceActivity(activity) {
  const panel = setDynamicPanel('pronounce', `${commonHeader(activity)}
    <p class="muted small">Target feature: ${escapeHtml(activity.target_feature || 'timing and prosody')}</p>
    <div class="feedback pronunciation-reference"><strong>${escapeHtml(activity.reference_text || '')}</strong></div>
    <button class="ghost dynamic-play-reference">🔊 Hear reference</button>
    ${recordingControls(activity, true)}`);
  panel.querySelector('.dynamic-play-reference').addEventListener('click', () => speakLocally(activity.reference_text, activity.language_code, 'reference', activity.audio?.url));
  wireRecording(panel, activity, true);
}

function wireTextSubmission(panel, activity, modality) {
  const button = panel.querySelector('.dynamic-submit-text');
  const input = panel.querySelector('.dynamic-text-response');
  const feedback = panel.querySelector('.dynamic-feedback');
  button.addEventListener('click', async () => {
    const text = input.value.trim();
    if (!text) {
      feedback.hidden = false;
      feedback.textContent = 'Answer first. An imperfect attempt is useful evidence.';
      return;
    }
    button.disabled = true;
    button.textContent = 'Analysing locally…';
    feedback.hidden = false;
    feedback.textContent = 'Qwen is looking for useful patterns and saving evidence.';
    const context = [activity.prompt, activity.input_text ? `Reading source: ${activity.input_text}` : '', activity.audio_text ? `Listening source: ${activity.audio_text}` : ''].filter(Boolean).join('\n\n');
    try {
      const result = await api('/api/learning/analyse-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          language_code: activity.language_code,
          modality,
          text,
          exercise_prompt: context,
          metadata: { activity_id: activity.activity_id, target_feature: activity.target_feature, source: 'adaptive-study' },
        }),
      });
      renderLearningFeedback(feedback, result, activity.language_code);
      button.textContent = '✓ Analysed + remembered';
    } catch (error) {
      feedback.hidden = false;
      feedback.className = 'feedback';
      feedback.textContent = `Local analysis could not run: ${error.message}`;
      button.disabled = false;
      button.textContent = 'Try again';
    }
  });
}

function wireRecording(panel, activity, pronunciation) {
  const record = panel.querySelector('.dynamic-record');
  const status = panel.querySelector('.dynamic-record-status');
  const playback = panel.querySelector('.dynamic-recording-playback');
  const save = panel.querySelector('.dynamic-save-recording');
  const feedback = panel.querySelector('.dynamic-feedback');

  record.addEventListener('click', async () => {
    if (studyRuntime.recorder?.state === 'recording') {
      studyRuntime.recorder.stop();
      record.classList.remove('recording');
      record.textContent = '🎙';
      return;
    }
    try {
      studyRuntime.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      studyRuntime.chunks = [];
      studyRuntime.recorder = new MediaRecorder(studyRuntime.stream);
      studyRuntime.recorder.addEventListener('dataavailable', event => { if (event.data.size) studyRuntime.chunks.push(event.data); });
      studyRuntime.recorder.addEventListener('stop', () => {
        studyRuntime.recordingBlob = new Blob(studyRuntime.chunks, { type: studyRuntime.recorder.mimeType || 'audio/webm' });
        playback.src = URL.createObjectURL(studyRuntime.recordingBlob);
        playback.hidden = false;
        save.hidden = false;
        status.textContent = 'Recorded locally. Listen once if you want, then submit.';
        studyRuntime.stream?.getTracks().forEach(track => track.stop());
      });
      studyRuntime.recorder.start();
      record.classList.add('recording');
      record.textContent = '■';
      status.textContent = 'Recording… press again to stop.';
    } catch (error) {
      status.textContent = `Microphone error: ${error.message}`;
    }
  });

  save.addEventListener('click', async () => {
    if (!studyRuntime.recordingBlob) return;
    save.disabled = true;
    save.textContent = pronunciation ? 'Measuring locally…' : 'Saving + transcribing…';
    const form = new FormData();
    form.append('file', studyRuntime.recordingBlob, 'focuslyra-speaking.webm');
    form.append('language_code', activity.language_code);
    form.append('activity', `${activity.title}: ${activity.prompt}`);
    form.append('activity_id', activity.activity_id || '');
    form.append('reference_text', activity.reference_text || '');
    form.append('target_feature', activity.target_feature || '');
    try {
      const saved = await api('/api/recordings', { method: 'POST', body: form });
      const recordingId = saved.recording.id;
      feedback.hidden = false;
      feedback.textContent = pronunciation ? 'Comparing your recording to the local reference…' : 'Whisper is transcribing locally, then Qwen will analyse the language…';
      if (pronunciation) {
        const assessed = await api(`/api/pronunciation/assess/${encodeURIComponent(recordingId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reference_text: activity.reference_text, language_code: activity.language_code, target_feature: activity.target_feature }),
        });
        renderPronunciationFeedback(feedback, assessed);
      } else {
        const analysed = await api(`/api/learning/analyse-recording/${encodeURIComponent(recordingId)}`, { method: 'POST' });
        renderLearningFeedback(feedback, analysed, activity.language_code, analysed.transcript?.text || '');
      }
      save.textContent = '✓ Saved + analysed';
    } catch (error) {
      feedback.hidden = false;
      feedback.className = 'feedback';
      feedback.textContent = error.message;
      save.disabled = false;
      save.textContent = 'Try again';
    }
  });
}

async function loadActivityForSlot(slot) {
  const result = await api('/api/study/activity', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(slot),
  });
  renderActivity(result.activity);
}

async function nextPlannedActivity() {
  if (!studyRuntime.plan) return;
  if (studyRuntime.index >= studyRuntime.plan.activities.length - 1) {
    const panel = document.getElementById(`mode-${studyRuntime.activity?.modality || 'speak'}`);
    panel.innerHTML = `
      <span class="badge">SESSION COMPLETE</span>
      <h2>Today's planned work is done.</h2>
      <p class="prompt">Your attempts and evidence are saved. Tomorrow's planner can use what happened today.</p>
      <button class="primary finish-to-dashboard">Back to dashboard</button>`;
    panel.querySelector('.finish-to-dashboard').addEventListener('click', () => setView('dashboard'));
    return;
  }
  studyRuntime.index += 1;
  updatePlanSidebar();
  const slot = plannerSlot();
  await loadActivityForSlot(slot);
}

async function changeCurrentActivity() {
  const slot = plannerSlot();
  if (!slot) return;
  const modes = ['speak', 'listen', 'write', 'read', 'pronounce'];
  const current = studyRuntime.activity?.modality || slot.modality || 'speak';
  const next = modes[(modes.indexOf(current) + 1) % modes.length];
  await loadActivityForSlot({ ...slot, modality: next, reason: `${slot.reason || ''}; learner requested a different activity wrapper` });
}

async function startAdaptiveSession(mode = 'normal') {
  setView('study');
  document.getElementById('pageSubtitle').textContent = 'Building today’s plan from your priorities and evidence…';
  try {
    const today = await api(`/api/study/today?mode=${encodeURIComponent(mode)}`);
    studyRuntime.plan = today.plan;
    studyRuntime.index = 0;
    state.sessionDurationMinutes = today.plan.total_minutes;
    state.currentLanguageCode = today.activity.language_code;
    renderActivity(today.activity);
  } catch (error) {
    const panel = setDynamicPanel('speak', `<span class="badge">SETUP</span><h2>Could not build today's session.</h2><p class="prompt">${escapeHtml(error.message)}</p>`);
    console.error(error);
  }
}

async function loadPlanPreview() {
  const host = document.getElementById('suggestedRhythm');
  if (!host) return;
  try {
    const result = await api('/api/study/today?mode=normal');
    const grouped = new Map();
    for (const item of result.plan.activities || []) {
      const existing = grouped.get(item.language_code) || { flag: item.flag, name: item.language_name, minutes: 0 };
      existing.minutes += Number(item.minutes || 0);
      grouped.set(item.language_code, existing);
    }
    host.innerHTML = [...grouped.values()].map(item => `<div class="activity"><span>${escapeHtml(item.flag || '')} ${escapeHtml(item.name || '')}</span><strong>${escapeHtml(item.minutes)}m</strong></div>`).join('');
    const note = host.nextElementSibling;
    if (note) note.textContent = 'Calculated from your current priorities, recency and saved evidence.';
  } catch (error) {
    host.innerHTML = `<span class="muted small">Plan preview unavailable: ${escapeHtml(error.message)}</span>`;
  }
}

async function injectLearningEngineStatus(force = false) {
  const host = document.getElementById('localLearningStatus') || document.querySelector('.study-side');
  if (!host) return;
  if (!force && document.getElementById('localLearningStatus')?.dataset.loaded === '1') return;
  const box = host.id === 'localLearningStatus' ? host : document.createElement('div');
  if (!box.id) {
    box.id = 'localLearningStatus';
    host.prepend(box);
  }
  box.className = 'local-engine-status';
  box.innerHTML = '<strong>🧠 Local engine</strong><span class="muted small">Checking…</span>';
  try {
    const [providers, audio, tts, pronunciation] = await Promise.all([
      api('/api/providers'), api('/api/audio/status'), api('/api/tts/status'), api('/api/pronunciation/status'),
    ]);
    const ollama = providers.find(provider => provider.id === 'ollama');
    box.innerHTML = `
      <strong>🧠 Local engine</strong>
      <span class="${ollama?.enabled ? 'engine-ok' : 'engine-warn'}">${ollama?.enabled ? 'Qwen ready' : 'Qwen setup needed'}</span>
      <small>Whisper: ${audio.local_stt_configured ? 'ready' : 'setup needed'}</small>
      <small>Kokoro: ${tts.configured ? 'ready' : 'browser fallback'}</small>
      <small>Pronunciation: ${pronunciation.configured ? 'controlled assessment ready' : 'setup needed'}</small>
      <small>API cost: €0</small>`;
    box.dataset.loaded = '1';
  } catch (error) {
    box.innerHTML = `<strong>🧠 Local engine</strong><small>${escapeHtml(error.message)}</small>`;
  }
}

// Override the old static Start handlers before their target-phase listeners run.
document.addEventListener('click', event => {
  const start = event.target.closest?.('#startSession');
  const quick = event.target.closest?.('#quickTen');
  const interesting = event.target.closest?.('#makeInteresting');
  if (start || quick || interesting) {
    event.preventDefault();
    event.stopImmediatePropagation();
    startAdaptiveSession(quick ? 'minimum' : 'normal');
  }
}, true);

// Manual mode tabs keep the same language/retrieval targets but regenerate the wrapper.
document.querySelectorAll('.mode-tab').forEach(button => {
  button.addEventListener('click', event => {
    if (!studyRuntime.plan) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const slot = plannerSlot();
    if (slot) loadActivityForSlot({ ...slot, modality: button.dataset.mode, reason: `${slot.reason || ''}; learner selected ${button.dataset.mode}` });
  }, true);
});

loadPlanPreview();
injectLearningEngineStatus();

if (!document.querySelector('script[data-focuslyra-voice-settings]')) {
  const voiceSettingsScript = document.createElement('script');
  voiceSettingsScript.src = '/static/voice-settings.js';
  voiceSettingsScript.dataset.focuslyraVoiceSettings = '1';
  document.body.appendChild(voiceSettingsScript);
}
