(() => {
  async function refreshDashboardEvidence() {
    try {
      const [progress, plan] = await Promise.all([
        api('/api/progress'),
        api('/api/study/plan?mode=normal'),
      ]);

      const progressByCode = Object.fromEntries((progress.languages || []).map(item => [item.code, item]));
      const cards = [...document.querySelectorAll('#languageGrid .language-card')];
      (state.languages || []).forEach((language, index) => {
        const card = cards[index];
        if (!card) return;
        const evidence = progressByCode[language.code];
        const score = evidence?.overall_evidence_score;
        const bar = card.querySelector('.language-progress i');
        if (bar) {
          bar.style.width = score == null ? '0%' : `${Math.max(0, Math.min(100, score))}%`;
          bar.title = score == null ? 'No learner evidence yet' : `Evidence score: ${score}%`;
        }
        const existing = card.querySelector('.dashboard-evidence-meta');
        if (existing) existing.remove();
        const meta = document.createElement('div');
        meta.className = 'language-meta dashboard-evidence-meta';
        meta.innerHTML = score == null
          ? '<strong>Evidence:</strong> not enough data yet'
          : `<strong>Evidence:</strong> ${escapeHtml(score)}% · confidence ${escapeHtml(evidence.evidence_confidence)}% · ${escapeHtml(evidence.sessions_7d)} session(s) / 7d`;
        card.appendChild(meta);
      });

      const rhythm = document.getElementById('suggestedRhythm');
      if (rhythm) {
        const totals = new Map();
        for (const activity of (plan.activities || [])) {
          const code = activity.language_code;
          const current = totals.get(code) || { flag: activity.flag || '', name: activity.language_name || code, minutes: 0, modes: [] };
          current.minutes += Number(activity.minutes || 0);
          if (activity.modality && !current.modes.includes(activity.modality)) current.modes.push(activity.modality);
          totals.set(code, current);
        }
        rhythm.innerHTML = [...totals.values()].map(item => `
          <div class="activity">
            <span>${escapeHtml(item.flag)} ${escapeHtml(item.name)} <small class="muted">${escapeHtml(item.modes.join(' · '))}</small></span>
            <strong>${escapeHtml(item.minutes)}m</strong>
          </div>`).join('') || '<span class="muted small">No study plan available yet.</span>';
        const note = rhythm.parentElement?.querySelector('.muted.small');
        if (note) note.textContent = 'Calculated from your priorities, recency, review targets and learner evidence. No AI generation is needed for this preview.';
      }
    } catch (error) {
      console.warn('Could not refresh dashboard evidence:', error);
    }
  }

  const dashboardButton = document.querySelector('[data-view="dashboard"]');
  dashboardButton?.addEventListener('click', refreshDashboardEvidence);
  setTimeout(refreshDashboardEvidence, 0);
  window.FocuslyraDashboard = { refresh: refreshDashboardEvidence };
})();
