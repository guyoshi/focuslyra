const state = {
  recorder: null,
  stream: null,
  chunks: [],
  recordingBlob: null,
  currentView: 'dashboard',
  currentMode: 'speak',
  calendarStatus: null,
  currentLanguageCode: null,
  sessionDurationMinutes: null,
  profile: null,
  languages: [],
};

const pageMeta = {
  dashboard: ['Focuslyra', 'One place for every language you decide to learn.'],
  study: ["Today's study", 'Speak, listen, read, write and train pronunciation in one workspace.'],
  review: ['Adaptive review', 'Recognition and production are different skills.'],
  memory: ['Memory', 'Reusable meaning and your own worlds/projects, without copying stale files.'],
  progress: ['Progress', 'Measure abilities instead of lesson completion.'],
  settings: ['Settings', 'Profile, languages, voices, AI providers and calendar — set once, mostly forget.'],
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
  const type = response.headers.get('content-type') || '';
  const body = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof body === 'object' && body?.detail ? body.detail : String(body);
    throw new Error(message);
  }
  return body;
}

function setView(viewId) {
  state.currentView = viewId;
  document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === viewId));
  document.querySelectorAll('.nav-button').forEach(button => button.classList.toggle('active', button.dataset.view === viewId));
  const [title, subtitle] = pageMeta[viewId];
  document.getElementById('pageTitle').textContent = title;
  document.getElementById('pageSubtitle').textContent = subtitle;
  if (viewId === 'settings') {
    const activeTab = document.querySelector('.sub-tab[data-settings-tab].active')?.dataset.settingsTab || 'profile';
    setSettingsTab(activeTab);
  }
}

function setMode(mode) {
  state.currentMode = mode;
  document.querySelectorAll('.mode-tab').forEach(button => button.classList.toggle('active', button.dataset.mode === mode));
  document.querySelectorAll('.mode-panel').forEach(panel => panel.classList.toggle('active', panel.id === `mode-${mode}`));
}

function setSettingsTab(tab) {
  document.querySelectorAll('.sub-tab[data-settings-tab]').forEach(button => button.classList.toggle('active', button.dataset.settingsTab === tab));
  document.querySelectorAll('#settings .sub-panel').forEach(panel => panel.classList.toggle('active', panel.id === `settings-${tab}`));
  if (tab === 'calendar') refreshCalendar().catch(console.error);
  if (tab === 'voices' && window.FocuslyraVoice?.reload) window.FocuslyraVoice.reload().catch(console.error);
  if (tab === 'profile') loadProfileSettings().catch(console.error);
  if (tab === 'languages') loadLanguageSettings().catch(console.error);
}

