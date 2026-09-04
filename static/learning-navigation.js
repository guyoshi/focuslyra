(() => {
  'use strict';

  // The local model may need several seconds to generate an activity. Keep the
  // learner informed immediately, split fast planning from slower generation,
  // and prefetch only one upcoming slot once the current activity is visible.
  const prefetched = new Map();
  let planRef = null;
  let transitioning = false;
  let startingSession = false;

  function activities() {
    if (typeof studyRuntime === 'undefined') return [];
    return Array.isArray(studyRuntime.plan?.activities) ? studyRuntime.plan.activities : [];
  }

  function syncPlan() {
    if (typeof studyRuntime === 'undefined') return;
    if (studyRuntime.plan !== planRef) {
      planRef = studyRuntime.plan;
      prefetched.clear();
    }
  }

  function slotKey(index, slot) {
    return [
      index,
      slot?.id || '',
      slot?.language_code || '',
      slot?.modality || '',
      slot?.minutes || '',
    ].join('|');
  }

  async function requestActivity(slot) {
    const result = await api('/api/study/activity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(slot),
    });
    if (!result?.activity) throw new Error('The local engine did not return an activity.');
    return result.activity;
  }

  function prepare(index, slot) {
    const key = slotKey(index, slot);
    if (prefetched.has(key)) return prefetched.get(key);

    const promise = requestActivity(slot)
      .then(activity => ({ activity, error: null }))
      .catch(error => ({ activity: null, error }));
    prefetched.set(key, promise);
    return promise;
  }

  function prefetchNext() {
    if (startingSession || typeof studyRuntime === 'undefined' || !studyRuntime.plan || !studyRuntime.activity) return;
    syncPlan();
    const plan = activities();
    const nextIndex = Number(studyRuntime.index || 0) + 1;
    if (nextIndex >= plan.length) return;
    prepare(nextIndex, plan[nextIndex]);
  }

  function continueStatus(button) {
    let status = button.parentElement?.querySelector('.continue-plan-status');
    if (!status && button.parentElement) {
      status = document.createElement('p');
      status.className = 'muted small continue-plan-status';
      button.insertAdjacentElement('afterend', status);
    }
    return status;
  }

  function finishSession() {
    const modality = studyRuntime.activity?.modality || 'speak';
    const panel = document.getElementById(`mode-${modality}`);
    if (!panel) return;
    panel.innerHTML = `
      <span class="badge">SESSION COMPLETE</span>
      <h2>Today's planned work is done.</h2>
      <p class="prompt">Your attempts and evidence are saved. Tomorrow's planner can use what happened today.</p>
      <button class="primary finish-to-dashboard">Back to dashboard</button>`;
    panel.querySelector('.finish-to-dashboard')?.addEventListener('click', () => setView('dashboard'));
  }

  function renderStartLoading(mode) {
    if (typeof setView === 'function') setView('study');
    if (typeof setMode === 'function') setMode('speak');
    const panel = document.getElementById('mode-speak');
    if (!panel) return { status: null, elapsed: null };
    panel.innerHTML = `
      <span class="badge">ADAPTIVE STUDY</span>
      <h2>Building your session…</h2>
      <p class="prompt">First Focuslyra chooses today's plan from your priorities and evidence. Then Qwen prepares the first activity locally.</p>
      <div class="feedback good">
        <strong class="session-start-step">Preparing the plan…</strong>
        <p class="muted small session-start-elapsed">0s elapsed</p>
      </div>`;
    const subtitle = document.getElementById('pageSubtitle');
    if (subtitle) subtitle.textContent = mode === 'minimum'
      ? 'Preparing a short adaptive session…'
      : 'Preparing today’s adaptive session…';
    return {
      status: panel.querySelector('.session-start-step'),
      elapsed: panel.querySelector('.session-start-elapsed'),
    };
  }

  function renderStartError(error, mode) {
    const panel = document.getElementById('mode-speak');
    if (!panel) return;
    panel.innerHTML = `
      <span class="badge">SESSION ERROR</span>
      <h2>Focuslyra could not start the session.</h2>
      <p class="prompt">${typeof escapeHtml === 'function' ? escapeHtml(error?.message || String(error)) : String(error?.message || error)}</p>
      <button type="button" class="primary retry-adaptive-start">Try again</button>`;
    panel.querySelector('.retry-adaptive-start')?.addEventListener('click', () => robustStartAdaptiveSession(mode));
  }

  async function robustStartAdaptiveSession(mode = 'normal') {
    if (startingSession) return;
    if (typeof studyRuntime === 'undefined') {
      renderStartError(new Error('The adaptive study engine has not finished loading yet.'), mode);
      return;
    }

    startingSession = true;
    transitioning = false;
    prefetched.clear();
    studyRuntime.plan = null;
    studyRuntime.activity = null;
    studyRuntime.index = 0;

    const loading = renderStartLoading(mode);
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      if (!loading.elapsed) return;
      const seconds = Math.floor((Date.now() - startedAt) / 1000);
      loading.elapsed.textContent = seconds < 15
        ? `${seconds}s elapsed`
        : `${seconds}s elapsed · the local model is still working; the app has not frozen.`;
    }, 1000);

    try {
      // Planning is deterministic and quick. Do it separately so the interface
      // responds instantly instead of waiting for Qwen before showing anything.
      const plan = await api(`/api/study/plan?mode=${encodeURIComponent(mode === 'minimum' ? 'minimum' : 'normal')}`);
      if (!Array.isArray(plan?.activities) || !plan.activities.length) {
        throw new Error(plan?.reason || 'No study activity is available for the selected learner.');
      }

      studyRuntime.plan = plan;
      studyRuntime.index = 0;
      if (typeof state !== 'undefined') state.sessionDurationMinutes = plan.total_minutes;
      if (typeof updatePlanSidebar === 'function') updatePlanSidebar();
      if (loading.status) loading.status.textContent = `Plan ready · preparing activity 1/${plan.activities.length} locally…`;

      const first = await requestActivity(plan.activities[0]);
      if (typeof state !== 'undefined') state.currentLanguageCode = first.language_code;
      renderActivity(first);
    } catch (error) {
      console.error('Could not start the Focuslyra adaptive session:', error);
      renderStartError(error, mode);
    } finally {
      window.clearInterval(timer);
      startingSession = false;
      setTimeout(prefetchNext, 0);
    }
  }

  // users.js owns the Study placeholder and calls this global function. Replace
  // the older implementation at runtime so both the sidebar Study button and
  // the placeholder Start button use the responsive two-step start flow.
  window.startAdaptiveSession = robustStartAdaptiveSession;

  async function handleContinue(event) {
    const button = event.target.closest?.('.continue-plan');
    if (!button) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    if (transitioning || startingSession || typeof studyRuntime === 'undefined' || !studyRuntime.plan) return;
    syncPlan();

    const plan = activities();
    const currentIndex = Number(studyRuntime.index || 0);
    if (currentIndex >= plan.length - 1) {
      finishSession();
      return;
    }

    const nextIndex = currentIndex + 1;
    const slot = plan[nextIndex];
    const key = slotKey(nextIndex, slot);
    const alreadyPreparing = prefetched.has(key);
    const status = continueStatus(button);

    transitioning = true;
    button.disabled = true;
    button.textContent = alreadyPreparing ? 'Opening next activity…' : 'Preparing next activity…';
    if (status) {
      status.textContent = alreadyPreparing
        ? 'The next activity is already being prepared locally.'
        : 'Qwen is preparing the next activity locally. This can take a few seconds the first time.';
    }

    try {
      const prepared = await prepare(nextIndex, slot);
      if (prepared.error) throw prepared.error;

      studyRuntime.index = nextIndex;
      prefetched.delete(key);
      renderActivity(prepared.activity);
      setTimeout(prefetchNext, 0);
    } catch (error) {
      console.error('Could not continue the Focuslyra plan:', error);
      button.disabled = false;
      button.textContent = 'Try next activity again →';
      prefetched.delete(key);
      if (status) status.textContent = `Could not prepare the next activity: ${error.message}`;
    } finally {
      transitioning = false;
    }
  }

  document.addEventListener('click', handleContinue, true);

  // Warm exactly one upcoming activity after the current one has rendered.
  const host = document.querySelector('#study .study-main');
  if (host) {
    const observer = new MutationObserver(() => setTimeout(prefetchNext, 0));
    observer.observe(host, { childList: true, subtree: true });
  }

  setTimeout(prefetchNext, 0);
})();
