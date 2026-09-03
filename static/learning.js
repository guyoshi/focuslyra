function learningScoreLabel(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return '';
  return `${Math.max(0, Math.min(100, Math.round(number)))}%`;
}

function browserSpeakFallback(text, languageCode) {
  if (!text || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = languageCode || 'en-GB';
  utterance.rate = 0.92;
  const voices = window.speechSynthesis.getVoices();
  const exact = voices.find(voice => voice.lang?.toLowerCase() === utterance.lang.toLowerCase());
  const base = (languageCode || '').split('-')[0].toLowerCase();
  const fallback = voices.find(voice => voice.lang?.toLowerCase().startsWith(`${base}-`));
  if (exact || fallback) utterance.voice = exact || fallback;
  window.speechSynthesis.speak(utterance);
}

async function speakLocally(text, languageCode, voice = null) {
  if (!text) return;
  try {
    const status = await api('/api/tts/status');
    if (status.configured && languageCode === 'en-GB') {
      const result = await api('/api/tts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language_code: languageCode, voice, speed: 1.0 }),
      });
      const audio = new Audio(result.url);
      await audio.play();
      return;
    }
  } catch (error) {
    console.warn('Local persistent TTS unavailable, using browser fallback:', error);
  }
  browserSpeakFallback(text, languageCode);
}

function renderLearningFeedback(container, result, languageCode, transcriptText = '') {
  const analysis = result?.analysis || {};
  const strengths = Array.isArray(analysis.strengths) ? analysis.strengths : [];
  const corrections = Array.isArray(analysis.corrections) ? analysis.corrections : [];
  const patterns = Array.isArray(analysis.patterns_to_revisit) ? analysis.patterns_to_revisit : [];
  const scores = analysis.scores && typeof analysis.scores === 'object' ? analysis.scores : {};
  const next = analysis.next_activity && typeof analysis.next_activity === 'object' ? analysis.next_activity : {};

  const scoresHtml = Object.entries(scores).map(([key, value]) => `
    <div class="learning-score">
      <span>${escapeHtml(key.replaceAll('_', ' '))}</span>
      <strong>${escapeHtml(learningScoreLabel(value))}</strong>
    </div>`).join('');

  const correctionHtml = corrections.slice(0, 5).map(item => `
    <div class="learning-correction">
      <span class="muted small">${escapeHtml(item.category || 'correction')}</span>
      <div><del>${escapeHtml(item.original || '')}</del></div>
      <div><strong>${escapeHtml(item.natural || '')}</strong></div>
      <div class="muted small">${escapeHtml(item.reason || '')}</div>
    </div>`).join('');

  const strengthHtml = strengths.slice(0, 4).map(item => `<li>${escapeHtml(item)}</li>`).join('');
  const patternHtml = patterns.slice(0, 5).map(item => {
    const label = typeof item === 'object' ? (item.item || item.pattern || '') : item;
    return `<span>${escapeHtml(label)}</span>`;
  }).join('');
  const audioText = String(next.audio_text || '').trim();

  container.hidden = false;
  container.className = 'feedback good learning-feedback';
  container.innerHTML = `
    <div class="learning-feedback-head">
      <div>
        <strong>Local AI analysis · Session #${escapeHtml(result.session_id || '')}</strong>
        <div class="muted small">${escapeHtml(analysis.model || 'local model')} · learner evidence saved</div>
      </div>
    </div>
    ${transcriptText ? `<div class="learning-transcript"><span class="muted small">Local transcript</span><p>${escapeHtml(transcriptText)}</p></div>` : ''}
    <p>${escapeHtml(analysis.summary || 'Analysis completed.')}</p>
    ${scoresHtml ? `<div class="learning-scores">${scoresHtml}</div>` : ''}
    ${strengthHtml ? `<div class="learning-block"><strong>What worked</strong><ul>${strengthHtml}</ul></div>` : ''}
    ${correctionHtml ? `<div class="learning-block"><strong>Useful corrections</strong>${correctionHtml}</div>` : ''}
    ${patternHtml ? `<div class="learning-block"><strong>Coming back later</strong><div class="target-list">${patternHtml}</div></div>` : ''}
    <div class="learning-next">
      <span class="badge">NEXT · ${escapeHtml(next.type || 'review')}</span>
      <p><strong>${escapeHtml(next.prompt || 'Try the idea again in a new sentence.')}</strong></p>
      ${audioText ? `<button type="button" class="ghost speak-generated-audio">🔊 Hear generated practice audio</button>` : ''}
    </div>`;

  const audioButton = container.querySelector('.speak-generated-audio');
  if (audioButton) audioButton.addEventListener('click', () => speakLocally(audioText, languageCode));
}

