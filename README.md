# StudyMate AI

강의자료 · 필기 PDF · 녹음을 연결하고, 원문 확인에서 질문과 간격 복습까지 이어가는 학습 웹앱입니다. Goodnotes 같은 필기 앱에서 내보낸 PDF를 가져오며 자체 필기 편집기는 만들지 않습니다.

**현재 상태: 로컬 실행 가능한 개발 버전.** 계정·자료·수정 이력·복습은 실제 DB에 저장됩니다. OpenAI API 키가 없으면 AI 결과를 만들어내지 않고 설정 필요 상태를 표시합니다. 외부 API의 실제 인식 품질과 공개 배포는 아직 검증되지 않았습니다.

## 시작하기

Python 3.12 이상을 권장합니다. 프로젝트 루트에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\scripts\start-local.ps1
```

브라우저에서 <http://127.0.0.1:5000>에 접속해 계정을 만듭니다. PowerShell 스크립트 실행이 제한된 환경에서는 터미널 두 개에서 각각 아래를 실행하세요.

```powershell
# 터미널 1: 웹 서버
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 app:app
# 터미널 2: 자료 처리 작업자
.\.venv\Scripts\python.exe -m flask --app app worker
```

macOS/Linux에서는 `.venv/bin/python`을 사용합니다. 웹 서버만 실행하면 자료 처리 작업은 대기합니다. 기본 DB와 업로드 파일은 `instance/`에 보관되며 Git에서 제외됩니다.

체험 자료를 원하면 **로컬 개발 환경에서만** `python scripts/seed-demo.py`를 실행합니다. `demo@studymate.test / local-demo-only-2026` 계정과 수동 작성한 체험 카드가 생성됩니다. 운영 DB에서는 사용하지 마세요. 기본 설치가 자동으로 체험 계정을 만들지는 않습니다.

## 사용 흐름

1. 내 과목 → 강의 추가 → 주제·단원·소주제를 입력합니다.
2. PDF/PPTX/DOCX/TXT를 먼저 업로드합니다. 자료 처리 완료 후 전문용어와 발음·연관어를 확인합니다.
3. 강의 녹음 파일을 올립니다. 4MB 조각 업로드와 구간별 처리 기록으로 업로드·처리를 이어갑니다.
4. PDF의 작은 손글씨 영역을 선택해 원본에서 크게 렌더링합니다. AI 판독 제안과 문맥 제안을 구분해서 확인·수정합니다.
5. 요약·핵심 포인트, 개념 관계도, 인출 카드를 생성하거나 직접 카드를 만듭니다.
6. 강의 자료를 근거로 챗봇에게 질문하고 출처로 이동합니다. 정답을 보기 전 회상한 뒤 자가 평가로 다음 복습 간격을 정합니다.

## 구현된 기능과 범위

| 영역 | 현재 동작 |
|---|---|
| 계정·과목·강의 | 비밀번호 해시, 세션, CSRF, 사용자별 자료 접근 검사 |
| 자료 수집 | PDF/PPTX/DOCX/TXT/MD, 지원 음성 파일; 최대 512MB, PDF 1,000쪽, TXT 10MB |
| 업로드 | 4MB 조각, 서버 상태 조회, 같은 파일 재선택 시 전송 재개, 내용 형식 검증 |
| 추출·수정 | PDF 페이지·PPT 슬라이드별 텍스트, 불가독 페이지 표시, 수정 버전 보존, 충돌 감지 |
| 작은 필기 판독 | 원본 PDF 영역 렌더링, 이미지 API 판독, 문맥 후보 분리, 직접 확인 후 저장 |
| 필체 개인화 | 동의한 사용자의 최근 확인 예시 최대 3개 참조; 신경망 재학습은 아님 |
| 긴 녹음 | FFmpeg로 5분씩 분할, 2초 경계 중첩, 최대 12시간, 절대 시간표시, 구간 재시도 |
| 받아쓰기 맥락 | 강의 주제·확인된 전문용어/발음/연관어·관련 자료 발췌를 사전 참고 |
| AI 노트 | 구간별 요약과 핵심 포인트, 3/5/7문장 요청, 한/영, 1~20개 수량 설정 |
| 개념 관계도 | 개념–관계–개념, 성립 조건, 원문 출처; 관계 가리고 설명하기 |
| 질문 | 자료 근거 / 일반 지식 구분 / 힌트 모드, 선택 영역 질문, 출처 링크 |
| 복습 | 객관식 서버 채점·결과 점수, 자유 응답 자가 평가, 확신도·힌트 기록, 간격 조절, 오답 노트·재복습, 오류 카드 보류 |
| 기록 관리 | 자료 검색, 원본 다운로드, 전사 텍스트·노트·전체 학습 기록 내보내기, 자료·필체 예시 삭제 |
| 개발·운영 | 기능별 API 모듈, 독립 서비스 계층, Alembic 마이그레이션, SQLite/PostgreSQL, 작업자, Docker Compose, CI |

## 직접 준비할 것

- **OpenAI 계정/API 키와 결제 설정**: `.env`의 `OPENAI_API_KEY`에 입력합니다. ChatGPT 앱 구독과 서버 API 사용 설정은 별도로 확인하세요. 키는 브라우저·채팅·GitHub에 넣지 않습니다.
- **모델 사용 권한**: `OPENAI_MODEL`은 텍스트/이미지를 지원하는 Responses 모델 ID입니다. 예시는 `gpt-6-astra`; 사용 가능한 모델을 계정에서 확인하세요. 시간표시 받아쓰기 어댑터는 `whisper-1`을 지원합니다.
- **FFmpeg**: 긴 녹음 처리를 위해 `ffmpeg`와 `ffprobe`가 PATH에 있어야 합니다. Docker 이미지에는 포함됩니다. Windows용 프로젝트 내부 설치는 `python scripts/install-ffmpeg.py`로 실행할 수 있습니다.
- **공개 서비스 운영 계정/도메인**: 원하는 서버를 준비한 후 [배포 안내](docs/DEPLOYMENT.md)를 따릅니다. 현재 저장소를 GitHub Pages에 올리는 것만으로 Python 서버가 실행되지는 않습니다.

## 한계와 후속 개발

이 버전의 개인화는 확인 예시 참조와 규칙 기반 복습입니다. **필체 모델 파인튜닝, 개인 망각곡선 학습, 생성 문항의 정답 타당도, 수 시간 실녹음의 인식 품질을 검증 완료한 제품이 아닙니다.** 긴 녹음의 분할·재개 제어는 테스트하며, 실제 API 품질 검증은 키와 허가된 음성 표본이 필요합니다.

Whisper의 짧은 프롬프트 한도 때문에 사전 자료 전체를 음성 모델에 입력하지 않습니다. 주제·용어·자료의 짧은 힌트를 사용합니다. 추가 자료를 업로드해도 기존 완료 전사는 자동 변경하지 않습니다. 수정된 전사로 새 노트를 만들 수 있습니다.

브라우저 녹음은 메모리에 보관하므로 창 종료·기기 절전에서 복구되지 않습니다. 긴 강의는 별도 녹음 앱으로 저장한 파일을 업로드하세요. `.ppt`와 `.hwp`는 PDF/PPTX로 변환해야 합니다. 검색은 현재 어휘 기반이며 의미 검색은 후속 확장 지점입니다. 이메일 인증·비밀번호 재설정·기관 SSO는 미구현입니다.

## 문서와 개발

- [세부 기획 및 요구사항 대응표](docs/PRODUCT_SPEC.md)
- [구조·DB·재시도와 확장 지점](docs/ARCHITECTURE.md)
- [설정·배포·백업·복구](docs/DEPLOYMENT.md)
- [검증 범위와 남은 검증](docs/VALIDATION.md)
- [직접 검수 체크리스트](docs/ACCEPTANCE.md)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m flask --app app db check
```

