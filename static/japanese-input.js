(() => {
  const HIRA_MAP = {
    a:'あ',i:'い',u:'う',e:'え',o:'お',
    ka:'か',ki:'き',ku:'く',ke:'け',ko:'こ',
    ga:'が',gi:'ぎ',gu:'ぐ',ge:'げ',go:'ご',
    sa:'さ',shi:'し',si:'し',su:'す',se:'せ',so:'そ',
    za:'ざ',ji:'じ',zi:'じ',zu:'ず',ze:'ぜ',zo:'ぞ',
    ta:'た',chi:'ち',ti:'ち',tsu:'つ',tu:'つ',te:'て',to:'と',
    da:'だ',di:'ぢ',du:'づ',de:'で',do:'ど',
    na:'な',ni:'に',nu:'ぬ',ne:'ね',no:'の',
    ha:'は',hi:'ひ',fu:'ふ',hu:'ふ',he:'へ',ho:'ほ',
    ba:'ば',bi:'び',bu:'ぶ',be:'べ',bo:'ぼ',
    pa:'ぱ',pi:'ぴ',pu:'ぷ',pe:'ぺ',po:'ぽ',
    ma:'ま',mi:'み',mu:'む',me:'め',mo:'も',
    ya:'や',yu:'ゆ',yo:'よ',
    ra:'ら',ri:'り',ru:'る',re:'れ',ro:'ろ',
    wa:'わ',wo:'を',
    kya:'きゃ',kyu:'きゅ',kyo:'きょ',gya:'ぎゃ',gyu:'ぎゅ',gyo:'ぎょ',
    sha:'しゃ',shu:'しゅ',sho:'しょ',sya:'しゃ',syu:'しゅ',syo:'しょ',
    ja:'じゃ',ju:'じゅ',jo:'じょ',jya:'じゃ',jyu:'じゅ',jyo:'じょ',
    cha:'ちゃ',chu:'ちゅ',cho:'ちょ',cya:'ちゃ',cyu:'ちゅ',cyo:'ちょ',
    nya:'にゃ',nyu:'にゅ',nyo:'にょ',hya:'ひゃ',hyu:'ひゅ',hyo:'ひょ',
    bya:'びゃ',byu:'びゅ',byo:'びょ',pya:'ぴゃ',pyu:'ぴゅ',pyo:'ぴょ',
    mya:'みゃ',myu:'みゅ',myo:'みょ',rya:'りゃ',ryu:'りゅ',ryo:'りょ',
    fa:'ふぁ',fi:'ふぃ',fe:'ふぇ',fo:'ふぉ',fya:'ふゃ',fyu:'ふゅ',fyo:'ふょ',
    she:'しぇ',je:'じぇ',che:'ちぇ',
    tsa:'つぁ',tsi:'つぃ',tse:'つぇ',tso:'つぉ',
    wi:'うぃ',we:'うぇ',va:'ゔぁ',vi:'ゔぃ',vu:'ゔ',ve:'ゔぇ',vo:'ゔぉ',
    xya:'ゃ',xyu:'ゅ',xyo:'ょ',lya:'ゃ',lyu:'ゅ',lyo:'ょ',
    xa:'ぁ',xi:'ぃ',xu:'ぅ',xe:'ぇ',xo:'ぉ',
    la:'ぁ',li:'ぃ',lu:'ぅ',le:'ぇ',lo:'ぉ',
    xtsu:'っ',ltsu:'っ'
  };

  const MAX_KEY = Math.max(...Object.keys(HIRA_MAP).map(key => key.length));
  const STORAGE_KEY = 'focuslyra.japaneseInput.v1';
  const state = loadState();
  let assistTimer = null;

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {
        autoKana: saved.autoKana !== false,
        script: saved.script === 'katakana' ? 'katakana' : 'hiragana',
        kanjiAssist: Boolean(saved.kanjiAssist),
      };
    } catch (_) {
      return { autoKana: true, script: 'hiragana', kanjiAssist: false };
    }
  }

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
  }

  function isConsonant(ch) {
    return /^[bcdfghjklmnpqrstvwxyz]$/i.test(ch || '');
  }

  function hiraToKata(text) {
    return String(text || '').replace(/[ぁ-ゖ]/g, ch => String.fromCharCode(ch.charCodeAt(0) + 0x60));
  }

  function tokenToHiragana(raw, finaliseEndN = false) {
    const token = String(raw || '').toLowerCase();
    let out = '';
    let i = 0;
    while (i < token.length) {
      const current = token[i];
      const next = token[i + 1] || '';

      if (current === '-' ) {
        out += 'ー';
        i += 1;
        continue;
      }

      if (isConsonant(current) && current !== 'n' && current === next) {
        out += 'っ';
        i += 1;
        continue;
      }

      if (current === 'n') {
        if (next === "'") {
          out += 'ん';
          i += 2;
          continue;
        }
        if (!next) {
          out += finaliseEndN ? 'ん' : 'n';
          i += 1;
          continue;
        }
        if (next === 'n') {
          out += 'ん';
          i += 1;
          continue;
        }
        if (isConsonant(next) && next !== 'y') {
          out += 'ん';
          i += 1;
          continue;
        }
      }

      let matched = false;
      for (let len = Math.min(MAX_KEY, token.length - i); len >= 1; len -= 1) {
        const key = token.slice(i, i + len);
        if (HIRA_MAP[key]) {
          out += HIRA_MAP[key];
          i += len;
          matched = true;
          break;
        }
      }
      if (matched) continue;

      out += raw[i] || token[i];
      i += 1;
    }
    return out;
  }

  function romajiToKana(text, script = 'hiragana', finalise = false) {
    const source = String(text || '');
    const converted = source.replace(/[A-Za-z]+(?:'[A-Za-z]+)?-*/g, (token, offset) => {
      const endsAtBoundary = offset + token.length < source.length;
      return tokenToHiragana(token, finalise || endsAtBoundary);
    });
    return script === 'katakana' ? hiraToKata(converted) : converted;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
    return payload;
  }

  function japanesePanelFor(textarea) {
    const panel = textarea.closest('.mode-panel, .card, article, section') || textarea.parentElement;
    const nearby = [
      panel?.querySelector?.('.badge')?.textContent || '',
      document.getElementById('pageSubtitle')?.textContent || '',
      textarea.getAttribute('lang') || '',
    ].join(' ');
    return /JAPANESE|JA-JP|🇯🇵/i.test(nearby) ? panel : null;
  }

  function convertTextarea(textarea, finalise = false) {
    if (!state.autoKana || !textarea) return;
    const start = textarea.selectionStart ?? textarea.value.length;
    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(start);
    const convertedBefore = romajiToKana(before, state.script, finalise);
    const convertedAfter = romajiToKana(after, state.script, finalise);
    if (convertedBefore + convertedAfter === textarea.value) return;
    textarea.value = convertedBefore + convertedAfter;
    const cursor = convertedBefore.length;
    textarea.setSelectionRange?.(cursor, cursor);
    textarea.dispatchEvent(new Event('focuslyra:japanese-converted', { bubbles: true }));
  }

  function toolbarHtml() {
    return `
      <div class="jp-input-toolbar">
        <div class="jp-input-row">
          <label class="jp-check"><input type="checkbox" data-jp-auto-kana ${state.autoKana ? 'checked' : ''}> Romaji → kana</label>
          <div class="jp-script-switch" role="group" aria-label="Japanese script">
            <button type="button" data-jp-script="hiragana" class="${state.script === 'hiragana' ? 'active' : ''}">ひらがな</button>
            <button type="button" data-jp-script="katakana" class="${state.script === 'katakana' ? 'active' : ''}">カタカナ</button>
          </div>
          <label class="jp-check"><input type="checkbox" data-jp-kanji-assist ${state.kanjiAssist ? 'checked' : ''}> Kanji Assist</label>
        </div>
        <div class="jp-input-hint">Type romaji normally. Kanji Assist suggests kanji but never replaces them without your choice.</div>
        <div class="jp-kanji-box" data-jp-kanji-box hidden></div>
      </div>`;
  }

  function installStyles() {
    if (document.getElementById('focuslyraJapaneseInputStyles')) return;
    const style = document.createElement('style');
    style.id = 'focuslyraJapaneseInputStyles';
    style.textContent = `
      .jp-input-toolbar{margin:10px 0 8px;padding:10px 12px;border:1px solid var(--border,#26354a);border-radius:12px;background:rgba(9,15,24,.55)}
      .jp-input-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .jp-check{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted,#91a1b7)}
      .jp-script-switch{display:inline-flex;border:1px solid var(--border,#26354a);border-radius:9px;overflow:hidden}
      .jp-script-switch button{border:0;border-right:1px solid var(--border,#26354a);background:transparent;color:inherit;padding:5px 9px;cursor:pointer}
      .jp-script-switch button:last-child{border-right:0}.jp-script-switch button.active{background:rgba(116,152,255,.18);font-weight:700}
      .jp-input-hint{font-size:11px;color:var(--muted,#91a1b7);margin-top:7px}
      .jp-kanji-box{margin-top:9px;padding-top:9px;border-top:1px solid var(--border,#26354a)}
      .jp-kanji-suggestion{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:8px}.jp-kanji-suggestion strong{font-size:18px}
      .jp-kanji-list{display:flex;gap:7px;flex-wrap:wrap}.jp-kanji-item{border:1px solid var(--border,#26354a);border-radius:10px;padding:7px 9px;background:rgba(255,255,255,.025)}
      .jp-kanji-item strong{font-size:17px}.jp-kanji-meta{font-size:11px;color:var(--muted,#91a1b7);display:block;margin:2px 0 5px}.jp-kanji-item button,.jp-kanji-suggestion button{font-size:11px;padding:5px 8px}
      .jp-kanji-status{font-size:11px;margin-top:7px;color:var(--muted,#91a1b7)}
    `;
    document.head.appendChild(style);
  }

  async function requestKanjiAssist(textarea, box) {
    const text = textarea.value.trim();
    if (!state.kanjiAssist || !text || !/[ぁ-ヿ]/.test(text)) {
      box.hidden = true;
      box.innerHTML = '';
      return;
    }
    box.hidden = false;
    box.innerHTML = '<span class="muted small">Looking for natural kanji locally…</span>';
    try {
      const result = await fetchJson('/api/japanese/kanji-suggest', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text })
      });
      renderKanjiSuggestion(textarea, box, result);
    } catch (error) {
      box.innerHTML = `<span class="muted small">Kanji Assist: ${escapeHtml(error.message)}</span>`;
    }
  }

  function scheduleKanjiAssist(textarea, box) {
    clearTimeout(assistTimer);
    if (!state.kanjiAssist) return;
    assistTimer = setTimeout(() => requestKanjiAssist(textarea, box), 850);
  }

  function renderKanjiSuggestion(textarea, box, result) {
    const converted = String(result.converted_text || '').trim();
    const items = Array.isArray(result.kanji) ? result.kanji : [];
    const changed = converted && converted !== textarea.value.trim();
    box.hidden = false;
    box.innerHTML = `
      ${changed ? `<div class="jp-kanji-suggestion"><span class="muted small">Suggestion</span><strong>${escapeHtml(converted)}</strong><button type="button" class="ghost" data-jp-use-suggestion>Use suggestion</button></div>` : '<div class="muted small">No kanji change suggested for this text.</div>'}
      ${items.length ? `<div class="jp-kanji-list">${items.map((item, index) => `
        <div class="jp-kanji-item">
          <strong>${escapeHtml(item.surface || '')}</strong>
          <span class="jp-kanji-meta">${escapeHtml(item.reading || '')}${item.meaning ? ` · ${escapeHtml(item.meaning)}` : ''}</span>
          <button type="button" class="ghost" data-jp-learn="${index}">＋ Learn this</button>
        </div>`).join('')}</div>` : ''}
      ${result.note ? `<div class="jp-kanji-status">${escapeHtml(result.note)}</div>` : ''}
      <div class="jp-kanji-status" data-jp-status></div>`;

    box.querySelector('[data-jp-use-suggestion]')?.addEventListener('click', () => {
      textarea.value = converted;
      textarea.focus();
      textarea.setSelectionRange?.(textarea.value.length, textarea.value.length);
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });

    box.querySelectorAll('[data-jp-learn]').forEach(button => button.addEventListener('click', async () => {
      const item = items[Number(button.dataset.jpLearn)];
      if (!item) return;
      const status = box.querySelector('[data-jp-status]');
      button.disabled = true;
      button.textContent = 'Adding…';
      try {
        await fetchJson('/api/japanese/kanji-learn', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            surface: item.surface || '', reading: item.reading || '', meaning: item.meaning || '', source_text: textarea.value
          })
        });
        button.textContent = '✓ In Concepts + Review';
        if (status) status.textContent = `${item.surface} will return later without romaji.`;
      } catch (error) {
        button.disabled = false;
        button.textContent = '＋ Learn this';
        if (status) status.textContent = error.message;
      }
    }));
  }

  function wireTextarea(textarea) {
    if (!textarea || textarea.dataset.jpInputWired === '1') return;
    const panel = japanesePanelFor(textarea);
    if (!panel) return;
    textarea.dataset.jpInputWired = '1';
    textarea.setAttribute('lang', 'ja');
    textarea.setAttribute('spellcheck', 'false');

    const host = document.createElement('div');
    host.innerHTML = toolbarHtml();
    const toolbar = host.firstElementChild;
    textarea.parentNode.insertBefore(toolbar, textarea);
    const box = toolbar.querySelector('[data-jp-kanji-box]');

    toolbar.querySelector('[data-jp-auto-kana]').addEventListener('change', event => {
      state.autoKana = event.target.checked;
      saveState();
      if (state.autoKana) convertTextarea(textarea, false);
    });
    toolbar.querySelectorAll('[data-jp-script]').forEach(button => button.addEventListener('click', () => {
      state.script = button.dataset.jpScript;
      saveState();
      toolbar.querySelectorAll('[data-jp-script]').forEach(item => item.classList.toggle('active', item === button));
      textarea.focus();
    }));
    toolbar.querySelector('[data-jp-kanji-assist]').addEventListener('change', event => {
      state.kanjiAssist = event.target.checked;
      saveState();
      if (state.kanjiAssist) requestKanjiAssist(textarea, box);
      else { box.hidden = true; box.innerHTML = ''; }
    });

    textarea.addEventListener('input', () => {
      if (!textarea.dataset.jpConverting) {
        textarea.dataset.jpConverting = '1';
        try { convertTextarea(textarea, false); } finally { delete textarea.dataset.jpConverting; }
      }
      scheduleKanjiAssist(textarea, box);
    });
    textarea.addEventListener('blur', () => convertTextarea(textarea, true));
    if (state.kanjiAssist && textarea.value.trim()) scheduleKanjiAssist(textarea, box);
  }

  function scan() {
    document.querySelectorAll('textarea.dynamic-text-response, textarea[data-language-code="ja-JP"], #writingInput').forEach(textarea => wireTextarea(textarea));
  }

  function finalise(textarea) {
    convertTextarea(textarea, true);
  }

  function boot() {
    installStyles();
    scan();
    const observer = new MutationObserver(() => scan());
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener('click', event => {
      const button = event.target.closest?.('.dynamic-submit-text, #saveWriting');
      if (!button) return;
      const panel = button.closest('.mode-panel, article, section');
      const textarea = panel?.querySelector('textarea[data-jp-input-wired="1"]');
      if (textarea) finalise(textarea);
    }, true);
  }

  const apiObject = { romajiToKana, tokenToHiragana, hiraToKata, wireTextarea, scan, finalise, state };
  if (typeof window !== 'undefined') window.FocuslyraJapaneseInput = apiObject;
  if (typeof module !== 'undefined' && module.exports) module.exports = apiObject;

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})();
