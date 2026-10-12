import { api, uploadFile } from "../lib/api.js";
import {
  $,
  $$,
  esc,
  icon,
  badge,
  empty,
  modal,
  toast,
  time,
  busy,
} from "../lib/ui.js";
import { bindForm, field, refresh } from "../app.js";
let recorder,
  recordingStream,
  recordingParts = [],
  recordingLecture;
window.addEventListener("beforeunload", (e) => {
  if (recorder?.state === "recording") {
    e.preventDefault();
    e.returnValue = "";
  }
});
const names = {
  extract: "자료 읽기",
  transcribe: "받아쓰기",
  summary: "요약 노트",
  quiz: "인출 연습",
  concepts: "개념 연결도",
  terms: "용어 추출",
};
export async function lectureView(id, status) {
  const d = await api("/lectures/" + id),
    l = d.lecture;
  $("#content").innerHTML =
    `<div class="page-heading"><div><a class="small" href="#/library">내 과목 / 강의</a><h1>${esc(l.title)}</h1><p>${esc(l.topic || "자료를 올리고 강의의 맥락을 알려주세요.")}</p></div><a class="btn primary" href="#/chat/${id}">${icon("chat")} AI에게 질문</a></div><div class="tabs"><button class="tab active" data-tab="prepare">강의 준비 · 자료</button><button class="tab" data-tab="learn">학습 노트 · 개념도</button><button class="tab" data-tab="terms">전문용어장</button></div><div class="row wrap"><a class="btn small" href="#/collection/materials?lecture_id=${id}">전체 자료</a><a class="btn small" href="#/collection/artifacts?lecture_id=${id}">전체 학습 노트</a><a class="btn small" href="#/collection/terms?course_id=${l.course_id}">전체 용어</a><a class="btn small" href="#/collection/jobs?lecture_id=${id}">전체 처리 이력</a></div><div id="lecture-pane"></div>`;
  const render = (tab) => {
    $$(".tab").forEach((b) =>
      b.classList.toggle("active", b.dataset.tab === tab),
    );
    if (tab === "prepare") {
      $("#lecture-pane").innerHTML =
        `<div class="lecture-grid"><section class="stack"><div class="panel"><div class="section-heading"><h2>01. 강의 맥락 알려주기</h2><button class="btn small" id="edit-topic">수정</button></div><p class="prose">${esc(l.topic || "주제, 단원, 교수님이 사용하는 표현을 입력해 주세요.")}</p></div><div class="panel"><h2>02. 자료 먼저 올리기</h2><p class="small">텍스트가 추출된 자료와 확인한 전문용어를 받아쓰기의 참고 맥락으로 사용합니다.</p><label class="upload-zone" id="drop-zone">${icon("upload")}<h3>강의자료를 여기에 놓으세요</h3><p>PDF · PPTX · DOCX · TXT · 음성 파일 / 파일당 최대 512MB</p><input type="file" id="files" multiple accept=".pdf,.pptx,.docx,.txt,.md,.mp3,.wav,.m4a,.mp4,.webm,.ogg,.flac"></label><p id="upload-progress" aria-live="polite"></p><div>${d.materials.map((m) => `<a class="list-row" href="#/material/${m.id}"><div class="row"><span class="file-icon">${esc(m.kind.toUpperCase())}</span><div><h3>${esc(m.name)}</h3><small>${(m.size / 1048576).toFixed(1)} MB</small></div></div>${badge(m.status)}</a>`).join("") || '<p class="small">아직 올린 자료가 없어요.</p>'}</div></div><div class="panel"><h2>03. 강의 녹음하기</h2><p class="small">긴 강의는 기기의 녹음 앱으로 저장한 파일을 올리는 방법을 권장합니다. 브라우저 녹음은 이 창을 유지해야 하며 메모리에 보관됩니다.</p><div class="row wrap"><button id="record" class="btn">${icon("mic")} ${recorder?.state === "recording" ? "녹음 정지 · 저장" : "브라우저 녹음 시작"}</button><span id="record-state" class="small">${recorder?.state === "recording" ? "녹음 중 · 창을 닫지 마세요" : ""}</span></div><p class="small">주변 사람에게 녹음 사실을 알리고, 업로드 권한이 있는 수업만 사용하세요.</p></div></section><aside class="stack"><div class="panel"><div class="section-heading"><h3>처리 현황</h3><button class="icon-button" id="jobs-refresh" aria-label="처리 상태 새로고침">↻</button></div>${d.jobs.map((j) => `<div class="job"><div class="row between"><strong>${names[j.kind] || esc(j.kind)}</strong>${badge(j.status)}</div>${j.total ? `<progress max="${j.total}" value="${j.progress}"></progress><small>${j.progress} / ${j.total} 구간</small>` : ""}<p>${esc(j.error || "")}</p>${["failed", "blocked"].includes(j.status) ? `<button class="btn small retry" data-id="${j.id}">이어서 재시도</button>` : ""}</div>`).join("") || '<p class="small">자료를 올리면 처리가 시작됩니다.</p>'}</div><div class="notice">${status.ai_ready ? "AI 연결 설정이 있습니다. 실제 호출 가능 여부는 처리 시 확인합니다." : "API 키 설정 전에는 자동 요약·판독·받아쓰기가 대기 상태가 됩니다."}<br>${status.audio_ready ? "긴 녹음 처리 도구가 준비되었습니다." : "긴 녹음 처리에는 서버에 FFmpeg 설치가 필요합니다."}</div><div class="panel"><h3>작은 글씨도 원본에서</h3><p class="small">PDF를 열고 필기 영역을 드래그하세요. 원본 PDF에서 영역을 크게 렌더링한 뒤 판독 결과를 직접 확인합니다.</p></div></aside></div>`;
      $("#edit-topic").onclick = () => {
        modal(
          "강의 맥락 수정",
          `<form id="topic-form">${field("제목", "title", "text", l.title)}<label>주제 · 단원 · 소주제<textarea name="topic">${esc(l.topic)}</textarea></label><button class="btn primary" type="submit">저장</button></form>`,
        );
        bindForm("#topic-form", async (v) => {
          await api("/lectures/" + id, { method: "PATCH", body: v });
          $("#dialog").close();
          refresh();
        });
      };
      const upload = async (files) => {
        for (const f of files) {
          $("#upload-progress").textContent = f.name + " 업로드 중…";
          await uploadFile(f, id, (p) => {
            if ($("#upload-progress"))
              $("#upload-progress").textContent = `${f.name} · ${p}%`;
          });
        }
        toast("업로드 완료. 작업자가 자료를 처리합니다.");
        await refresh();
      };
      $("#files").onchange = (e) =>
        upload(e.target.files).catch((e) => toast(e.message));
      const zone = $("#drop-zone");
      zone.ondragover = (e) => {
        e.preventDefault();
        zone.classList.add("over");
      };
      zone.ondragleave = () => zone.classList.remove("over");
      zone.ondrop = (e) => {
        e.preventDefault();
        zone.classList.remove("over");
        upload(e.dataTransfer.files).catch((e) => toast(e.message));
      };
      $("#jobs-refresh").onclick = refresh;
      $$(".retry").forEach(
        (b) =>
          (b.onclick = () =>
            busy(b, async () => {
              await api("/jobs/" + b.dataset.id + "/retry", { method: "POST" });
              refresh();
            })),
      );
      $("#record").onclick = () =>
        busy($("#record"), async () => {
          if (recorder?.state === "recording") {
            recorder.stop();
            return;
          }
          if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
            throw Error(
              "이 브라우저에서 녹음을 지원하지 않습니다. 녹음 파일을 업로드해 주세요.",
            );
          recordingStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
          recordingParts = [];
          recordingLecture = id;
          recorder = new MediaRecorder(recordingStream);
          recorder.ondataavailable = (e) => {
            if (e.data.size) recordingParts.push(e.data);
          };
          recorder.onstop = async () => {
            recordingStream.getTracks().forEach((t) => t.stop());
            const ext = recorder.mimeType.includes("mp4")
              ? "m4a"
              : recorder.mimeType.includes("ogg")
                ? "ogg"
                : "webm";
            const file = new File(
              recordingParts,
              `lecture-${Date.now()}.${ext}`,
              { type: recorder.mimeType },
            );
            const url = URL.createObjectURL(file);
            modal(
              "녹음 완료",
              `<div class="stack"><audio controls src="${url}"></audio><a class="btn" id="download-recording" href="${url}" download="${file.name}">원본 녹음 다운로드</a><p class="small">업로드 전 원본을 기기에 저장해 두세요.</p><button class="btn primary" id="save-recording">강의에 업로드</button><p id="record-progress"></p></div>`,
            );
            $("#save-recording").onclick = () =>
              busy($("#save-recording"), async () => {
                await uploadFile(
                  file,
                  recordingLecture,
                  (p) => ($("#record-progress").textContent = p + "%"),
                );
                $("#dialog").close();
                URL.revokeObjectURL(url);
                recordingParts = [];
                refresh();
              });
          };
          recorder.start(10000);
          $("#record-state").textContent = "녹음 중 · 창을 닫지 마세요";
          setTimeout(() => {
            if ($("#record"))
              $("#record").innerHTML = icon("mic") + " 녹음 정지 · 저장";
          }, 0);
        });
    } else if (tab === "terms") {
      $("#lecture-pane").innerHTML =
        `<div class="page-heading"><p>확인한 용어와 발음·연관어를 인식에 참고합니다. 연관어를 정답으로 강제 치환하지 않습니다.</p><button class="btn primary" id="add-term">${icon("plus")} 용어 등록</button></div><div class="notes-grid">${d.terms.map((t) => `<div class="term"><div class="row between"><h3>${esc(t.word)}</h3>${badge(t.confirmed ? "confirmed" : "uncertain")}</div><small>${esc(t.pronunciation)}</small><p>${esc(t.meaning)}</p><p class="small">연관어: ${esc(t.related.join(", "))}</p><div class="row">${!t.confirmed ? `<button class="btn small confirm-term" data-id="${t.id}">확인 · 사용</button>` : ""}<button class="btn small delete-term" data-id="${t.id}">삭제</button></div></div>`).join("") || empty("용어장을 준비해 보세요", "강의 전에 전문용어를 등록하면 받아쓰기 참고 맥락에 포함됩니다.")}</div>`;
      $("#add-term").onclick = () => {
        modal(
          "전문용어 등록",
          `<form id="term-form">${field("전문용어", "word")}<label>발음<input name="pronunciation"></label><label>의미<textarea name="meaning"></textarea></label><label>연관 단어 (쉼표로 구분)<input name="related"></label><button class="btn primary" type="submit">등록</button></form>`,
        );
        bindForm("#term-form", async (v) => {
          const t = await api("/terms", {
            method: "POST",
            body: { ...v, course_id: l.course_id },
          });
          d.terms.unshift(t);
          $("#dialog").close();
          render("terms");
        });
      };
      $$(".confirm-term").forEach(
        (b) =>
          (b.onclick = () =>
            busy(b, async () => {
              await api("/terms/" + b.dataset.id, {
                method: "PATCH",
                body: { confirmed: true },
              });
              d.terms.find((t) => t.id === b.dataset.id).confirmed = true;
              render("terms");
            })),
      );
      $$(".delete-term").forEach(
        (b) =>
          (b.onclick = () =>
            busy(b, async () => {
              await api("/terms/" + b.dataset.id, { method: "DELETE" });
              d.terms = d.terms.filter((t) => t.id !== b.dataset.id);
              render("terms");
            })),
      );
    } else {
      $("#lecture-pane").innerHTML =
        `<section class="panel stack"><div><h2>이해에서 기억으로</h2><p>자료에 근거해 요약하고, 개념을 연결하고, 답을 떠올려보세요.</p></div><div class="row wrap">${["summary", "concepts", "quiz", "terms"].map((k) => `<button class="btn generate" data-kind="${k}">${icon(k === "concepts" ? "map" : "spark")} ${names[k]}</button>`).join("")}<button class="btn" id="manual-card">직접 카드 만들기</button></div><p class="small">긴 자료는 전체 구간을 나눠 여러 노트로 생성합니다. 불확실한 판독은 먼저 확인해 주세요.</p></section><div class="notes-grid">${d.artifacts.map((a) => `<button class="panel artifact" data-id="${a.id}"><span class="eyebrow">${names[a.kind]}</span><h3>${esc(a.title)}</h3><p>${a.stale ? "원본이 변경되어 재생성이 필요합니다." : "내용과 근거 확인하기 →"}</p></button>`).join("")}</div>`;
      $$(".generate").forEach(
        (b) =>
          (b.onclick = () => {
            modal(
              names[b.dataset.kind] + " 설정",
              `<form id="generate-form"><label>학습 목적<select name="purpose"><option>처음 배우기</option><option>시험 전 복습</option><option>개념의 조건과 적용 연습</option></select></label><label>출력 언어<select name="language"><option value="ko">한국어</option><option value="en">영어</option></select></label>${b.dataset.kind === "summary" ? '<label>요약 길이<select name="summary_sentences"><option value="3">짧게 · 3문장</option><option value="5" selected>보통 · 5문장</option><option value="7">길게 · 7문장</option></select></label><label>핵심 포인트 수<input name="key_points" type="number" min="1" max="20" value="10"></label>' : ""}${b.dataset.kind === "quiz" ? '<label>문제 수<input name="question_count" type="number" min="1" max="20" value="5"></label>' : ""}<p class="small">긴 자료는 구간별로 위 수량을 요청합니다. 내용이 부족하면 AI가 더 적게 생성할 수 있습니다.</p><button class="btn primary" type="submit">생성 시작</button></form>`,
            );
            bindForm("#generate-form", async (v) => {
              for (const k of [
                "summary_sentences",
                "key_points",
                "question_count",
              ])
                if (v[k]) v[k] = Number(v[k]);
              await api("/lectures/" + id + "/generate", {
                method: "POST",
                body: { ...v, kind: b.dataset.kind },
              });
              $("#dialog").close();
              toast("생성을 요청했습니다. 처리 현황에서 확인하세요.");
              refresh();
            });
          }),
      );
      $("#manual-card").onclick = () => {
        modal(
          "인출 카드 만들기",
          `<form id="card-form">${field("질문", "question")}<label>정답<textarea required name="answer"></textarea></label><label>객관식 선택지 (선택 사항 · 한 줄에 하나)<textarea name="choices" placeholder="비워두면 자유 응답 카드입니다. 정답과 정확히 같은 선택지를 하나 넣어주세요."></textarea></label><label>해설<textarea name="explanation"></textarea></label><label>개념<input name="concept"></label><button class="btn primary" type="submit">복습에 추가</button></form>`,
        );
        bindForm("#card-form", async (v) => {
          v.options = v.choices
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean);
          delete v.choices;
          await api("/cards", {
            method: "POST",
            body: { ...v, lecture_id: id },
          });
          $("#dialog").close();
          toast("오늘의 복습에 추가했습니다.");
        });
      };
      $$(".artifact").forEach(
        (b) =>
          (b.onclick = () =>
            openArtifact(b.dataset.id).catch((e) => toast(e.message))),
      );
    }
  };
  $$(".tab").forEach((b) => (b.onclick = () => render(b.dataset.tab)));
  render("prepare");
}
export async function openArtifact(id) {
  const d = await api("/artifacts/" + id),
    a = d.artifact || d;
  const c = a.content;
  const sources = d.sources || [];
  let content = "";
  if (a.kind === "summary")
    content = c.sections
      .map(
        (s) =>
          `<section><h3>${esc(s.heading)}</h3><p class="prose">${esc(s.text)}</p></section>`,
      )
      .join("");
  if (a.kind === "quiz")
    content = c.questions
      .map(
        (q) =>
          `<details><summary>${esc(q.question)}</summary><p class="prose">${esc(q.answer)}\n${esc(q.explanation)}</p></details>`,
      )
      .join("");
  if (a.kind === "concepts")
    content =
      `<label class="check-label"><input type="checkbox" id="hide-relations">관계를 가리고 직접 설명해보기</label>` +
      c.edges
        .map(
          (e) =>
            `<div class="concept-edge"><span class="concept-node">${esc(c.nodes.find((n) => n.id === e.from)?.label)}</span><span class="concept-relation">${esc(e.label)} →<small>${esc(e.condition)}</small></span><span class="concept-node">${esc(c.nodes.find((n) => n.id === e.to)?.label)}</span></div>`,
        )
        .join("");
  modal(
    a.title,
    `<div class="stack">${a.stale ? '<div class="notice">원본이 변경된 이전 노트입니다. 새 노트를 생성하세요.</div>' : ""}${content}<h3>참고한 원문</h3>${sources.map((s) => `<button class="btn small source-link" data-id="${s.segment_id}">원문 · 버전 ${s.revision}</button>`).join("")}<a class="btn" href="/api/artifacts/${id}/export">노트 내보내기</a></div>`,
  );
  $$(".source-link").forEach(
    (b) =>
      (b.onclick = async () => {
        const r = await api("/segments/" + b.dataset.id);
        $("#dialog").close();
        location.hash =
          "/material/" + r.segment.material_id + "/" + r.segment.id;
      }),
  );
  if ($("#hide-relations"))
    $("#hide-relations").onchange = (e) =>
      $$(".concept-relation").forEach(
        (n) => (n.style.visibility = e.target.checked ? "hidden" : "visible"),
      );
}
export async function materialView(id, selected, status, cursor = "") {
  const d = await api(
      "/materials/" + id + "?cursor=" + encodeURIComponent(cursor),
    ),
    m = d.material;
  if (selected && !d.segments.some((s) => s.id === selected)) {
    const chosen = (await api("/segments/" + selected)).segment;
    if (chosen.material_id === id) d.segments.unshift(chosen);
  }
  let page = 1,
    cropMode = false,
    start;
  $("#content").innerHTML =
    `<div class="page-heading"><div><a class="small" href="#/lecture/${m.lecture_id}">← 강의로 돌아가기</a><h1>${esc(m.name)}</h1><p>${badge(m.status)} · 원본과 읽어낸 내용을 함께 확인하세요.</p></div><div class="row"><a class="btn" href="/api/materials/${id}/file" target="_blank" rel="noopener">원본 열기</a><a class="btn" href="/api/materials/${id}/export">전사 내보내기</a><button class="btn danger" id="delete-material">삭제</button></div></div><div class="material-layout"><section class="panel">${m.kind === "pdf" ? `<div class="material-toolbar"><label>페이지<input id="page-number" type="number" min="1" max="${m.page_count || 1000}" value="1"></label><button class="btn" id="page-go">이동</button><button class="btn" id="crop-mode">필기 영역 선택</button></div><p id="crop-hint" class="small">필기 영역 선택을 누르고 글씨가 있는 곳을 드래그하세요.</p><div class="pdf-stage"><div class="source-page" id="source-page"><img id="pdf-image" src="/api/materials/${id}/pages/1" alt="PDF 원본 페이지"><div id="crop-box" class="crop-overlay hidden"></div></div></div>` : m.kind === "audio" ? `<audio id="audio" controls preload="metadata" src="/api/materials/${id}/file"></audio><p class="small">녹취록의 시간 버튼을 누르면 해당 구간으로 이동합니다.</p>` : "<h3>원본 자료</h3><p>텍스트를 추출한 내용입니다. 원본 열기를 통해 비교하세요.</p>"}</section><section><div class="section-heading"><h2>읽어낸 내용</h2><button id="reload-material" class="btn small">새로고침</button></div><div class="segments">${d.segments.map((s) => `<article class="segment-card" id="segment-${s.id}"><div class="row between"><button class="btn small jump" data-id="${s.id}">${s.page ? "p. " + s.page : time(s.start)}${s.bbox ? " · 필기 영역" : ""}</button>${badge(s.state)}</div><p class="prose">${esc(s.text || "아직 읽어낸 내용이 없습니다.")}</p><div class="row wrap"><button class="btn small edit-segment" data-id="${s.id}">확인 · 수정</button>${m.kind === "pdf" ? `<button class="btn small recognize" data-id="${s.id}">${icon("spark")} 확대 판독</button>` : ""}<a class="btn small" href="#/chat/${m.lecture_id}?segment=${s.id}">질문</a></div></article>`).join("") || empty("아직 읽어낸 내용이 없어요", "처리 현황을 확인하거나 잠시 후 새로고침해 주세요.")}</div></section></div>`;
  const paging = document.createElement("div");
  paging.className = "row";
  paging.innerHTML =
    '<button class="btn" id="segments-first">처음 구간</button><button class="btn" id="segments-next">다음 구간</button>';
  $(".segments").after(paging);
  $("#segments-next").disabled = !d.next_cursor;
  $("#segments-first").onclick = () =>
    busy($("#segments-first"), () => materialView(id, null, status));
  $("#segments-next").onclick = () =>
    busy($("#segments-next"), () =>
      materialView(id, null, status, d.next_cursor),
    );
  $("#reload-material").onclick = refresh;
  $("#delete-material").onclick = () => {
    modal(
      "자료 삭제",
      `<p>원본과 전사, 개인 필체 예시를 삭제합니다. 생성한 노트와 대화는 별도 기록으로 남으며, 관련 노트는 원본 변경 상태가 됩니다.</p><button class="btn danger" id="confirm-delete">이 자료 삭제</button>`,
    );
    $("#confirm-delete").onclick = () =>
      busy($("#confirm-delete"), async () => {
        await api("/materials/" + id, { method: "DELETE" });
        $("#dialog").close();
        location.hash = "/lecture/" + m.lecture_id;
      });
  };
  const showPage = (n) => {
    page = n;
    $("#page-number").value = n;
    $("#pdf-image").src = `/api/materials/${id}/pages/${n}`;
  };
  $$(".jump").forEach(
    (b) =>
      (b.onclick = () => {
        const s = d.segments.find((s) => s.id === b.dataset.id);
        if (m.kind === "pdf") showPage(s.page);
        if ($("#audio")) {
          $("#audio").currentTime = s.start;
          $("#audio")
            .play()
            .catch(() => {});
        }
      }),
  );
  $$(".edit-segment").forEach(
    (b) =>
      (b.onclick = () =>
        editSegment(b.dataset.id, status).catch((e) => toast(e.message))),
  );
  $$(".recognize").forEach(
    (b) =>
      (b.onclick = () =>
        busy(b, async () => {
          const r = await api("/segments/" + b.dataset.id + "/recognize", {
            method: "POST",
          });
          await editSegment(b.dataset.id, status, r);
        })),
  );
  if (m.kind === "pdf") {
    $("#page-go").onclick = () =>
      showPage(Math.max(1, Number($("#page-number").value) || 1));
    $("#pdf-image").onerror = () =>
      toast("페이지를 불러올 수 없습니다. 페이지 번호와 PDF를 확인하세요.");
    $("#crop-mode").onclick = () => {
      cropMode = !cropMode;
      $("#crop-hint").textContent = cropMode
        ? "필기 영역을 드래그하세요. 충분히 여백을 포함하면 판독에 도움이 됩니다."
        : "필기 영역 선택을 누르고 글씨가 있는 곳을 드래그하세요.";
    };
    const area = $("#source-page"),
      point = (e) => {
        const r = $("#pdf-image").getBoundingClientRect();
        return [
          Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
          Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
        ];
      };
    area.onpointerdown = (e) => {
      if (!cropMode) return;
      start = point(e);
      area.setPointerCapture(e.pointerId);
    };
    area.onpointermove = (e) => {
      if (!start) return;
      const p = point(e),
        box = $("#crop-box");
      box.classList.remove("hidden");
      Object.assign(box.style, {
        left: Math.min(start[0], p[0]) * 100 + "%",
        top: Math.min(start[1], p[1]) * 100 + "%",
        width: Math.abs(p[0] - start[0]) * 100 + "%",
        height: Math.abs(p[1] - start[1]) * 100 + "%",
      });
    };
    area.onpointerup = async (e) => {
      if (!start) return;
      const p = point(e),
        s = start;
      start = null;
      const bbox = [
        Math.min(s[0], p[0]),
        Math.min(s[1], p[1]),
        Math.abs(s[0] - p[0]),
        Math.abs(s[1] - p[1]),
      ];
      if (bbox[2] < 0.01 || bbox[3] < 0.01) return;
      try {
        const v = await api("/materials/" + id + "/crop", {
          method: "POST",
          body: { page, bbox },
        });
        await materialView(id, v.id, status);
        toast("영역을 저장했습니다. 확대 판독 또는 직접 수정을 선택하세요.");
      } catch (e) {
        toast(e.message);
      }
    };
  }
  if (selected) {
    const s = d.segments.find((s) => s.id === selected);
    if (s?.page && m.kind === "pdf") showPage(s.page);
    $("#segment-" + selected)?.scrollIntoView({ block: "center" });
  }
}
async function editSegment(id, status, recognition) {
  const d = await api("/segments/" + id),
    s = d.segment,
    p = recognition?.proposal;
  modal(
    p ? "판독 제안 확인" : "원문 확인 · 수정",
    `<form id="segment-form" class="stack">${s.page && d.material_kind === "pdf" ? `<img class="source-preview" src="/api/segments/${id}/image" alt="선택한 PDF 원본">` : ""}${p ? `<div class="notice"><strong>문맥에 따른 제안 (자동 적용되지 않음)</strong><p class="prose">${esc(p.contextual_suggestion)}</p><p>불확실한 부분: ${esc((p.uncertain_spans || []).join(", "))}</p><p>${esc(p.explanation)}</p></div>` : ""}<label>읽어낸 원문<textarea name="text" rows="8">${esc(p?.visual_text ?? s.text)}</textarea></label><label>수정 구분<select name="reason"><option value="transcription">원본을 그대로 읽어 수정</option><option value="content_edit">원문의 내용 자체를 편집</option></select></label>${s.bbox && status.personalization ? '<label class="check-label"><input type="checkbox" name="save_example">본인의 손글씨이며 원문을 확인했습니다. 필체 예시로 저장</label>' : ""}<p class="small">원본은 보존됩니다. 수정하면 관련 AI 노트는 재확인 상태로 바뀝니다.</p><button type="submit" class="btn primary">확인하고 저장</button><a class="btn small" id="all-revisions" href="#/collection/revisions?segment_id=${id}">전체 수정 기록</a><details><summary>최근 수정 기록 ${d.revisions.length}개</summary>${d.revisions.map((r) => `<div class="revision"><strong>버전 ${r.number} · ${esc(r.author)}</strong><p class="prose">${esc(r.text)}</p></div>`).join("")}</details></form>`,
  );
  $("#all-revisions").onclick = () => $("#dialog").close();
  bindForm("#segment-form", async (v) => {
    await api("/segments/" + id, {
      method: "PATCH",
      body: {
        ...v,
        revision: recognition?.segment_revision ?? s.revision,
        save_example: !!v.save_example,
        own_handwriting: !!v.save_example,
      },
    });
    $("#dialog").close();
    refresh();
  });
}
