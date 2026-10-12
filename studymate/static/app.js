import { api } from "./lib/api.js";
import {
  $,
  $$,
  esc,
  icon,
  modal,
  toast,
  empty,
  busy,
  badge,
} from "./lib/ui.js";
import { lectureView, materialView } from "./views/lecture.js";
import {
  reviewView,
  settingsView,
  chatView,
  mistakesView,
} from "./views/learning.js";
let user, status;
export const refresh = () => route();
export const formData = (form) => Object.fromEntries(new FormData(form));
export function field(label, name, type = "text", value = "") {
  return `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" required></label>`;
}
export function bindForm(id, fn) {
  $(id).onsubmit = (e) => {
    e.preventDefault();
    busy($("button[type=submit]", e.target), () => fn(formData(e.target)));
  };
}
export function newCourse() {
  modal(
    "새 과목",
    `<form id="new-course">${field("과목 이름", "title")}<label>소개<textarea name="description"></textarea></label><button type="submit" class="btn primary">과목 만들기</button></form>`,
  );
  bindForm("#new-course", async (d) => {
    await api("/courses", { method: "POST", body: d });
    $("#dialog").close();
    refresh();
  });
}
export function newLecture(courseId) {
  modal(
    "강의 준비",
    `<form id="new-lecture">${field("강의 제목", "title")}<label>단원 · 소주제 · 미리 알려줄 내용<textarea name="topic" placeholder="예: 인지심리학 · 작업기억과 장기기억 · Baddeley 모형"></textarea></label><label>강의 언어<select name="language"><option value="ko">한국어</option><option value="en">영어</option></select></label><button type="submit" class="btn primary">강의 만들기</button></form>`,
  );
  bindForm("#new-lecture", async (d) => {
    let l = await api("/lectures", {
      method: "POST",
      body: { ...d, course_id: courseId },
    });
    $("#dialog").close();
    location.hash = "/lecture/" + l.id;
  });
}
function auth(register = false) {
  $("#app").innerHTML =
    `<main class="auth"><section class="auth-story"><a class="brand" href="#/">${icon("book")} StudyMate<span>AI</span></a><div><span class="eyebrow">YOUR LEARNING, CONNECTED</span><h1>배운 순간을,<br>내 것이 되는 순간으로.</h1><p>강의자료와 녹음에서 시작해<br>이해하고, 질문하고, 오래 기억하세요.</p><div class="paper-art"><span>이해 → 연결 → 기억</span></div></div><small>자료에 근거한 학습, StudyMate AI</small></section><section class="auth-form"><div><span class="eyebrow">LET’S GET STARTED</span><h2>${register ? "나만의 공부 공간 만들기" : "다시 만나서 반가워요"}</h2><p class="muted">${register ? "자료와 학습 기록을 한곳에 모으세요." : "오늘의 배움을 이어가세요."}</p><form id="auth-form">${register ? field("이름", "name") : ""}${field("이메일", "email", "email")}${field("비밀번호 (12자 이상)", "password", "password")}<p id="auth-error" role="alert"></p><button class="btn primary" type="submit">${register ? "계정 만들기" : "로그인"} ${icon("arrow")}</button></form><button id="switch-auth" class="btn text">${register ? "이미 계정이 있어요 · 로그인" : "처음이신가요? 계정 만들기"}</button><p class="small muted">현재 설치된 StudyMate 서버에 계정이 생성됩니다.</p></div></section></main>`;
  $("#switch-auth").onclick = () => auth(!register);
  bindForm("#auth-form", async (d) => {
    try {
      const v = await api("/auth/" + (register ? "register" : "login"), {
        method: "POST",
        body: d,
      });
      user = v.user;
      await route();
    } catch (e) {
      $("#auth-error").textContent = e.message;
    }
  });
}
function shell(path) {
  const links = [
    ["/", "home", "학습 홈"],
    ["/library", "grid", "내 과목"],
    ["/review", "clock", "오늘의 복습"],
    ["/mistakes", "book", "오답 노트"],
    ["/inbox", "flag", "확인할 내용"],
    ["/search", "search", "자료 검색"],
  ];
  $("#app").innerHTML =
    `<div class="app-shell"><aside class="sidebar"><a class="brand" href="#/">${icon("book")} StudyMate<span>AI</span></a><span class="nav-label">MY WORKSPACE</span><nav>${links.map(([url, i, t]) => `<a href="#${url}" class="nav-link ${path === url ? "active" : ""}">${icon(i)}${t}</a>`).join("")}</nav><div class="sidebar-bottom"><div class="sidebar-note">작은 복습이<br><strong>오래가는 기억으로.</strong></div><a class="nav-link" href="#/settings">${icon("settings")}설정</a><button id="logout" class="nav-link">${icon("logout")}로그아웃</button><div class="profile"><span class="avatar">${esc(user.name.slice(0, 1))}</span><div><strong>${esc(user.name)}</strong><small>나의 학습 공간</small></div></div></div></aside><div class="workspace"><header class="topbar"><span>나의 학습 공간 <span class="muted">/ StudyMate</span></span><a class="search-shortcut" href="#/search">${icon("search")} 자료에서 찾아보기</a></header><main id="content" class="content"><p>학습 공간을 불러오는 중…</p></main></div></div>`;
  $("#logout").onclick = () =>
    busy($("#logout"), async () => {
      await api("/auth/logout", { method: "POST" });
      user = null;
      await api("/session");
      auth();
    });
}
async function dashboard(library = false) {
  const d = await api("/dashboard");
  $("#content").innerHTML =
    `<div class="page-heading"><div><span class="eyebrow">${library ? "MY COURSES" : "LEARN A LITTLE, REMEMBER LONGER"}</span><h1>${library ? "내 과목" : `${esc(user.name)}님, 오늘도 한 걸음.`}</h1><p class="muted">${library ? "과목별로 강의자료와 학습 기록을 정리하세요." : "배운 내용을 연결하고, 기억으로 남겨보세요."}</p></div><button class="btn primary" id="add-course">${icon("plus")} 새 과목</button></div>${
      !library
        ? `<section class="hero"><div><span class="eyebrow">TODAY’S LEARNING</span><h2>읽는 공부를 넘어,<br>기억하는 공부로.</h2><p>강의를 준비하고, 궁금한 건 바로 물어보고.<br>나에게 필요한 복습을 시작하세요.</p><a class="btn primary" href="#/review">오늘의 복습 시작 ${icon("arrow")}</a></div><div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="book-back"></div><div class="book-front"><span>STUDY<br>MATE.</span><small>Make it yours.</small></div><div class="float-label">${icon("check")} 하나씩, 확실하게</div></div></section><div class="stats">${[
            ["grid", d.courses.length, "함께 공부하는 과목"],
            ["file", d.counts.materials, "모아둔 학습자료"],
            ["clock", d.counts.due, "오늘 복습할 카드"],
            ["check", d.counts.attempts, "쌓아온 복습 기록"],
          ]
            .map(
              ([i, n, t]) =>
                `<div class="stat-card">${icon(i)}<div><strong>${n}</strong><span>${t}</span></div></div>`,
            )
            .join("")}</div>`
        : ""
    }<div class="dashboard-columns"><section><div class="section-heading"><h2>나의 과목 <span class="count">${d.courses.length}</span></h2></div><div class="course-grid">${
      d.courses
        .map(
          (c, i) =>
            `<article class="course-card"><div class="course-icon tone-${i % 4}">${icon("book")}</div><span class="eyebrow">COURSE ${String(i + 1).padStart(2, "0")}</span><h3>${esc(c.title)}</h3><p>${esc(c.description || "이 과목의 배움을 차곡차곡 모아요.")}</p><div class="course-footer"><span>${d.lectures.filter((l) => l.course_id === c.id).length}개의 강의</span><button class="icon-button open-course" data-id="${c.id}" aria-label="${esc(c.title)} 열기">${icon("arrow")}</button></div><div class="course-lectures">${d.lectures
              .filter((l) => l.course_id === c.id)
              .slice(0, 3)
              .map(
                (l) =>
                  `<a href="#/lecture/${l.id}">${esc(l.title)} ${icon("arrow")}</a>`,
              )
              .join(
                "",
              )}<button class="btn text add-lecture" data-id="${c.id}">+ 강의 추가</button></div></article>`,
        )
        .join("") ||
      empty(
        "첫 과목을 만들어보세요",
        "과목 안에 강의를 만들고 자료를 추가할 수 있어요.",
      )
    }<button class="course-card add-course-card" id="add-course-card">${icon("plus")}<strong>새로운 배움 시작하기</strong><span>과목 추가</span></button></div></section><aside><section class="review-promo"><span class="eyebrow">A MOMENT TO RECALL</span><h3>기억은 꺼내볼수록<br>단단해져요.</h3><p>정답을 보기 전에 먼저 떠올려보세요.<br>짧은 인출 연습부터 시작합니다.</p><a href="#/review" class="btn primary">${d.counts.due}개 카드 복습하기 ${icon("arrow")}</a></section><section class="panel"><h3>확인이 필요한 내용</h3><p class="muted">흐릿한 필기와 불확실한 전사를 원본과 비교하세요.</p><a href="#/inbox" class="text-link">${d.counts.review}개 확인하기 →</a></section>${!status.ai_ready ? '<div class="notice">AI 연결 준비 중<br><small>서버에 API 키를 설정하면 요약·받아쓰기·질문 기능을 사용할 수 있어요.</small><a href="#/settings">설정 안내 →</a></div>' : ""}</aside></div>`;
  $("#add-course").onclick = newCourse;
  $("#add-course-card").onclick = newCourse;
  $$(".add-lecture").forEach(
    (b) => (b.onclick = () => newLecture(b.dataset.id)),
  );
  $$(".open-course").forEach(
    (b) =>
      (b.onclick = () => {
        const c = d.courses.find((c) => c.id === b.dataset.id);
        modal(
          c.title,
          `<div class="stack">${
            d.lectures
              .filter((l) => l.course_id === c.id)
              .map(
                (l) =>
                  `<a class="list-row" href="#/lecture/${l.id}">${esc(l.title)} ${icon("arrow")}</a>`,
              )
              .join("") || "<p>아직 강의가 없어요.</p>"
          }<button id="course-lecture" class="btn primary">강의 추가</button></div>`,
        );
        $$("#dialog a").forEach(
          (a) => (a.onclick = () => $("#dialog").close()),
        );
        $("#course-lecture").onclick = () => newLecture(c.id);
      }),
  );
}
async function searchView(inbox = false) {
  $("#content").innerHTML =
    `<div class="page-heading"><div><span class="eyebrow">${inbox ? "REVIEW INBOX" : "FIND YOUR KNOWLEDGE"}</span><h1>${inbox ? "확인할 내용" : "자료 검색"}</h1><p class="muted">${inbox ? "AI가 놓칠 수 있는 내용을 원본과 함께 확인하세요." : "업로드한 자료와 수정한 녹취록에서 찾아보세요."}</p></div></div>${!inbox ? '<form id="search-form" class="inline-form"><input name="q" required minlength="2" placeholder="두 글자 이상 입력"><button class="btn primary" type="submit">검색</button></form>' : ""}<div id="results" class="stack"></div>`;
  const show = (rows) => {
    $("#results").innerHTML =
      rows
        .map(
          (s) =>
            `<a class="panel" href="#/material/${s.material_id}/${s.id}">${badge(s.state)}<h3>${s.page ? "페이지 " + s.page : "녹취 · 자료"}</h3><p class="prewrap">${esc(s.text || "읽히지 않는 영역입니다. 직접 확인하거나 확대 판독을 요청하세요.")}</p></a>`,
        )
        .join("") ||
      empty(
        "표시할 내용이 없어요",
        inbox
          ? "현재 확인 대기 중인 내용이 없습니다."
          : "다른 검색어로 찾아보세요.",
      );
  };
  if (inbox) show((await api("/review-inbox")).items);
  else
    bindForm("#search-form", async (d) =>
      show((await api("/search?q=" + encodeURIComponent(d.q))).items),
    );
}
async function route() {
  try {
    if (!user) {
      const s = await api("/session");
      user = s.user;
      if (!user) return auth();
    }
    status = await api("/status");
    const path = location.hash.slice(1) || "/";
    shell(path);
    const [kind, id, extra] = path.split("/").filter(Boolean);
    if (!kind || kind === "library") await dashboard(kind === "library");
    else if (kind === "lecture") await lectureView(id, status);
    else if (kind === "material") await materialView(id, extra, status);
    else if (kind === "review") await reviewView();
    else if (kind === "mistakes") await mistakesView();
    else if (kind === "settings") await settingsView(status);
    else if (kind === "chat") await chatView(id, status);
    else if (kind === "search" || kind === "inbox")
      await searchView(kind === "inbox");
    else
      $("#content").innerHTML = empty(
        "페이지를 찾을 수 없어요",
        "왼쪽 메뉴에서 다시 이동해 주세요.",
      );
  } catch (e) {
    if (e.status === 401) {
      user = null;
      return auth();
    }
    if ($("#content"))
      $("#content").innerHTML =
        `<div class="notice error">${esc(e.message)} <button id="reload" class="btn">다시 시도</button></div>`;
    else toast(e.message);
    if ($("#reload")) $("#reload").onclick = route;
  }
}
window.addEventListener("hashchange", route);
$(".skip").onclick = (e) => {
  e.preventDefault();
  const main = $("#content");
  if (main) {
    main.tabIndex = -1;
    main.focus();
  }
};
route();
