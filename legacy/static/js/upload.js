// NEW: Upload page JavaScript for StudyMate AI
// This file is entirely new – handles the new upload form with progress overlay.
'use strict';

const fileInput       = document.getElementById('fileInput');
const dropZone        = document.getElementById('dropZone');
const fileHint        = document.getElementById('fileHint');
const uploadForm      = document.getElementById('uploadForm');
const analyzeBtn      = document.getElementById('analyzeBtn');
const errorBanner     = document.getElementById('errorBanner');
const errorMessage    = document.getElementById('errorMessage');
const progressOverlay = document.getElementById('progressOverlay');
const progressMessage = document.getElementById('progressMessage');
const numQuestions    = document.getElementById('numQuestions');
const numQuestionsDisp= document.getElementById('numQuestionsDisplay');
const quizCountGroup  = document.getElementById('quizCountGroup');
const modeRadios      = document.querySelectorAll('input[name="mode"]');

const MAX_FILE_SIZE = 16 * 1024 * 1024;

// ── Mode visibility ─────────────────────────────────────────────────────────
function getMode() {
  const checked = document.querySelector('input[name="mode"]:checked');
  return checked ? checked.value : 'summarize';
}

function updateModeUI() {
  const mode = getMode();
  if (quizCountGroup) quizCountGroup.hidden = (mode !== 'quiz');
  const label = analyzeBtn?.querySelector('.btn__label');
  if (label) {
    const labels = {
      summarize:   'AI 요약 노트 생성',
      quiz:        'AI 예상 문제 생성',
      upload_only: '자료 저장',
    };
    label.textContent = labels[mode] || 'AI 분석 시작';
  }
}

modeRadios.forEach((r) => r.addEventListener('change', updateModeUI));
updateModeUI();

if (numQuestions && numQuestionsDisp) {
  numQuestions.addEventListener('input', () => {
    numQuestionsDisp.textContent = numQuestions.value;
  });
}

// ── File selection ──────────────────────────────────────────────────────────
if (fileInput) fileInput.addEventListener('change', () => handleFileSelection(fileInput.files[0]));

if (dropZone) {
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
}

function handleFileSelection(file) {
  hideError();
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showError('PDF 파일만 업로드 가능합니다.');
    if (analyzeBtn) analyzeBtn.disabled = true;
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    showError('파일 크기는 16 MB를 초과할 수 없습니다.');
    if (analyzeBtn) analyzeBtn.disabled = true;
    return;
  }
  if (fileHint) fileHint.textContent = `선택된 파일: ${file.name} (${formatSize(file.size)})`;
  if (analyzeBtn) analyzeBtn.disabled = false;
}

function formatSize(bytes) {
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── UI helpers ──────────────────────────────────────────────────────────────
function showError(msg) {
  if (errorMessage) errorMessage.textContent = msg;
  if (errorBanner)  errorBanner.removeAttribute('hidden');
}

function hideError() {
  if (errorBanner)  errorBanner.setAttribute('hidden', '');
  if (errorMessage) errorMessage.textContent = '';
}

function setLoading(loading) {
  if (!analyzeBtn) return;
  analyzeBtn.classList.toggle('btn--loading', loading);
  analyzeBtn.disabled = loading;
  if (progressOverlay) progressOverlay.hidden = !loading;
}

// ── Form submit ─────────────────────────────────────────────────────────────
if (uploadForm) {
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();

    const file = fileInput?.files[0];
    if (!file) { showError('파일을 선택해 주세요.'); return; }

    const mode = getMode();
    setLoading(true);

    const messages = {
      summarize:   'AI가 요약 노트를 생성 중입니다… (1~2분 소요)',
      quiz:        'AI가 예상 문제를 생성 중입니다… (1~2분 소요)',
      upload_only: '자료를 저장하는 중입니다…',
    };
    if (progressMessage) progressMessage.textContent = messages[mode] || 'AI가 분석 중입니다…';

    const formData = new FormData(uploadForm);

    try {
      const response = await fetch('/api/upload', { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) {
        showError(data.error || '알 수 없는 오류가 발생했습니다.');
        return;
      }
      // Redirect to result page
      if (data.redirect) {
        window.location.href = data.redirect;
      } else {
        window.location.href = '/materials';
      }
    } catch (err) {
      console.error('Upload failed:', err);
      showError('서버와 통신 중 오류가 발생했습니다. 네트워크 연결을 확인해 주세요.');
    } finally {
      setLoading(false);
    }
  });
}
