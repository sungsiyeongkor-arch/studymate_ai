import { api } from "../lib/api.js";
import { $, $$, esc, busy, badge, empty, modal } from "../lib/ui.js";
import { newLecture } from "../app.js";

const titles = {
  courses: "전체 과목",
  lectures: "과목의 강의",
  materials: "전체 자료",
  artifacts: "전체 학습 노트",
  terms: "전체 용어",
  jobs: "전체 처리 이력",
  examples: "전체 필체 예시",
  uploads: "업로드 관리",
  chats: "전체 대화 기록",
  revisions: "수정 이력",
};

export async function collectionView(spec) {
  const [name, params = ""] = spec.split("?");
  let next = null;
  const endpoint = "/collections/" + name + "?" + params;
  $("#content").innerHTML =
    `<div class="page-heading"><h1>${esc(titles[name] || "학습 기록")}</h1><a class="btn" href="#/library">내 과목</a></div><div id="collection-actions"></div><p class="small">한 번에 50개씩 표시합니다. 다음 버튼으로 이전 기록을 확인하세요.</p><div id="collection-items" class="stack"></div><div class="row"><button class="btn" id="collection-first">처음</button><button class="btn" id="collection-next">다음</button></div>`;
  if (name === "lectures" && new URLSearchParams(params).get("course_id")) {
    $("#collection-actions").innerHTML =
      '<button class="btn primary" id="collection-add">강의 추가</button>';
    $("#collection-add").onclick = () =>
      newLecture(new URLSearchParams(params).get("course_id"));
  }
  const load = async (cursor = "") => {
    const data = await api(endpoint + "&cursor=" + encodeURIComponent(cursor));
    next = data.next_cursor;
    $("#collection-next").disabled = !next;
    $("#collection-items").innerHTML =
      data.items
        .map((r) => {
          let href =
            name === "courses"
              ? "/collection/lectures?course_id=" + r.id
              : name === "lectures"
                ? "/lecture/" + r.id
                : name === "materials"
                  ? "/material/" + r.id
                  : r.lecture_id
                    ? "/lecture/" + r.lecture_id
                    : "";
          return `<article class="panel"><h3>${esc(r.title || r.name || r.word || r.kind || "학습 기록")}</h3><p class="prewrap">${esc(r.text || r.meaning || r.error || "")}</p>${r.status ? badge(r.status) : ""}<div class="row wrap">${href ? `<a class="btn small" href="#${href}">열기</a>` : ""}${name === "artifacts" ? `<a class="btn small" href="/api/artifacts/${r.id}/export">노트 다운로드</a>` : ""}${name === "examples" ? `<button class="btn small remove-example" data-id="${r.id}">예시 삭제</button>` : ""}${name === "jobs" && ["failed", "blocked"].includes(r.status) ? `<button class="btn small retry-job" data-id="${r.id}">재시도</button>` : ""}${name === "uploads" && r.status === "pending" ? `<button class="btn small cancel-upload" data-id="${r.id}">업로드 취소 · 공간 반환</button>` : ""}</div></article>`;
        })
        .join("") ||
      empty("기록이 없습니다", "새로운 자료를 추가하면 여기에 표시됩니다.");
    $$(".cancel-upload").forEach(
      (b) =>
        (b.onclick = () =>
          busy(b, async () => {
            await api("/uploads/" + b.dataset.id, { method: "DELETE" });
            await load();
          })),
    );
    $$(".retry-job").forEach(
      (b) =>
        (b.onclick = () =>
          busy(b, async () => {
            await api("/jobs/" + b.dataset.id + "/retry", { method: "POST" });
            await load();
          })),
    );
    $$(".remove-example").forEach(
      (b) =>
        (b.onclick = () => {
          modal(
            "필체 예시 삭제",
            '<p>이 예시를 이후 판독의 참고 대상에서 제거할까요?</p><button class="btn danger" id="remove-confirm">삭제</button>',
          );
          $("#remove-confirm").onclick = () =>
            busy($("#remove-confirm"), async () => {
              await api("/handwriting-examples/" + b.dataset.id, {
                method: "DELETE",
              });
              $("#dialog").close();
              await load();
            });
        }),
    );
  };
  $("#collection-first").onclick = () =>
    busy($("#collection-first"), () => load());
  $("#collection-next").onclick = () =>
    busy($("#collection-next"), () => load(next));
  await load();
}
