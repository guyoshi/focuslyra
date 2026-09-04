(() => {
  'use strict';

  // The local model may need several seconds to generate the next activity.
  // Prepare only the next slot in the background so Continue normally feels
  // instant, while keeping a clear loading/error state when generation is not
  // ready yet.
  const prefetched = new Map();
  let planRef = null;
  let transitioning = false;

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
    if (typeof studyRuntime === 'undefined' || !studyRuntime.plan) return;
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

  async function handleContinue(event) {
    const button = event.target.closest?.('.continue-plan');
    if (!button) return;

    // Replace the original unguarded handler from learning.js. Without this,
    // a slow local generation request looks like a dead button and a failed
    // request becomes an unhandled rejection with no learner-facing message.
    event.preventDefault();
    event.stopImmediatePropagation();

    if (transitioning || typeof studyRuntime === 'undefined' || !studyRuntime.plan) return;
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

      // Commit the plan position only after the next activity exists. This
      // prevents a failed request from silently skipping an activity.
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

  // Activity rendering and feedback both mutate the study card. That gives us
  // a cheap signal to warm exactly one upcoming activity in the background.
  const host = document.querySelector('#study .study-main');
  if (host) {
    const observer = new MutationObserver(() => setTimeout(prefetchNext, 0));
    observer.observe(host, { childList: true, subtree: true });
  }

  setTimeout(prefetchNext, 0);
})();