function setMemoryTab(tab) {
  document.querySelectorAll('.sub-tab[data-memory-tab]').forEach(button => button.classList.toggle('active', button.dataset.memoryTab === tab));
  document.querySelectorAll('#memory .sub-panel').forEach(panel => panel.classList.toggle('active', panel.id === `memory-${tab}`));
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

function localDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function setCalendarMessage(message, good = false) {
  const box = document.getElementById('calendarConnectionResult');
  box.hidden = false;
  box.className = good ? 'feedback good' : 'feedback';
  box.textContent = message;
}

function setScheduleMessage(message, good = false) {
  const box = document.getElementById('calendarScheduleResult');
  box.hidden = false;
  box.className = good ? 'feedback good' : 'feedback';
  box.innerHTML = message;
}

function renderCalendarStatus(status) {
  state.calendarStatus = status;
  const badge = document.getElementById('calendarStateBadge');
  const text = document.getElementById('calendarStatusText');
  const connect = document.getElementById('connectCalendar');
  const disconnect = document.getElementById('disconnectCalendar');

  if (status.connected) {
    badge.textContent = 'CONNECTED';
    badge.classList.add('safe');
    const calendarName = status.focuslyra_calendar?.summary || 'Focuslyra';
    text.innerHTML = `Connected. Study sessions will be written to <strong>${escapeHtml(calendarName)}</strong>. Time zone: ${escapeHtml(status.timezone || '')}.`;
    connect.disabled = true;
    connect.textContent = '✓ Google connected';
    disconnect.disabled = false;
  } else if (status.credentials_configured) {
    badge.textContent = 'READY TO CONNECT';
    badge.classList.remove('safe');
    text.textContent = 'OAuth credentials are stored locally. Authorise your Google account next.';
    connect.disabled = false;
    connect.textContent = 'Connect Google Calendar';
    disconnect.disabled = true;
  } else {
    badge.textContent = 'SETUP NEEDED';
    badge.classList.remove('safe');
    text.textContent = 'First upload the Desktop OAuth credentials JSON downloaded from Google Cloud.';
    connect.disabled = true;
    connect.textContent = 'Connect Google Calendar';
    disconnect.disabled = true;
  }
}

function renderCalendarList(calendars) {
  const host = document.getElementById('calendarList');
  if (!calendars.length) {
    host.innerHTML = '<span class="muted small">No calendars were returned by Google.</span>';
    return;
  }
  host.innerHTML = calendars.map(calendar => `
    <label class="calendar-check">
      <input type="checkbox" value="${escapeHtml(calendar.id)}" ${calendar.selected || calendar.primary || calendar.focuslyra ? 'checked' : ''} />
      <span><strong>${escapeHtml(calendar.summary)}</strong><small>${calendar.primary ? 'Primary · ' : ''}${calendar.focuslyra ? 'Focuslyra · ' : ''}${escapeHtml(calendar.timeZone || '')}</small></span>
    </label>`).join('');
  document.getElementById('saveAvailabilityCalendars').disabled = false;
}

function formatGoogleDateTime(eventPart) {
  if (!eventPart) return '';
  const raw = eventPart.dateTime || eventPart.date;
  if (!raw) return '';
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString([], { dateStyle: 'medium', timeStyle: eventPart.dateTime ? 'short' : undefined });
}

function renderUpcoming(events) {
  const host = document.getElementById('upcomingCalendarEvents');
  if (!events.length) {
    host.innerHTML = '<span class="muted small">No upcoming Focuslyra sessions yet.</span>';
    return;
  }
  host.innerHTML = events.map(event => `
    <div class="calendar-event">
      <div><strong>${escapeHtml(event.summary)}</strong><small>${escapeHtml(formatGoogleDateTime(event.start))}</small></div>
      ${event.htmlLink ? `<a href="${escapeHtml(event.htmlLink)}" target="_blank" rel="noreferrer">Open</a>` : ''}
    </div>`).join('');
}

async function refreshCalendar() {
  const status = await api('/api/calendar/status');
  renderCalendarStatus(status);
  if (!status.connected) {
    document.getElementById('calendarList').innerHTML = '<span class="muted small">Connect Google first.</span>';
    document.getElementById('saveAvailabilityCalendars').disabled = true;
    document.getElementById('upcomingCalendarEvents').innerHTML = '<span class="muted small">Connect Google first.</span>';
    return;
  }
  const [calendars, upcoming] = await Promise.all([
    api('/api/calendar/calendars'),
    api('/api/calendar/upcoming'),
  ]);
  renderCalendarList(calendars);
  renderUpcoming(upcoming);
}

async function uploadCalendarCredentials() {
  const input = document.getElementById('calendarCredentials');
  if (!input.files?.length) {
    setCalendarMessage('Choose the credentials.json file first.');
    return;
  }
  const button = document.getElementById('uploadCalendarCredentials');
  button.disabled = true;
  button.textContent = 'Saving…';
  const form = new FormData();
  form.append('file', input.files[0], input.files[0].name);
  try {
    await api('/api/calendar/credentials', { method: 'POST', body: form });
    setCalendarMessage('Google OAuth credentials saved locally. Now click Connect Google Calendar.', true);
    await refreshCalendar();
  } catch (error) {
    setCalendarMessage(error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Upload credentials locally';
  }
}

async function connectCalendar() {
  const button = document.getElementById('connectCalendar');
  button.disabled = true;
  button.textContent = 'Waiting for Google authorisation…';
  setCalendarMessage('A Google authorisation page should open. Choose your account and approve Focuslyra.');
  try {
    await api('/api/calendar/connect', { method: 'POST' });
    setCalendarMessage('Google Calendar connected. Focuslyra created/located its own study calendar.', true);
    await refreshCalendar();
  } catch (error) {
    setCalendarMessage(error.message);
    button.disabled = false;
    button.textContent = 'Connect Google Calendar';
  }
}

async function disconnectCalendar() {
  await api('/api/calendar/disconnect', { method: 'POST' });
  setCalendarMessage('Google Calendar disconnected. The Focuslyra calendar itself was left intact in Google.', true);
  await refreshCalendar();
}

async function saveAvailabilityCalendars() {
  const ids = [...document.querySelectorAll('#calendarList input[type="checkbox"]:checked')].map(input => input.value);
  try {
    await api('/api/calendar/availability-calendars', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ calendar_ids: ids }),
    });
    setCalendarMessage(`Availability will be checked against ${ids.length} calendar${ids.length === 1 ? '' : 's'}.`, true);
  } catch (error) {
    setCalendarMessage(error.message);
  }
}

function scheduleParameters() {
  return {
    target_date: document.getElementById('scheduleDate').value,
    duration_minutes: Number(document.getElementById('scheduleDuration').value || 45),
    window_start: document.getElementById('scheduleStart').value || '08:00',
    window_end: document.getElementById('scheduleEnd').value || '19:00',
  };
}

