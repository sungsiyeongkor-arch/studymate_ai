export const $ = (selector, parent = document) =>
  parent.querySelector(selector);
export const $$ = (selector, parent = document) => [
  ...parent.querySelectorAll(selector),
];
export function esc(value = "") {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
const paths = {
  book: '<path d="M3 4c4-1 7 0 9 2 2-2 5-3 9-2v15c-4-1-7 0-9 2-2-2-5-3-9-2z"/><path d="M12 6v15"/>',
  home: '<path d="m3 10 9-7 9 7v11H3z"/><path d="M9 21v-8h6v8"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  file: '<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8M8 17h6"/>',
  mic: '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',
  spark:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 5 2 5 3 1 1 3h6l1-3 3-1 2-5-2-5-3-1-1-3z"/>',
  flag: '<path d="M5 22V3c5-4 9 4 14 0v11c-5 4-9-4-14 0"/>',
  chat: '<path d="M21 11a9 9 0 0 1-9 9H3l2-5a9 9 0 1 1 16-4Z"/><path d="M8 10h8M8 14h5"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  logout: '<path d="M10 3H4v18h6m3-15 6 6-6 6m-5-6h13"/>',
  map: '<circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><path d="m10 8-4 8m8-8 4 8"/>',
  down: '<path d="m5 9 7 7 7-7"/>',
};
export function icon(name, cls = "") {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
}
export function badge(state) {
  const labels = {
    queued: "대기 중",
    running: "처리 중",
    completed: "완료",
    blocked: "설정 확인",
    failed: "재시도 필요",
    ready: "준비됨",
    review: "확인 필요",
    processing: "처리 중",
    automatic: "자동 추출",
    confirmed: "원문 확인됨",
    edited: "내용 편집",
    uncertain: "판독 확인",
    unreadable: "텍스트 없음",
  };
  return `<span class="badge ${esc(state)}">${esc(labels[state] || state)}</span>`;
}
export function empty(title, description, action = "") {
  return `<div class="empty"><div class="empty-icon">${icon("book")}</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${action}</div>`;
}
export function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("visible");
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(
    () => $("#toast").classList.remove("visible"),
    5000,
  );
}
export function modal(title, content) {
  $("#dialog-body").innerHTML =
    `<header class="modal-header"><h2>${esc(title)}</h2><button class="icon-button" id="close-dialog" aria-label="닫기">${icon("close")}</button></header>${content}`;
  const dialog = $("#dialog");
  if (!dialog.open) dialog.showModal();
  $("#close-dialog").onclick = () => dialog.close();
}
export function time(seconds) {
  const n = Math.floor(seconds || 0);
  return `${Math.floor(n / 3600) ? Math.floor(n / 3600) + ":" : ""}${String(Math.floor(n / 60) % 60).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
}
export function date(value) {
  return new Date(value).toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
  });
}
export async function busy(button, task) {
  const old = button.innerHTML;
  button.disabled = true;
  button.textContent = "처리 중…";
  try {
    return await task();
  } catch (e) {
    toast(e.message);
  } finally {
    button.disabled = false;
    button.innerHTML = old;
  }
}
