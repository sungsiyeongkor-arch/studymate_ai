import { api } from "../lib/api.js";
import {
  $,
  $$,
  esc,
  icon,
  empty,
  toast,
  busy,
  modal,
  date,
} from "../lib/ui.js";
import { bindForm, refresh } from "../app.js";
export async function reviewView() {
  const d = await api("/reviews/due");
  let index = 0;
  const render = () => {
    const item = d.items[index];
    if (!item) {
      $("#content").innerHTML =
        `<div class="page-heading"><div><span class="eyebrow">TODAY’S RECALL</span><h1>오늘의 복습</h1></div></div>${empty(index ? "이번 복습을 마쳤어요" : "지금 복습할 카드가 없어요", "강의의 학습 노트 탭에서 AI 문제를 생성하거나 직접 카드를 만들어보세요.", '<a class="btn primary" href="#/library">내 과목으로</a>')}<p class="small">한 번에 최대 30개의 예정 카드를 표시합니다. 더 있다면 새로고침하세요.</p>`;
      return;
    }
    const { card: c, state: s } = item;
    let hint = false,
      revealed = false;
    $("#content").innerHTML =
      `<div class="page-heading"><div><span class="eyebrow">RETRIEVAL PRACTICE</span><h1>먼저 떠올려보세요.</h1><p>읽고 이해한 것과 스스로 설명할 수 있는 것은 달라요.</p></div><span>${index + 1} / ${d.items.length}</span></div><section class="panel review-panel-main"><span class="badge">${esc(c.concept || "인출 연습")}</span><h2 class="review-question">${esc(c.question)}</h2><label>내 답변<textarea id="review-answer" placeholder="기억나는 대로 설명해보세요. 틀려도 괜찮아요."></textarea></label><label>정답을 보기 전 확신 정도<select id="confidence"><option value="0">잘 모르겠어요</option><option value="1" selected>어느 정도 알아요</option><option value="2">확실히 알아요</option></select></label><div class="row wrap"><button class="btn" id="hint">생각할 단서</button><button class="btn primary" id="reveal">정답과 비교하기</button><button class="btn text" id="report">문제 오류 신고</button></div><div id="hint-text"></div><div id="answer-section"></div></section><p class="small review-panel-main">자가 평가로 복습 간격을 조절합니다. 힌트를 쓴 복습은 간격을 짧게 유지합니다. 아직 개인의 망각곡선을 학습한 모델은 아닙니다.</p>`;
    $("#hint").onclick = () => {
      hint = true;
      $("#hint-text").innerHTML =
        `<div class="notice info">${c.concept ? `‘${esc(c.concept)}’의 정의, 성립 조건, 예시를 하나씩 떠올려보세요.` : "질문의 핵심 개념을 정의한 뒤, 강의에서 본 예시와 연결해보세요."}</div>`;
    };
    $("#reveal").onclick = () => {
      if (revealed) return;
      revealed = true;
      $("#confidence").disabled = true;
      $("#answer-section").innerHTML =
        `<div class="answer-box"><h3>정답 · 해설</h3><p class="prose">${esc(c.answer)}\n\n${esc(c.explanation)}</p></div><p>얼마나 스스로 떠올렸나요?</p><div class="grade-buttons">${["다시 학습", "어려웠어요", "기억했어요", "쉽게 설명해요"].map((t, i) => `<button class="btn grade" data-grade="${i}">${t}</button>`).join("")}</div>`;
      const requestKey = crypto.randomUUID();
      $$(".grade").forEach(
        (b) =>
          (b.onclick = () =>
            busy(b, async () => {
              $$(".grade").forEach((x) => (x.disabled = true));
              try {
                const r = await api("/cards/" + c.id + "/review", {
                  method: "POST",
                  body: {
                    request_key: requestKey,
                    state_version: s.version,
                    grade: Number(b.dataset.grade),
                    confidence: Number($("#confidence").value),
                    hint_used: hint,
                    answer: $("#review-answer").value,
                  },
                });
                toast("복습 저장 · 다음 예정 " + date(r.next_due));
                index++;
                render();
              } catch (e) {
                $$(".grade").forEach((x) => (x.disabled = false));
                throw e;
              }
            })),
      );
    };
    $("#report").onclick = () => {
      modal(
        "문제 오류 신고",
        `<p>이 문제의 복습을 중단하고 기존 평가를 통계에서 제외합니다. 강의자료를 확인한 후 새 문제를 만들어 주세요.</p><button class="btn danger" id="confirm-report">오류로 보류</button>`,
      );
      $("#confirm-report").onclick = () =>
        busy($("#confirm-report"), async () => {
          await api("/cards/" + c.id + "/report", { method: "POST" });
          $("#dialog").close();
          index++;
          render();
        });
    };
  };
  render();
}
export async function chatView(raw, status) {
  const [id, query] = raw.split("?"),
    selected = new URLSearchParams(query || "").get("segment");
  const [d, history] = await Promise.all([
    api("/lectures/" + id),
    api("/lectures/" + id + "/chat"),
  ]);
  $("#content").innerHTML =
    `<div class="page-heading"><div><a class="small" href="#/lecture/${id}">← ${esc(d.lecture.title)}</a><h1>이해가 될 때까지, 질문하세요.</h1><p>답변의 근거를 직접 확인하며 공부하세요.</p></div></div><div class="chat-layout"><aside class="panel chat-aside"><h3>질문의 범위</h3><p class="small">현재 강의의 자료와 녹취록에서 관련 내용을 찾습니다. 전체 자료를 모두 읽은 답변이 아닐 수 있습니다.</p><div class="notice info">${selected ? "선택한 원문 영역을 우선 참고합니다." : "정의 → 조건 → 예시 순서로 질문해보세요."}</div><p class="small">${status.ai_ready ? "AI 연결 설정 있음" : "서버에 API 키를 설정하면 대화할 수 있어요."}</p></aside><section class="panel"><div id="chat-history" class="chat-history"></div><form id="chat-form" class="stack"><label>답변 방식<select name="mode"><option value="sources">자료 근거만 사용</option><option value="background">자료 + 일반 지식 (구분해서 표시)</option><option value="hint">정답 대신 학습 힌트</option></select></label><div class="chat-compose"><textarea name="question" required placeholder="예: 이 개념이 앞 단원의 내용과 어떻게 연결돼?"></textarea><button class="btn primary" type="submit">보내기 ${icon("arrow")}</button></div></form></section></div>`;
  const draw = (items) => {
    $("#chat-history").innerHTML =
      items
        .map(
          (c) =>
            `<div class="bubble ${esc(c.role)}">${esc(c.text)}${(c.sources || []).map((s) => `<a class="source-button" href="#/material/${s.material_id}/${s.id}">${s.page ? "p. " + s.page : "원문"} · v${s.revision}</a>`).join("")}</div>`,
        )
        .join("") ||
      empty(
        "어떤 부분이 궁금한가요?",
        "자료의 개념이나 조건, 예시를 물어보세요.",
      );
    $("#chat-history").scrollTop = $("#chat-history").scrollHeight;
  };
  let items = history.items || [];
  draw(items);
  bindForm("#chat-form", async (v) => {
    const a = await api("/lectures/" + id + "/chat", {
      method: "POST",
      body: { ...v, segment_id: selected },
    });
    items.push({ role: "user", text: v.question }, a);
    draw(items);
    $("#chat-form textarea").value = "";
  });
}
export async function settingsView(status) {
  const d = await api("/settings");
  $("#content").innerHTML =
    `<div class="page-heading"><div><span class="eyebrow">YOUR PREFERENCES</span><h1>설정</h1><p>내 자료와 AI 사용 방식을 관리하세요.</p></div></div><div class="lecture-grid"><section class="stack"><div class="panel stack"><h2>필체 개인화</h2><label class="check-label"><input id="personalization" type="checkbox" ${d.user.personalization ? "checked" : ""}>확인한 내 필기 예시를 다음 판독에 참고</label><p class="small">본인의 손글씨 영역과 직접 확인한 원문만 예시로 저장합니다. 활성화하면 최근 예시 최대 3개를 판독 요청과 함께 AI 제공자에게 전송합니다. 모델 자체를 재학습하지 않으며 정확도 향상을 보장하지 않습니다. 끄면 이후 요청에서 예시 사용이 중단됩니다.</p><h3>저장한 필체 예시 · ${d.examples.length}</h3>${d.examples.map((e) => `<div class="list-row"><p>${esc(e.text.slice(0, 120))}</p><button class="btn small delete-example" data-id="${e.id}">삭제</button></div>`).join("") || '<p class="small">PDF 필기 영역을 원문대로 수정한 뒤 예시로 저장할 수 있어요.</p>'}</div><div class="panel stack"><h2>복습 방식</h2><p>${esc(status.scheduler)}</p><p class="small">정답 여부에 대한 자가 평가·힌트 사용·복습 이력으로 다음 간격을 정합니다. 개인 망각곡선 적합과 검증은 후속 개발 범위입니다.</p></div><div class="panel"><h2>내 기록 내보내기</h2><p class="small">자료 원본은 각 자료 화면에서, 계정의 텍스트 기록은 아래에서 내려받을 수 있습니다.</p><a class="btn" href="/api/account/export">학습 기록 JSON 다운로드</a></div></section><aside class="stack"><div class="panel stack"><h2>AI 연결 상태</h2><p>${status.ai_ready ? "API 키 설정됨" : "API 키 설정 필요"}</p><p class="small">텍스트·이미지: ${esc(status.model)}<br>장시간 음성 도구: ${status.audio_ready ? "준비됨" : "FFmpeg 설치 필요"}<br>계정당 하루 API 요청 한도: ${status.daily_limit}회</p><div class="notice">운영자가 서버의 .env에 OPENAI_API_KEY를 설정하고 앱과 작업자를 재시작해야 합니다. API 키를 채팅이나 GitHub에 올리지 마세요.</div><p class="small">실제 모델 사용 권한은 API 계정에 따라 다릅니다. 모델 ID는 서버 설정으로 바꿀 수 있습니다. 처리할 자료·녹음은 기능 요청 시 외부 AI API로 전달됩니다.</p></div><div class="panel"><h2>최근 API 사용</h2>${d.usage.map((u) => `<div class="list-row"><div><strong>${esc(u.operation)}</strong><small>${esc(u.model)} · ${date(u.created_at)}</small></div></div>`).join("") || '<p class="small">아직 API 사용 기록이 없습니다.</p>'}<p class="small">이 화면의 호출 기록은 청구 금액과 다를 수 있습니다. 제공자 대시보드에서 비용을 확인하세요.</p></div></aside></div>`;
  $("#personalization").onchange = async (e) => {
    try {
      await api("/settings", {
        method: "PATCH",
        body: { personalization: e.target.checked },
      });
      toast("설정을 저장했습니다.");
    } catch (err) {
      e.target.checked = !e.target.checked;
      toast(err.message);
    }
  };
  $$(".delete-example").forEach(
    (b) =>
      (b.onclick = () =>
        busy(b, async () => {
          await api("/handwriting-examples/" + b.dataset.id, {
            method: "DELETE",
          });
          refresh();
        })),
  );
}