async function attachAcousticButton(container, recordingId) {
  try {
    const status = await api('/api/pronunciation/status');
    if (!status.configured || !recordingId) return;
    const host = document.createElement('div');
    host.className = 'learning-block';
    host.innerHTML = `
      <strong>Original audio signal</strong>
      <p class="muted small">Praat can measure the recording itself. This is not yet a phoneme/accent score.</p>
      <button type="button" class="ghost acoustic-button">👄 Measure acoustic signal</button>
      <div class="acoustic-result muted small" hidden></div>`;
    container.appendChild(host);
    const button = host.querySelector('.acoustic-button');
    const output = host.querySelector('.acoustic-result');
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Measuring locally…';
      try {
        const result = await api(`/api/pronunciation/analyse-recording/${encodeURIComponent(recordingId)}`, { method: 'POST' });
        const a = result.acoustics || {};
        output.hidden = false;
        output.innerHTML = `Duration: ${escapeHtml(a.duration_seconds ?? '')}s · voiced frames: ${escapeHtml(Math.round((a.pitch?.voiced_frame_ratio || 0) * 100))}% · pitch range: ${escapeHtml(a.pitch?.min_hz ?? '—')}–${escapeHtml(a.pitch?.max_hz ?? '—')} Hz<br>${escapeHtml(a.warning || '')}`;
        button.textContent = '✓ Acoustic signal measured';
      } catch (error) {
        output.hidden = false;
        output.textContent = error.message;
        button.disabled = false;
        button.textContent = 'Try acoustic analysis again';
      }
    });
  } catch (error) {
    console.warn(error);
  }
}

async function focuslyraAnalyseWriting(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
  const text = document.getElementById('writingInput').value.trim();
  const resultBox = document.getElementById('writingResult');
  const button = document.getElementById('saveWriting');
  if (!text) {
    resultBox.hidden = false;
    resultBox.className = 'feedback';
    resultBox.textContent = 'Write something first. The messy first draft is useful data.';
    return;
  }

  button.disabled = true;
  button.textContent = 'Qwen is analysing…';
  resultBox.hidden = false;
  resultBox.className = 'feedback';
  resultBox.textContent = 'Your original is being preserved. The local learning engine is looking for useful patterns, not every tiny mistake.';

  try {
    const result = await api('/api/learning/analyse-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language_code: 'es-ES',
        modality: 'writing',
        text,
        exercise_prompt: 'Describe your morning in 5–8 sentences.',
        metadata: { exercise: 'describe-morning', source: 'study-ui' },
      }),
    });
    renderLearningFeedback(resultBox, result, 'es-ES');
    button.textContent = '✓ Analysed + remembered';
  } catch (error) {
    resultBox.hidden = false;
    resultBox.className = 'feedback';
    resultBox.textContent = `Local analysis could not run: ${error.message}`;
    button.disabled = false;
    button.textContent = 'Try analysis again';
  }
}

async function focuslyraSaveAndAnalyseRecording(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
  if (!state.recordingBlob) return;

  const button = document.getElementById('saveRecording');
  const feedback = document.getElementById('recordFeedback');
  button.disabled = true;
  button.textContent = 'Saving recording…';

  const form = new FormData();
  form.append('file', state.recordingBlob, 'speaking.webm');
  form.append('language_code', 'es-ES');
  form.append('activity', 'Hotel reservation roleplay: explain the booking, ask them to check again, react if full.');

  try {
    const saved = await api('/api/recordings', { method: 'POST', body: form });
    const recordingId = saved.recording.id;
    state.lastRecordingId = recordingId;
    feedback.hidden = false;
    feedback.className = 'feedback';
    feedback.innerHTML = `<strong>Recording saved locally.</strong><br><span class="muted small">${escapeHtml(saved.recording.relative_audio_path)}</span><br><br>Whisper is transcribing it locally, then Qwen will analyse the language…`;
    button.textContent = 'Transcribing locally…';

    try {
      const analysed = await api(`/api/learning/analyse-recording/${encodeURIComponent(recordingId)}`, { method: 'POST' });
      renderLearningFeedback(feedback, analysed, 'es-ES', analysed.transcript?.text || '');
      await attachAcousticButton(feedback, recordingId);
      button.textContent = '✓ Analysed + remembered';
    } catch (analysisError) {
      feedback.hidden = false;
      feedback.className = 'feedback';
      feedback.innerHTML = `<strong>Recording saved safely.</strong><br>${escapeHtml(analysisError.message)}<br><span class="muted small">If this mentions local transcription, run configure_free_audio.bat once. Nothing paid is required.</span>`;
      button.disabled = false;
      button.textContent = 'Retry audio analysis';
    }
  } catch (error) {
    feedback.hidden = false;
    feedback.className = 'feedback';
    feedback.textContent = `Could not save recording: ${error.message}`;
    button.disabled = false;
    button.textContent = 'Try save again';
  }
}

