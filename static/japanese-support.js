(() => {
  'use strict';

  const JAPANESE_RE = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;
  const SELECTORS = [
    '#study h2',
    '#study .prompt',
    '#study .reading-passage',
    '#study .pronunciation-reference',
    '#study .dynamic-transcript p',
    '#study .learning-correction strong',
    '#study .learning-block li',
    '#study .learning-transcript p',
  ].join(',');

  function installStyles() {
    if (document.getElementById('focuslyraJapaneseStyles')) return;
    const style = document.createElement('style');
    style.id = 'focuslyraJapaneseStyles';
    style.textContent = `
      .romaji-helper { display:flex; align-items:center; gap:.65rem; margin:.45rem 0 1rem; flex-wrap:wrap; }
      .romaji-toggle { padding:.4rem .75rem; font-size:.85rem; }
      .romaji-output { width:100%; padding:.7rem .85rem; border:1px solid #2a4059; border-radius:12px; background:#0c1622; color:#b9cee8; line-height:1.55; }
      .romaji-output[hidden] { display:none; }
    `;
    document.head.appendChild(style);
  }

  async function fetchRomaji(text) {
    const result = await api('/api/japanese/romaji', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texts: [text] }),
    });
    return String(result?.romaji?.[0] || '');
  }

  function enhanceElement(source) {
    if (!source || source.dataset.romajiEnhanced === '1') return;
    const text = (source.textContent || '').trim();
    if (!text || !JAPANESE_RE.test(text)) return;

    source.dataset.romajiEnhanced = '1';
    const helper = document.createElement('div');
    helper.className = 'romaji-helper';
    helper.innerHTML = `
      <button type="button" class="ghost romaji-toggle">あ Show romaji</button>
      <div class="romaji-output" hidden></div>`;
    source.insertAdjacentElement('afterend', helper);

    const button = helper.querySelector('.romaji-toggle');
    const output = helper.querySelector('.romaji-output');
    let loaded = false;

    button.addEventListener('click', async () => {
      if (!output.hidden) {
        output.hidden = true;
        button.textContent = 'あ Show romaji';
        return;
      }

      output.hidden = false;
      button.textContent = 'あ Hide romaji';
      if (loaded) return;

      button.disabled = true;
      output.textContent = 'Converting to Hepburn romaji…';
      try {
        const romaji = await fetchRomaji(text);
        output.textContent = romaji || 'Romaji could not be generated for this text.';
        loaded = true;
      } catch (error) {
        output.textContent = `Romaji unavailable: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
  }

  function scan(root = document) {
    installStyles();
    root.querySelectorAll?.(SELECTORS).forEach(enhanceElement);
    if (root.matches?.(SELECTORS)) enhanceElement(root);
  }

  const study = document.getElementById('study');
  if (study) {
    const observer = new MutationObserver(mutations => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) scan(node);
        }
      }
      scan(study);
    });
    observer.observe(study, { childList: true, subtree: true });
    scan(study);
  }

  window.FocuslyraJapanese = { scan };
})();