async function findFreeSlots() {
  const params = scheduleParameters();
  const query = new URLSearchParams({
    target_date: params.target_date,
    duration_minutes: String(params.duration_minutes),
    window_start: params.window_start,
    window_end: params.window_end,
  });
  const host = document.getElementById('freeSlotList');
  host.innerHTML = '<span class="muted small">Checking your calendars…</span>';
  try {
    const result = await api(`/api/calendar/free-slots?${query}`);
    if (!result.slots.length) {
      host.innerHTML = '<span class="muted small">No free study slot was found in this window.</span>';
      return;
    }
    host.innerHTML = result.slots.map(slot => {
      const start = new Date(slot.start);
      const end = new Date(slot.end);
      const label = `${start.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}–${end.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
      return `<button class="slot-button" data-start="${escapeHtml(slot.start)}">${escapeHtml(label)}</button>`;
    }).join('');
    host.querySelectorAll('.slot-button').forEach(button => button.addEventListener('click', () => createEventAt(button.dataset.start)));
  } catch (error) {
    host.innerHTML = `<span class="muted small">${escapeHtml(error.message)}</span>`;
  }
}

async function createEventAt(start) {
  const params = scheduleParameters();
  try {
    const result = await api('/api/calendar/study-events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start, duration_minutes: params.duration_minutes }),
    });
    const link = result.event?.htmlLink ? ` <a href="${escapeHtml(result.event.htmlLink)}" target="_blank" rel="noreferrer">Open in Google Calendar</a>` : '';
    setScheduleMessage(`<strong>Scheduled.</strong> Google Calendar will hold the session and reminders.${link}`, true);
    await refreshCalendar();
  } catch (error) {
    setScheduleMessage(escapeHtml(error.message));
  }
}

async function smartSchedule() {
  const params = scheduleParameters();
  try {
    const result = await api('/api/calendar/study-events/smart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const start = new Date(result.slot.start).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
    const link = result.event?.htmlLink ? ` <a href="${escapeHtml(result.event.htmlLink)}" target="_blank" rel="noreferrer">Open event</a>` : '';
    setScheduleMessage(`<strong>Study scheduled for ${escapeHtml(start)}.</strong>${link}`, true);
    await refreshCalendar();
  } catch (error) {
    setScheduleMessage(escapeHtml(error.message));
  }
}

function fillProfileForm(profile) {
  const form = document.getElementById('profileForm');
  if (!form) return;
  form.learner_name.value = profile.learner_name || '';
  form.native_language.value = profile.native_language || '';
  form.normal_session_minutes.value = profile.normal_session_minutes || 45;
  form.minimum_session_minutes.value = profile.minimum_session_minutes || 12;
  form.accent_importance.value = profile.accent_importance || 'medium';
  form.attention_strategy.value = profile.attention_strategy || '';
  const focus = new Set(profile.learning_focus || []);
  form.querySelectorAll('input[name="learning_focus"]').forEach(checkbox => {
    checkbox.checked = focus.has(checkbox.value);
  });
}

async function loadProfileSettings() {
  try {
    const profile = await api('/api/profile');
    state.profile = profile;
    fillProfileForm(profile);
  } catch (error) {
    const message = document.getElementById('profileSettingsMessage');
    message.hidden = false;
    message.className = 'feedback';
    message.textContent = error.message;
  }
}

async function saveProfileSettings(event) {
  event.preventDefault();
  const form = event.target;
  const message = document.getElementById('profileSettingsMessage');
  const payload = {
    ...(state.profile || {}),
    learner_name: form.learner_name.value.trim(),
    native_language: form.native_language.value.trim(),
    normal_session_minutes: Number(form.normal_session_minutes.value || 45),
    minimum_session_minutes: Number(form.minimum_session_minutes.value || 12),
    accent_importance: form.accent_importance.value,
    attention_strategy: form.attention_strategy.value.trim(),
    learning_focus: [...form.querySelectorAll('input[name="learning_focus"]:checked')].map(checkbox => checkbox.value),
  };
  try {
    state.profile = await api('/api/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    fillProfileForm(state.profile);
    message.hidden = false;
    message.className = 'feedback good';
    message.textContent = 'Profile saved. The local learning engine will use these values on the next analysis.';
  } catch (error) {
    message.hidden = false;
    message.className = 'feedback';
    message.textContent = error.message;
  }
}

function renderLanguageSettings(languages) {
  const host = document.getElementById('languageSettingsGrid');
  if (!host) return;
  host.innerHTML = languages.map(language => `
    <div class="language-setting-row" data-code="${escapeHtml(language.code)}">
      <span class="language-title"><span>${escapeHtml(language.flag)}</span>${escapeHtml(language.name)}</span>
      <label class="inline-field">Priority
        <input type="number" min="1" max="9" value="${escapeHtml(language.priority)}" data-field="priority" />
      </label>
      <label class="inline-field">Status
        <select data-field="status">
          <option value="active" ${language.status === 'active' ? 'selected' : ''}>Active</option>
          <option value="maintenance" ${language.status === 'maintenance' ? 'selected' : ''}>Maintenance</option>
          <option value="parked" ${language.status === 'parked' ? 'selected' : ''}>Parked</option>
        </select>
      </label>
    </div>`).join('');
}

async function loadLanguageSettings() {
  try {
    const languages = await api('/api/languages');
    state.languages = languages;
    renderLanguageSettings(languages);
  } catch (error) {
    const message = document.getElementById('languageSettingsMessage');
    message.hidden = false;
    message.className = 'feedback';
    message.textContent = error.message;
  }
}

async function saveLanguageSettings() {
  const message = document.getElementById('languageSettingsMessage');
  const updates = {};
  document.querySelectorAll('.language-setting-row').forEach(row => {
    updates[row.dataset.code] = {
      priority: Number(row.querySelector('[data-field="priority"]').value || 1),
      status: row.querySelector('[data-field="status"]').value,
    };
  });
  try {
    const languages = await api('/api/languages', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ languages: updates }),
    });
    state.languages = languages;
    renderLanguages(languages);
    renderLanguageSettings(languages);
    message.hidden = false;
    message.className = 'feedback good';
    message.textContent = "Languages updated. \"Start today's session\" will follow the new priorities.";
  } catch (error) {
    message.hidden = false;
    message.className = 'feedback';
    message.textContent = error.message;
  }
}

async function boot() {
  document.getElementById('scheduleDate').value = localDateString();
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
    state.languages = languages;
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
  if (state.recorder?.state === 'recording') state.recorder.stop();
  const button = document.getElementById('recordButton');
  button.classList.remove('recording');
  button.textContent = '🎙';
}

// Note: saving/analysing the writing and recording panels is handled by
// learning.js (focuslyraAnalyseWriting / focuslyraSaveAndAnalyseRecording),
// which also persists AI feedback. There is intentionally no second, simpler
// handler here — an earlier version of this file had one, and the two had
// to fight over the same button via stopImmediatePropagation().

async function applyTodaySession(target) {
  const subtitle = document.getElementById('pageSubtitle');
  try {
    const today = await api('/api/study/today');
    state.currentLanguageCode = today.language.code;
    state.sessionDurationMinutes = target === 'minimum' ? today.minimum_session_minutes : today.normal_session_minutes;
    setView('study');
    if (target === 'minimum') {
      subtitle.textContent = `10-minute mode: one useful ${today.language.name} speaking task + short review. No backlog. (~${state.sessionDurationMinutes} min)`;
    } else {
      subtitle.textContent = `Today: ${today.language.flag} ${today.language.name} · ~${state.sessionDurationMinutes} min suggested · target ${today.language.target_variety}.`;
    }
  } catch (error) {
    setView('study');
    subtitle.textContent = `Could not load today's plan automatically (${error.message}). Add an active language in Settings → Languages.`;
  }
}

document.querySelectorAll('.nav-button').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
document.querySelectorAll('.mode-tab').forEach(button => button.addEventListener('click', () => setMode(button.dataset.mode)));
document.querySelectorAll('.sub-tab[data-settings-tab]').forEach(button => button.addEventListener('click', () => setSettingsTab(button.dataset.settingsTab)));
document.querySelectorAll('.sub-tab[data-memory-tab]').forEach(button => button.addEventListener('click', () => setMemoryTab(button.dataset.memoryTab)));

document.getElementById('startSession').addEventListener('click', () => applyTodaySession('normal'));
document.getElementById('quickTen').addEventListener('click', () => applyTodaySession('minimum'));
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
document.getElementById('reviewReveal').addEventListener('click', () => document.getElementById('reviewAnswer').hidden = false);
document.getElementById('demoListen').addEventListener('click', () => {
  const box = document.getElementById('listenDemoResult');
  box.hidden = false;
  box.innerHTML = '<strong>Flow:</strong> play audio → learner answers → reveal transcript → compare → create evidence event. Generated/cached audio comes in the speech phase.';
});

document.getElementById('profileForm').addEventListener('submit', saveProfileSettings);
document.getElementById('saveLanguageSettings').addEventListener('click', saveLanguageSettings);

document.getElementById('uploadCalendarCredentials').addEventListener('click', uploadCalendarCredentials);
document.getElementById('connectCalendar').addEventListener('click', connectCalendar);
document.getElementById('disconnectCalendar').addEventListener('click', disconnectCalendar);
document.getElementById('saveAvailabilityCalendars').addEventListener('click', saveAvailabilityCalendars);
document.getElementById('findFreeSlots').addEventListener('click', findFreeSlots);
document.getElementById('smartSchedule').addEventListener('click', smartSchedule);

boot();