async function injectVoiceCalibration() {
  const panel = document.getElementById('mode-pronounce');
  if (!panel || document.getElementById('rpVoiceCalibration')) return;
  const section = document.createElement('div');
  section.id = 'rpVoiceCalibration';
  section.className = 'feedback';
  section.innerHTML = '<strong>🇬🇧 RP reference voice calibration</strong><p class="muted small">Checking local voice engine…</p>';
  panel.appendChild(section);
  try {
    const status = await api('/api/tts/status');
    if (!status.configured) {
      section.innerHTML = '<strong>🇬🇧 RP reference voice calibration</strong><p class="muted small">Run <code>configure_local_tts.bat</code> after the Whisper download finishes. Browser speech remains a temporary fallback.</p>';
      return;
    }
    const calibration = await api('/api/tts/calibration-prompts');
    const sample = calibration.prompts?.find(p => p.id === 'connected') || calibration.prompts?.[0];
    section.innerHTML = `
      <strong>🇬🇧 RP reference voice calibration</strong>
      <p class="muted small">Audition the British candidates. We will not label one "RP reference" until it passes this calibration.</p>
      <p>${escapeHtml(sample?.text || '')}</p>
      <div class="target-list calibration-voices">${(calibration.voices || []).map(v => `<button type="button" class="ghost calibration-voice" data-voice="${escapeHtml(v)}">🔊 ${escapeHtml(v)}</button>`).join('')}</div>
      <p class="muted small">${escapeHtml(calibration.warning || '')}</p>`;
    section.querySelectorAll('.calibration-voice').forEach(button => {
      button.addEventListener('click', async () => {
        const old = button.textContent;
        button.textContent = 'Generating…';
        button.disabled = true;
        await speakLocally(sample.text, 'en-GB', button.dataset.voice);
        button.textContent = old;
        button.disabled = false;
      });
    });
  } catch (error) {
    section.innerHTML = `<strong>🇬🇧 RP reference voice calibration</strong><p class="muted small">${escapeHtml(error.message)}</p>`;
  }
}

async function injectLearningEngineStatus() {
  const side = document.querySelector('.study-side');
  if (!side || document.getElementById('localLearningStatus')) return;
  const box = document.createElement('div');
  box.id = 'localLearningStatus';
  box.className = 'local-engine-status';
  box.innerHTML = '<strong>🧠 Local learning engine</strong><span class="muted small">Checking…</span>';
  side.prepend(box);
  try {
    const [providers, audio, tts, pronunciation] = await Promise.all([
      api('/api/providers'),
      api('/api/audio/status'),
      api('/api/tts/status'),
      api('/api/pronunciation/status'),
    ]);
    const ollama = providers.find(provider => provider.id === 'ollama');
    box.innerHTML = `
      <strong>🧠 Local learning engine</strong>
      <span class="${ollama?.enabled ? 'engine-ok' : 'engine-warn'}">${ollama?.enabled ? 'Qwen ready' : 'Qwen not ready'}</span>
      <small>Speech transcription: ${audio.local_stt_configured ? 'ready' : 'setup needed'}</small>
      <small>Persistent local voice: ${tts.configured ? 'Kokoro ready' : 'browser fallback'}</small>
      <small>Acoustic pronunciation: ${pronunciation.configured ? 'ready' : 'setup optional'}</small>
      <small>Per-token cost: €0</small>`;
  } catch (error) {
    box.innerHTML = `<strong>🧠 Local learning engine</strong><small>${escapeHtml(error.message)}</small>`;
  }
}

const focuslyraWriteButton = document.getElementById('saveWriting');
if (focuslyraWriteButton) focuslyraWriteButton.addEventListener('click', focuslyraAnalyseWriting, { capture: true });
const focuslyraRecordingButton = document.getElementById('saveRecording');
if (focuslyraRecordingButton) focuslyraRecordingButton.addEventListener('click', focuslyraSaveAndAnalyseRecording, { capture: true });

injectLearningEngineStatus();
injectVoiceCalibration();
