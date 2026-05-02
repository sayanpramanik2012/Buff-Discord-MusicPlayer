/* ── Sidebar toggle ──────────────────────────────────────────────────────── */
const sidebar  = document.querySelector('.sidebar');
const hamburger = document.querySelector('.hamburger');
if (hamburger && sidebar) {
  hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && e.target !== hamburger)
      sidebar.classList.remove('open');
  });
}

/* ── Auto-dismiss flash alerts ───────────────────────────────────────────── */
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => el.style.transition = 'opacity .5s', 2500);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 500); }, 3000);
});

/* ── Volume slider label ─────────────────────────────────────────────────── */
const volSlider = document.getElementById('volume');
const volLabel  = document.getElementById('volume-label');
if (volSlider && volLabel) {
  volSlider.addEventListener('input', () => volLabel.textContent = volSlider.value + '%');
}

/* ── Queue limit label ───────────────────────────────────────────────────── */
const qlSlider = document.getElementById('max_queue_length');
const qlLabel  = document.getElementById('ql-label');
if (qlSlider && qlLabel) {
  qlSlider.addEventListener('input', () => {
    qlLabel.textContent = qlSlider.value == 0 ? 'Unlimited' : qlSlider.value + ' tracks';
  });
}

/* ── Live bot status badge ───────────────────────────────────────────────── */
async function refreshStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    document.querySelectorAll('[data-stat-guilds]').forEach(el => el.textContent = d.guilds.toLocaleString());
    document.querySelectorAll('[data-stat-users]').forEach(el => el.textContent = d.users.toLocaleString());
    document.querySelectorAll('.bot-status-dot').forEach(dot => {
      dot.classList.toggle('online', d.online);
      dot.title = d.online ? 'Bot online' : 'Bot offline';
    });
  } catch {}
}
refreshStatus();
setInterval(refreshStatus, 30_000);

/* ── Plan assignment confirmation ────────────────────────────────────────── */
document.querySelectorAll('form.assign-plan-form').forEach(form => {
  form.addEventListener('submit', e => {
    const plan = form.querySelector('[name=plan]').value;
    const name = form.dataset.guildName || 'this server';
    if (!confirm(`Set plan to ${plan.toUpperCase()} for "${name}"?`)) e.preventDefault();
  });
});

/* ── Copy prefix shortcut ────────────────────────────────────────────────── */
document.querySelectorAll('[data-copy]').forEach(el => {
  el.style.cursor = 'pointer';
  el.title = 'Click to copy';
  el.addEventListener('click', () => {
    navigator.clipboard.writeText(el.dataset.copy).then(() => {
      const orig = el.textContent;
      el.textContent = 'Copied!';
      setTimeout(() => el.textContent = orig, 1200);
    });
  });
});
