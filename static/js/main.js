'use strict';

const fileInput    = document.getElementById('fileInput');
const dropZone     = document.getElementById('dropZone');
const fileHint     = document.getElementById('fileHint');
const uploadForm   = document.getElementById('uploadForm');
const analyzeBtn   = document.getElementById('analyzeBtn');
const errorBanner  = document.getElementById('errorBanner');
const errorMessage = document.getElementById('errorMessage');
const resultsSection = document.getElementById('resultsSection');
const summaryText  = document.getElementById('summaryText');
const keyPointsList = document.getElementById('keyPointsList');
const resetBtn     = document.getElementById('resetBtn');
const uploadSection = document.getElementById('uploadSection');

// ── File selection ──────────────────────────────────

fileInput.addEventListener('change', () => {
  handleFileSelection(fileInput.files[0]);
});

dropZone.addEventListener('click', (e) => {
  if (e.target !== fileInput && !e.target.closest('label')) {
    fileInput.click();
  }
});

dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fileInput.click();
  }
});

// ── Drag & drop ─────────────────────────────────────

['dragenter', 'dragover'].forEach(evt => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
});

['dragleave', 'drop'].forEach(evt => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
  });
});

dropZone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  handleFileSelection(file);
});

// ── Helpers ──────────────────────────────────────────

function handleFileSelection(file) {
  hideError();
  if (!file) return;

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showError('PDF 파일만 업로드 가능합니다.');
    analyzeBtn.disabled = true;
    return;
  }

  if (file.size > 16 * 1024 * 1024) {
    showError('파일 크기는 16 MB를 초과할 수 없습니다.');
    analyzeBtn.disabled = true;
    return;
  }

  fileHint.textContent = `선택된 파일: ${file.name} (${formatFileSize(file.size)})`;
  analyzeBtn.disabled = false;
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.hidden = false;
}

function hideError() {
  errorBanner.hidden = true;
  errorMessage.textContent = '';
}

function setLoading(loading) {
  if (loading) {
    analyzeBtn.classList.add('btn--loading');
    analyzeBtn.disabled = true;
  } else {
    analyzeBtn.classList.remove('btn--loading');
    analyzeBtn.disabled = false;
  }
}

// ── Form submit ──────────────────────────────────────

uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError();

  const file = fileInput.files[0];
  if (!file) {
    showError('파일을 선택해 주세요.');
    return;
  }

  setLoading(true);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('/analyze', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      showError(data.error || '알 수 없는 오류가 발생했습니다.');
      return;
    }

    renderResults(data);
  } catch (err) {
    console.error('Upload failed:', err);
    showError('서버와 통신 중 오류가 발생했습니다. 네트워크 연결을 확인해 주세요.');
  } finally {
    setLoading(false);
  }
});

// ── Render results ───────────────────────────────────

function renderResults(data) {
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

  uploadSection.hidden = true;
  resultsSection.hidden = false;
}

// ── Reset ────────────────────────────────────────────

resetBtn.addEventListener('click', () => {
  uploadForm.reset();
  fileHint.textContent = '최대 16 MB · PDF 형식만 지원';
  analyzeBtn.disabled = true;
  hideError();
  resultsSection.hidden = true;
  uploadSection.hidden = false;
});