기존 버전은 `legacy/`에 보존했습니다. 새 앱은 `sm_` 테이블을 별도 DB에 생성하며 기존 DB를 자동 변환하거나 덮어쓰지 않습니다. 기존 OAuth·공유 화면은 활성 앱에 연결되지 않습니다.


## 대규모 데이터 저장 기반

목록 커서 페이지네이션, 사용자·상위 자료별 복합 인덱스, PostgreSQL `SKIP LOCKED` 작업 분배,
구간별 생성 스냅샷, 원자적 업로드 용량 예약, 스트리밍 내보내기, 백업·복원 확인 도구를 제공합니다.
현재 테이블은 19개이며, 로컬 원본 저장소를 사용합니다. 대규모 운영 서버 자체나 실제 사용자 데이터는 포함하지 않습니다.

- [운영·확장 절차](docs/DATABASE_OPERATIONS.md)
- [100만 합성 구간 측정 결과](docs/validation/million-segments.json)

```sh
flask --app app db upgrade
flask --app app db-report
# PostgreSQL 전용, 인덱스 설치 권한이 있는 운영자가 실행
flask --app app search-index
# 운영 DB와 무관한 새로운 로컬 테스트 폴더에만 합성 데이터 생성
python scripts/benchmark-database.py --rows 1000000 --output test-results/my-scale-run
```
