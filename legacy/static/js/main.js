'use strict';

// ── DOM refs ───────────────────────────────────────────────────────────────
const fileInput        = document.getElementById('fileInput');
const dropZone         = document.getElementById('dropZone');
const fileHint         = document.getElementById('fileHint');
const uploadForm       = document.getElementById('uploadForm');
const analyzeBtn       = document.getElementById('analyzeBtn');
const errorBanner      = document.getElementById('errorBanner');
const errorMessage     = document.getElementById('errorMessage');
const resultsSection   = document.getElementById('resultsSection');
const uploadSection    = document.getElementById('uploadSection');
const resetBtn         = document.getElementById('resetBtn');

// Analysis
const analysisResults  = document.getElementById('analysisResults');
const summaryText      = document.getElementById('summaryText');
const keyPointsList    = document.getElementById('keyPointsList');

// Quiz
const quizResults      = document.getElementById('quizResults');
const quizContainer    = document.getElementById('quizContainer');
const quizScore        = document.getElementById('quizScore');
const scoreDisplay     = document.getElementById('scoreDisplay');

// Settings
const settingsToggle   = document.getElementById('settingsToggle');
const settingsClose    = document.getElementById('settingsClose');
const settingsPanel    = document.getElementById('settingsPanel');
const settingsOverlay  = document.getElementById('settingsOverlay');
const themeToggle      = document.getElementById('themeToggle');
const languageSel      = document.getElementById('languageSel');
const numPoints        = document.getElementById('numPoints');
const numPointsDisp    = document.getElementById('numPointsDisplay');
const summarySentences = document.getElementById('summarySentences');
const numQuestions     = document.getElementById('numQuestions');
const numQuestionsDisp = document.getElementById('numQuestionsDisplay');
const analyzeSettings  = document.getElementById('analyzeSettings');
const quizSettings     = document.getElementById('quizSettings');
const modeRadios       = document.querySelectorAll('input[name="mode"]');

// ── Constants ──────────────────────────────────────────────────────────────
const MAX_FILE_SIZE  = 16 * 1024 * 1024; // 16 MB
const SETTINGS_KEY   = 'studymate_settings';

// ── Settings persistence ───────────────────────────────────────────────────
function getMode() {
  const checked = document.querySelector('input[name="mode"]:checked');
  return checked ? checked.value : 'analyze';
}

function updateRangeDisplays() {
  numPointsDisp.textContent    = numPoints.value;
  numQuestionsDisp.textContent = numQuestions.value;
}

function updateModeVisibility() {
  const mode = getMode();
  analyzeSettings.hidden = (mode !== 'analyze');
  quizSettings.hidden    = (mode !== 'quiz');
  const label = analyzeBtn.querySelector('.btn__label');
  if (label) label.textContent = mode === 'quiz' ? '퀴즈 생성 시작' : 'AI 분석 시작';
}

function saveSettings() {
  const s = {
    language:         languageSel.value,
    numPoints:        numPoints.value,
    summarySentences: summarySentences.value,
    numQuestions:     numQuestions.value,
    mode:             getMode(),
    theme:            document.documentElement.dataset.theme || 'light',
  };
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)); } catch (err) {
    console.error('Settings could not be saved:', err);
  }
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (s.language)         languageSel.value = s.language;
    if (s.numPoints)        numPoints.value = s.numPoints;
    if (s.summarySentences) summarySentences.value = s.summarySentences;
    if (s.numQuestions)     numQuestions.value = s.numQuestions;
    if (s.mode) {
      const radio = document.querySelector(`input[name="mode"][value="${s.mode}"]`);
      if (radio) radio.checked = true;
    }
    if (s.theme) applyTheme(s.theme);
  } catch (err) {
    console.error('Settings could not be loaded:', err);
  }

  updateRangeDisplays();
  updateModeVisibility();
}

// ── Theme ──────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  themeToggle.setAttribute('aria-label', theme === 'dark' ? '라이트모드 전환' : '다크모드 전환');
}

themeToggle.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  saveSettings();
});

