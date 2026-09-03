(() => {
  const purposes = [
    ['default_voice', 'Default voice'],
    ['reference_voice', 'Pronunciation / reference'],
    ['conversation_voice', 'Conversation'],
    ['listening_voice', 'Listening'],
  ];

  const voiceState = {
    languages: [],
    catalog: { engines: [], languages: {} },
    preferences: { languages: {} },
  };

  window.FocuslyraVoice = {
    state: voiceState,
    getProfile(languageCode) {
      return voiceState.preferences.languages?.[languageCode] || null;
    },
    getVoice(languageCode, purpose = 'default') {
      const profile = this.getProfile(languageCode) || {};
      const key = {
        reference: 'reference_voice',
        conversation: 'conversation_voice',
        listening: 'listening_voice',
        default: 'default_voice',
      }[purpose] || 'default_voice';
      return profile[key] || profile.default_voice || null;
    },
    browserVoices(languageCode) {
      if (!('speechSynthesis' in window)) return [];
      const voices = window.speechSynthesis.getVoices();
      const code = String(languageCode || '').toLowerCase();
      const base = code.split('-')[0];
      return voices
        .filter(voice => {
          const lang = String(voice.lang || '').toLowerCase();
          return lang === code || lang.startsWith(`${base}-`) || lang === base;
        })
        .sort((a, b) => a.name.localeCompare(b.name));
    },
  };

  function injectShell() {
    if (document.getElementById('voiceSettings')) return;

    if (typeof pageMeta !== 'undefined') {
      pageMeta.voiceSettings = ['Voice settings', 'Choose the voice engine and sound you want for every language.'];
    }

    const providersButton = document.querySelector('.nav-button[data-view="providers"]');
    if (providersButton) {
      const button = document.createElement('button');
      button.className = 'nav-button';
      button.dataset.view = 'voiceSettings';
      button.textContent = '🔊 Voices';
      providersButton.before(button);
      button.addEventListener('click', () => {
        setView('voiceSettings');
        loadVoiceSettings().catch(console.error);
      });
    }

    const providers = document.getElementById('providers');
    if (providers) {
      const section = document.createElement('section');
      section.id = 'voiceSettings';
      section.className = 'view';
      section.innerHTML = `
        <div class="section-heading">
          <div>
            <h2>Voice profiles</h2>
            <p>Each language can use its own engine, reference voice, conversation voice and listening voice.</p>
          </div>
          <button id="saveVoiceProfiles" class="primary">Save voice profiles</button>
        </div>
        <div id="voiceSettingsMessage" class="feedback" hidden></div>
        <div id="voiceProfileGrid" class="voice-profile-grid"><span class="muted">Loading voices…</span></div>`;
      providers.before(section);
      section.querySelector('#saveVoiceProfiles').addEventListener('click', saveVoiceSettings);
    }

    const style = document.createElement('style');
    style.textContent = `
      .voice-profile-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
      .voice-profile-card{background:var(--card,#111a28);border:1px solid var(--border,#26354a);border-radius:18px;padding:18px}
      .voice-profile-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}
      .voice-profile-head h3{margin:0}.voice-profile-head small{display:block;margin-top:4px}
      .voice-control{display:grid;grid-template-columns:1fr;gap:6px;margin:11px 0}
      .voice-control label{font-size:12px;color:var(--muted,#91a1b7)}
      .voice-control select,.voice-control input{width:100%;border:1px solid var(--border,#26354a);background:#0b121d;color:inherit;border-radius:10px;padding:9px 10px}
      .voice-inline{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end}
      .voice-preview{white-space:nowrap}.voice-note{font-size:11px;color:var(--muted,#91a1b7);line-height:1.45;margin-top:10px}
    `;
    document.head.appendChild(style);
  }

  function browserOptions(languageCode) {
    return window.FocuslyraVoice.browserVoices(languageCode).map(voice => ({
      id: voice.name,
      label: `${voice.name} · ${voice.lang}`,
      engine: 'browser',
    }));
  }

  function kokoroOptions(languageCode) {
    const entry = voiceState.catalog.languages?.[languageCode] || {};
    return (entry.kokoro_voices || []).map(id => ({ id, label: id, engine: 'kokoro' }));
  }

  function optionsFor(languageCode, engine) {
    const kokoro = kokoroOptions(languageCode);
    const browser = browserOptions(languageCode);
    if (engine === 'kokoro') return kokoro;
    if (engine === 'browser') return browser;
    return kokoro.length ? kokoro : browser;
  }

  function voiceSelectHtml(languageCode, engine, value, field) {
    const options = optionsFor(languageCode, engine);
    const current = value || '';
    const known = options.some(option => option.id === current);
    return `<select data-voice-field="${field}">
      <option value="">${field === 'default_voice' ? 'Automatic' : 'Inherit default voice'}</option>
      ${!known && current ? `<option value="${escapeHtml(current)}" selected>${escapeHtml(current)} · currently saved</option>` : ''}
      ${options.map(option => `<option value="${escapeHtml(option.id)}" ${option.id === current ? 'selected' : ''}>${escapeHtml(option.label)}</option>`).join('')}
    </select>`;
  }

  function renderVoiceProfiles() {
    const grid = document.getElementById('voiceProfileGrid');
    if (!grid) return;
    grid.innerHTML = voiceState.languages.map(language => {
      const profile = voiceState.preferences.languages?.[language.code] || { engine: 'auto', speed: 1 };
      const catalog = voiceState.catalog.languages?.[language.code] || {};
      return `
        <article class="voice-profile-card" data-language-code="${escapeHtml(language.code)}">
          <div class="voice-profile-head">
            <div><h3>${escapeHtml(language.flag)} ${escapeHtml(language.name)}</h3><small class="muted">${escapeHtml(language.target_variety || '')}</small></div>
            <span class="badge">${catalog.kokoro_supported ? 'LOCAL + SYSTEM' : 'SYSTEM'}</span>
          </div>
          <div class="voice-control">
            <label>Voice engine</label>
            <select data-voice-field="engine">
              ${(voiceState.catalog.engines || []).map(engine => `<option value="${escapeHtml(engine.id)}" ${engine.id === profile.engine ? 'selected' : ''}>${escapeHtml(engine.label)}</option>`).join('')}
            </select>
          </div>
          ${purposes.map(([field, label]) => `
            <div class="voice-control">
              <label>${escapeHtml(label)}</label>
              <div class="voice-inline">
                <div class="voice-select-host" data-field-host="${field}">${voiceSelectHtml(language.code, profile.engine || 'auto', profile[field], field)}</div>
                <button type="button" class="ghost voice-preview" data-preview-field="${field}">▶ Preview</button>
              </div>
            </div>`).join('')}
          <div class="voice-control">
            <label>Speed · <span data-speed-label>${Number(profile.speed || 1).toFixed(2)}×</span></label>
            <input type="range" min="0.65" max="1.35" step="0.05" value="${Number(profile.speed || 1)}" data-voice-field="speed" />
          </div>
          <div class="voice-note">Auto prefers persistent local audio when the selected local engine supports this language, then falls back to the device's system voices.</div>
        </article>`;
    }).join('');

    grid.querySelectorAll('.voice-profile-card').forEach(card => wireCard(card));
  }

  function wireCard(card) {
    const languageCode = card.dataset.languageCode;
    const engineSelect = card.querySelector('[data-voice-field="engine"]');
    engineSelect.addEventListener('change', () => {
      const oldValues = {};
      card.querySelectorAll('[data-voice-field]').forEach(el => oldValues[el.dataset.voiceField] = el.value);
      purposes.forEach(([field]) => {
        const host = card.querySelector(`[data-field-host="${field}"]`);
        host.innerHTML = voiceSelectHtml(languageCode, engineSelect.value, oldValues[field], field);
      });
    });

    const range = card.querySelector('[data-voice-field="speed"]');
    range.addEventListener('input', () => card.querySelector('[data-speed-label]').textContent = `${Number(range.value).toFixed(2)}×`);

    card.querySelectorAll('[data-preview-field]').forEach(button => button.addEventListener('click', async () => {
      const field = button.dataset.previewField;
      const select = card.querySelector(`[data-voice-field="${field}"]`);
      const defaultSelect = card.querySelector('[data-voice-field="default_voice"]');
      const voice = select?.value || defaultSelect?.value || null;
      const engine = engineSelect.value;
      const speed = Number(range.value || 1);
      const language = voiceState.languages.find(item => item.code === languageCode);
      const sample = previewText(languageCode);
      const old = button.textContent;
      button.disabled = true;
      button.textContent = 'Playing…';
      try {
        const kokoroVoices = kokoroOptions(languageCode).map(item => item.id);
        const useKokoro = engine === 'kokoro' || (engine === 'auto' && voice && kokoroVoices.includes(voice));
        if (useKokoro) {
          const result = await api('/api/tts/generate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: sample, language_code: languageCode, voice, speed }),
          });
          await new Audio(result.url).play();
        } else {
          previewBrowser(sample, languageCode, voice, speed);
        }
      } catch (error) {
        previewBrowser(sample, languageCode, voice, speed);
      } finally {
        setTimeout(() => { button.disabled = false; button.textContent = old; }, 500);
      }
    }));
  }

  function previewText(languageCode) {
    return {
      'en-GB': 'I thought the weather would be better, but I could have stayed a little longer.',
      'es-ES': 'Me gustaría hablar contigo un poco más para practicar mi español.',
      'fr-FR': 'Je voudrais parler un peu plus pour améliorer mon français.',
      'it-IT': 'Vorrei parlare un po’ di più per migliorare il mio italiano.',
      'ja-JP': 'こんにちは。もう少し日本語を話したいです。',
      'de-DE': 'Ich möchte ein bisschen mehr Deutsch sprechen und üben.',
      'ar': 'أريد أن أتحدث أكثر لأتدرب على اللغة العربية.',
    }[languageCode] || 'This is a Focuslyra voice preview.';
  }

  function previewBrowser(text, languageCode, voiceName, speed) {
    if (!('speechSynthesis' in window)) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = languageCode;
    utterance.rate = speed;
    const voices = window.FocuslyraVoice.browserVoices(languageCode);
    utterance.voice = voices.find(voice => voice.name === voiceName) || voices[0] || null;
    speechSynthesis.speak(utterance);
  }

  async function loadVoiceSettings() {
    const [languages, catalog, preferences] = await Promise.all([
      api('/api/languages'), api('/api/voice/catalog'), api('/api/voice/preferences'),
    ]);
    voiceState.languages = languages;
    voiceState.catalog = catalog;
    voiceState.preferences = preferences;
    renderVoiceProfiles();
  }

  async function saveVoiceSettings() {
    const message = document.getElementById('voiceSettingsMessage');
    const payload = { languages: {} };
    document.querySelectorAll('.voice-profile-card').forEach(card => {
      const code = card.dataset.languageCode;
      const values = {};
      card.querySelectorAll('[data-voice-field]').forEach(field => {
        values[field.dataset.voiceField] = field.dataset.voiceField === 'speed' ? Number(field.value) : (field.value || null);
      });
      payload.languages[code] = values;
    });
    try {
      voiceState.preferences = await api('/api/voice/preferences', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      message.hidden = false;
      message.className = 'feedback good';
      message.textContent = 'Voice profiles saved locally. New generated audio will follow these preferences.';
    } catch (error) {
      message.hidden = false;
      message.className = 'feedback';
      message.textContent = error.message;
    }
  }

  injectShell();
  loadVoiceSettings().catch(error => {
    const grid = document.getElementById('voiceProfileGrid');
    if (grid) grid.innerHTML = `<span class="muted">${escapeHtml(error.message)}</span>`;
  });

  if ('speechSynthesis' in window) {
    speechSynthesis.addEventListener?.('voiceschanged', () => {
      if (document.getElementById('voiceSettings')?.classList.contains('active')) renderVoiceProfiles();
    });
  }
})();
