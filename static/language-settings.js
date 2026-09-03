(() => {
  function installLanguageSettingsStyles() {
    if (document.getElementById('focuslyraLanguageSettingsStyles')) return;
    const style = document.createElement('style');
    style.id = 'focuslyraLanguageSettingsStyles';
    style.textContent = `
      .language-settings-intro { margin:0 0 16px; padding:14px 16px; border:1px solid #263a52; border-radius:16px; background:#0c1622; }
      .language-settings-intro strong { display:block; margin-bottom:4px; }
      .language-setting-card { display:grid; gap:12px; padding:16px; border:1px solid #26384e; border-radius:16px; background:#0d1723; margin-bottom:12px; }
      .language-setting-card.not-selected { opacity:.64; }
      .language-setting-main { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
      .language-select-toggle { display:flex; align-items:center; gap:8px; font-weight:700; cursor:pointer; }
      .language-select-toggle input { width:18px; height:18px; }
      .language-setting-controls { display:flex; gap:10px; flex-wrap:wrap; margin-left:auto; }
      .language-setting-controls label { display:grid; gap:5px; color:#8fa6c4; font-size:.78rem; }
      .language-setting-controls select { min-width:135px; }
      .language-ai-context { display:grid; gap:6px; }
      .language-ai-context span { color:#8fa6c4; font-size:.8rem; }
      .language-ai-context input { width:100%; }
      .language-level-line { color:#8fa6c4; font-size:.82rem; }
      .language-setting-card.not-selected .language-study-field { pointer-events:none; }
      .language-setting-card.not-selected .language-study-field select,
      .language-setting-card.not-selected .language-study-field input { opacity:.55; }
      @media (max-width:760px) {
        .language-setting-controls { width:100%; margin-left:0; }
        .language-setting-controls label { flex:1; }
        .language-setting-controls select { width:100%; min-width:0; }
      }
    `;
    document.head.appendChild(style);
  }

  function escapeValue(value) {
    return typeof escapeHtml === 'function' ? escapeHtml(value) : String(value ?? '');
  }

  function goalContext(language) {
    return Array.isArray(language.goals) ? language.goals.join('; ') : '';
  }

  function splitGoals(value) {
    return String(value || '')
      .split(/[;\n]+/)
      .map(item => item.trim())
      .filter(Boolean)
      .slice(0, 8);
  }

  function updateSelectedVisual(row) {
    const selected = row.querySelector('[data-field="selected"]')?.checked ?? false;
    row.classList.toggle('not-selected', !selected);
    row.querySelectorAll('.language-study-field select, .language-study-field input').forEach(control => {
      control.disabled = !selected;
    });
  }

  function renderLanguageSettingsV2(languages) {
    installLanguageSettingsStyles();
    const host = document.getElementById('languageSettingsGrid');
    if (!host) return;
    host.innerHTML = `
      <div class="language-settings-intro">
        <strong>Escolha o que faz parte do seu perfil de estudo.</strong>
        <span class="muted small">Todos os idiomas suportados aparecem aqui. Marque os que quer estudar, defina a prioridade e diga em uma frase o que quer conseguir. Isso já dá à IA o contexto essencial sem transformar o cadastro num interrogatório.</span>
      </div>
      ${languages.map(language => `
        <div class="language-setting-row language-setting-card ${language.selected ? '' : 'not-selected'}" data-code="${escapeValue(language.code)}">
          <div class="language-setting-main">
            <label class="language-select-toggle">
              <input type="checkbox" data-field="selected" ${language.selected ? 'checked' : ''} />
              <span class="language-title"><span>${escapeValue(language.flag)}</span>${escapeValue(language.name)}</span>
            </label>
            <div class="language-setting-controls language-study-field">
              <label>Prioridade
                <select data-field="priority">
                  <option value="1" ${Number(language.priority) === 1 ? 'selected' : ''}>1 · Principal</option>
                  <option value="2" ${Number(language.priority) === 2 ? 'selected' : ''}>2 · Alta</option>
                  <option value="3" ${Number(language.priority) === 3 ? 'selected' : ''}>3 · Normal</option>
                  <option value="4" ${Number(language.priority) === 4 ? 'selected' : ''}>4 · Baixa</option>
                </select>
              </label>
              <label>Ritmo
                <select data-field="status">
                  <option value="active" ${language.status === 'active' ? 'selected' : ''}>Ativo</option>
                  <option value="maintenance" ${language.status === 'maintenance' ? 'selected' : ''}>Manutenção</option>
                  <option value="parked" ${language.status === 'parked' ? 'selected' : ''}>Pausado</option>
                </select>
              </label>
            </div>
          </div>
          <label class="language-ai-context language-study-field">
            <span>Objetivo / contexto para a IA · uma frase basta</span>
            <input type="text" data-field="goals" maxlength="700" value="${escapeValue(goalContext(language))}" placeholder="Ex.: quero morar na Espanha e conversar com naturalidade no dia a dia" />
          </label>
          <div class="language-level-line"><strong>Nível atual:</strong> ${escapeValue(language.current_state || 'Ainda não avaliado.')}</div>
        </div>`).join('')}`;

    host.querySelectorAll('.language-setting-row').forEach(row => {
      const toggle = row.querySelector('[data-field="selected"]');
      toggle?.addEventListener('change', () => updateSelectedVisual(row));
      updateSelectedVisual(row);
    });

    // users.js watches these rows and adds the per-language placement button.
    if (typeof enhancePlacementButtons === 'function') enhancePlacementButtons();
  }

  async function loadLanguageSettingsV2() {
    try {
      const languages = await api('/api/languages/catalogue');
      state.languageCatalogue = languages;
      renderLanguageSettingsV2(languages);
    } catch (error) {
      const message = document.getElementById('languageSettingsMessage');
      if (message) {
        message.hidden = false;
        message.className = 'feedback';
        message.textContent = error.message;
      }
    }
  }

  async function saveLanguageSettingsV2() {
    const message = document.getElementById('languageSettingsMessage');
    const updates = {};
    document.querySelectorAll('.language-setting-row').forEach(row => {
      updates[row.dataset.code] = {
        selected: Boolean(row.querySelector('[data-field="selected"]')?.checked),
        priority: Number(row.querySelector('[data-field="priority"]')?.value || 3),
        status: row.querySelector('[data-field="status"]')?.value || 'active',
        goals: splitGoals(row.querySelector('[data-field="goals"]')?.value),
      };
    });

    try {
      await api('/api/languages', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ languages: updates }),
      });
      const [selectedLanguages, catalogue] = await Promise.all([
        api('/api/languages'),
        api('/api/languages/catalogue'),
      ]);
      state.languages = selectedLanguages;
      state.languageCatalogue = catalogue;
      if (typeof renderLanguages === 'function') renderLanguages(selectedLanguages);
      renderLanguageSettingsV2(catalogue);
      if (message) {
        message.hidden = false;
        message.className = 'feedback good';
        message.textContent = 'Idiomas salvos. O planejador só usa os idiomas marcados e a IA recebe os objetivos/contexto de cada um.';
      }
      if (typeof loadPlanPreview === 'function') loadPlanPreview().catch(console.error);
    } catch (error) {
      if (message) {
        message.hidden = false;
        message.className = 'feedback';
        message.textContent = error.message;
      }
    }
  }

  window.renderLanguageSettings = renderLanguageSettingsV2;
  window.loadLanguageSettings = loadLanguageSettingsV2;
  window.saveLanguageSettings = saveLanguageSettingsV2;

  // app.js attached its original save handler before this enhancement loaded.
  // Capture the click first so only the catalogue-aware save path runs.
  document.addEventListener('click', event => {
    const save = event.target.closest?.('#saveLanguageSettings');
    if (save) {
      event.preventDefault();
      event.stopImmediatePropagation();
      saveLanguageSettingsV2();
      return;
    }
    const languagesTab = event.target.closest?.('[data-settings-tab="languages"]');
    if (languagesTab) setTimeout(() => loadLanguageSettingsV2(), 0);
  }, true);
})();