// ── Settings panel ─────────────────────────────────────────────────────────
function openSettings() {
  settingsPanel.classList.add('is-open');
  settingsOverlay.removeAttribute('hidden');
  settingsClose.focus();
}

function closeSettings() {
  settingsPanel.classList.remove('is-open');
  settingsOverlay.setAttribute('hidden', '');
  saveSettings();
}

settingsToggle.addEventListener('click', openSettings);
settingsClose.addEventListener('click',  closeSettings);
settingsOverlay.addEventListener('click', closeSettings);

// Close settings on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && settingsPanel.classList.contains('is-open')) closeSettings();
});

numPoints.addEventListener('input', () => {
  numPointsDisp.textContent = numPoints.value;
});
numQuestions.addEventListener('input', () => {
  numQuestionsDisp.textContent = numQuestions.value;
});
modeRadios.forEach((r) => r.addEventListener('change', () => {
  updateModeVisibility();
  saveSettings();
}));
languageSel.addEventListener('change', saveSettings);
summarySentences.addEventListener('change', saveSettings);

// ── File selection ─────────────────────────────────────────────────────────
fileInput.addEventListener('change', () => handleFileSelection(fileInput.files[0]));

dropZone.addEventListener('click', (e) => {
  if (e.target !== fileInput && !e.target.closest('label')) fileInput.click();
});

dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

['dragenter', 'dragover'].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); })
);
['dragleave', 'drop'].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove('drag-over'); })
);
dropZone.addEventListener('drop', (e) => handleFileSelection(e.dataTransfer.files[0]));

function handleFileSelection(file) {
  hideError();
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showError('PDF 파일만 업로드 가능합니다.');
    analyzeBtn.disabled = true;
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    showError('파일 크기는 16 MB를 초과할 수 없습니다.');
    analyzeBtn.disabled = true;
    return;
  }
  fileHint.textContent = `선택된 파일: ${file.name} (${formatFileSize(file.size)})`;
  analyzeBtn.disabled = false;
}

function formatFileSize(bytes) {
  if (bytes < 1024)            return `${bytes} B`;
  if (bytes < 1024 * 1024)     return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.removeAttribute('hidden');
}

function hideError() {
  errorBanner.setAttribute('hidden', '');
  errorMessage.textContent = '';
}

function setLoading(loading) {
  analyzeBtn.classList.toggle('btn--loading', loading);
  analyzeBtn.disabled = loading;
}

// ── Form submit ────────────────────────────────────────────────────────────
uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError();

  const file = fileInput.files[0];
  if (!file) { showError('파일을 선택해 주세요.'); return; }

  const mode = getMode();
  setLoading(true);

  const formData = new FormData();
  formData.append('file', file);
  formData.append('mode', mode);
  formData.append('language', languageSel.value);
  formData.append('num_points', numPoints.value);
  formData.append('summary_sentences', summarySentences.value);
  formData.append('num_questions', numQuestions.value);

  try {
    const response = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || '알 수 없는 오류가 발생했습니다.');
      return;
    }
    if (mode === 'quiz') renderQuiz(data);
    else renderAnalysis(data);
  } catch (err) {
    console.error('Upload failed:', err);
    showError('서버와 통신 중 오류가 발생했습니다. 네트워크 연결을 확인해 주세요.');
  } finally {
    setLoading(false);
  }
});

// ── Render: analysis ───────────────────────────────────────────────────────
function renderAnalysis(data) {
  summaryText.textContent = data.summary || '요약을 가져올 수 없습니다.';

  keyPointsList.innerHTML = '';
  const points = Array.isArray(data.key_points) ? data.key_points : [];
  if (points.length === 0) {
    const li = document.createElement('li');
    li.textContent = '핵심 포인트를 가져올 수 없습니다.';
    keyPointsList.appendChild(li);
  } else {
    points.forEach((point) => {
      const li = document.createElement('li');
      li.textContent = point;
      keyPointsList.appendChild(li);
    });
  }

  analysisResults.removeAttribute('hidden');
  quizResults.setAttribute('hidden', '');
  showResults();
}

