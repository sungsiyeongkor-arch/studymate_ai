// NEW: Dashboard JavaScript for StudyMate AI
// This file is entirely new – handles sidebar, theme, profile dropdown, and shared UI.
'use strict';

// ── Theme ──────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.textContent = theme === 'dark' ? '☀️' : '🌙';
    toggle.setAttribute('aria-label', theme === 'dark' ? '라이트모드 전환' : '다크모드 전환');
  }
  try { localStorage.setItem('studymate_theme', JSON.stringify(theme)); } catch (e) {}
}

(function initTheme() {
  try {
    const saved = JSON.parse(localStorage.getItem('studymate_theme') || '"light"');
    applyTheme(saved);
  } catch (e) {
    applyTheme('light');
  }
})();

const themeToggle = document.getElementById('themeToggle');
if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });
}

// ── Sidebar toggle (mobile) ────────────────────────────────────────────────
const sidebar       = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');

if (sidebar && sidebarToggle) {
  sidebarToggle.addEventListener('click', () => {
    const isOpen = sidebar.classList.toggle('sidebar--open');
    sidebarToggle.setAttribute('aria-expanded', String(isOpen));
  });

  // Close on backdrop click (mobile)
  document.addEventListener('click', (e) => {
    if (
      sidebar.classList.contains('sidebar--open') &&
      !sidebar.contains(e.target) &&
      !sidebarToggle.contains(e.target)
    ) {
      sidebar.classList.remove('sidebar--open');
      sidebarToggle.setAttribute('aria-expanded', 'false');
    }
  });
}

// ── Profile dropdown ───────────────────────────────────────────────────────
const profileBtn      = document.getElementById('profileMenuBtn');
const profileDropdown = document.getElementById('profileDropdown');

if (profileBtn && profileDropdown) {
  profileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = !profileDropdown.hidden;
    profileDropdown.hidden = isOpen;
    profileBtn.setAttribute('aria-expanded', String(!isOpen));
    if (!isOpen) profileDropdown.querySelector('a')?.focus();
  });

  document.addEventListener('click', (e) => {
    if (!profileDropdown.hidden && !profileBtn.contains(e.target) && !profileDropdown.contains(e.target)) {
      profileDropdown.hidden = true;
      profileBtn.setAttribute('aria-expanded', 'false');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !profileDropdown.hidden) {
      profileDropdown.hidden = true;
      profileBtn.setAttribute('aria-expanded', 'false');
      profileBtn.focus();
    }
  });
}

// ── Auto-dismiss flash messages ────────────────────────────────────────────
document.querySelectorAll('.flash').forEach((el) => {
  setTimeout(() => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  }, 4000);
});