// ── Render: quiz ───────────────────────────────────────────────────────────
function renderQuiz(data) {
  const questions = Array.isArray(data.questions) ? data.questions : [];
  quizContainer.innerHTML = '';
  quizScore.setAttribute('hidden', '');

  let answered = 0;
  let correct  = 0;
  const total  = questions.length;

  questions.forEach((q, idx) => {
    const card = document.createElement('div');
    card.className = 'quiz-card';

    // Question header
    const qEl = document.createElement('div');
    qEl.className = 'quiz-card__question';
    const numSpan = document.createElement('span');
    numSpan.className = 'q-num';
    numSpan.textContent = `Q${idx + 1}.`;
    qEl.appendChild(numSpan);
    qEl.appendChild(document.createTextNode(q.question));
    card.appendChild(qEl);

    // Options
    const optsEl = document.createElement('div');
    optsEl.className = 'quiz-options';
    const options = Array.isArray(q.options) ? q.options : [];

    options.forEach((opt) => {
      const btn = document.createElement('button');
      btn.className = 'quiz-option';
      btn.textContent = opt;

      btn.addEventListener('click', () => {
        if (btn.disabled) return;

        // Disable all options for this question
        optsEl.querySelectorAll('.quiz-option').forEach((b) => { b.disabled = true; });

        // Safely extract leading letter (e.g. "A" from "A. 선택지")
        const trimmed   = (typeof opt === 'string' ? opt : '').trim();
        const letter    = trimmed.length > 0 ? trimmed.charAt(0).toUpperCase() : '';
        const answer    = String(q.answer || '').trim().toUpperCase();
        const isCorrect = letter !== '' && letter === answer;
        btn.classList.add(isCorrect ? 'correct' : 'incorrect');

        if (!isCorrect) {
          // Highlight the correct answer
          optsEl.querySelectorAll('.quiz-option').forEach((b) => {
            const bFirst = (b.textContent || '').trim().charAt(0).toUpperCase();
            if (bFirst === answer) b.classList.add('correct');
          });
        }

        answered++;
        if (isCorrect) correct++;

        if (answered === total) {
          const pct = Math.round((correct / total) * 100);
          scoreDisplay.textContent = `${correct} / ${total} (${pct}%)`;
          quizScore.removeAttribute('hidden');
          quizScore.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });

      optsEl.appendChild(btn);
    });

    card.appendChild(optsEl);
    quizContainer.appendChild(card);
  });

  analysisResults.setAttribute('hidden', '');
  quizResults.removeAttribute('hidden');
  showResults();
}

function showResults() {
  uploadSection.setAttribute('hidden', '');
  resultsSection.removeAttribute('hidden');
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Copy to clipboard ──────────────────────────────────────────────────────
document.querySelectorAll('.copy-btn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const el = document.getElementById(btn.dataset.target);
    if (!el) return;

    const text =
      el.tagName === 'UL'
        ? Array.from(el.querySelectorAll('li'))
            .map((li) => `• ${li.textContent}`)
            .join('\n')
        : el.textContent;

    try {
      await navigator.clipboard.writeText(text);
      const orig = btn.textContent;
      btn.textContent = '✅';
      setTimeout(() => { btn.textContent = orig; }, 1500);
    } catch (err) {
      console.error('Clipboard copy failed:', err);
      showError('클립보드 복사에 실패했습니다. 브라우저 권한을 확인해 주세요.');
    }
  });
});

// ── Reset ──────────────────────────────────────────────────────────────────
resetBtn.addEventListener('click', () => {
  uploadForm.reset();
  fileHint.textContent = '최대 16 MB · PDF 형식만 지원';
  analyzeBtn.disabled  = true;
  hideError();
  resultsSection.setAttribute('hidden', '');
  uploadSection.removeAttribute('hidden');
  quizScore.setAttribute('hidden', '');
});

// ── Init ───────────────────────────────────────────────────────────────────
loadSettings();
