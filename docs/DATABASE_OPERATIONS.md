# 대규모 데이터 축적을 위한 구현과 운영

## 현재 제공하는 것

운영용 PostgreSQL을 연결할 수 있는 코드와 재현 가능한 검증 도구입니다. 클라우드 서버를 개설하거나 실제 사용자 학습 데이터를 대량 수집한 상태는 아닙니다. 로컬의 100만 구간 DB는 명시적으로 표시된 합성 데이터이며 앱의 실제 계정 DB와 분리되어 있습니다.

| 영역 | 구현 | 한계 |
|---|---|---|
| 목록 | 기본 50, 최대 100개, `(created_at,id)` keyset 커서 | 총 페이지 수 대신 다음 커서 제공, 신규 데이터는 처음부터 새로 조회 |
| 커서 보안 | 사용자·테이블·필터·정렬을 서명에 결합, 24시간 만료 | 커서는 암호화가 아니며 클라이언트가 내용을 신뢰해서는 안 됨 |
| 화면 | 전체 과목·강의·자료·용어·이력 화면, 검색·원문 다음 페이지 | 홈과 강의 개요는 최근 50개 미리보기 |
| 인덱스 | 소유자/상위 자료/시간/ID, 복습 기한, 작업 선점 | 인덱스는 저장 공간과 쓰기 비용을 사용함 |
| 검색 | DB에서 조건 검색, pg_trgm GIN 선택 설치 | 한국어 형태소 분석·벡터 의미 검색은 아님. 짧거나 흔한 검색어는 느릴 수 있음 |
| 생성 작업 | JobBatch마다 원문 스냅샷과 완료 상태, 결과와 완료 표시 원자적 저장 | 외부 API 과금의 exactly-once 보장은 없음 |
| 작업자 | PostgreSQL `FOR UPDATE SKIP LOCKED`, SQLite CAS 대안 | DB 큐이며 기관별 공정 배분·작업 우선순위는 미구현 |
| 용량 | 사용자별 원본 사용량+대기 예약을 조건부 UPDATE로 제한 | DB 텍스트·스냅샷·임시 파일의 물리적 디스크 사용량까지 제한하지 않음 |
| 내보내기 | JSON/전사를 100행씩 스트리밍 | 동시 편집 중 전체 테이블의 한 시점 스냅샷은 아님. DB 백업과 구분 |
| 운영 | 백업 체크섬·별도 복원, 만료 업로드 정리, 완료 스냅샷 정리, 상태 집계 | 백업 보관 주기·암호화·외부 저장소·복구 목표는 운영자가 구성 |

자료는 19개 관계형 테이블에 저장합니다. 원본 바이너리는 DB에 넣지 않고 `DATA_DIR/files`에 보관하며, DB에는 저장 키·크기·해시를 저장합니다. 호스트가 여러 대가 되면 공유 영구 저장소 또는 객체 저장소 어댑터가 필요합니다. 현재 코드는 S3 지원을 구현했다고 주장하지 않습니다.

## PostgreSQL 적용

1. `.env`의 `DATABASE_URL`을 준비합니다. 빈 DB를 연결해 `flask --app app db upgrade`를 실행합니다. SQLite 데이터를 PostgreSQL로 자동 이전하는 기능은 없습니다. 기존 데이터 이전은 별도 검증된 ETL과 원본 복사가 필요합니다.
2. 기존 배포 업데이트는 웹·작업자를 중지하고 DB와 파일을 백업한 후 마이그레이션합니다. 이번 스키마 마이그레이션은 일반 인덱스 생성과 용량 합계 backfill을 포함하므로 **무중단 마이그레이션으로 간주하지 않습니다.** 대형 기존 DB에 적용하기 전에 복제 환경에서 소요 시간과 잠금을 측정하세요.
3. 기존 원본과 `pending/assembling` 업로드에서 사용량·예약을 계산합니다. 이전 pending 업로드는 마이그레이션 시점으로부터 24시간의 만료 시간을 받습니다.
4. `flask --app app db check`로 스키마 일치를 확인합니다. `flask --app app search-index`는 별도 실행합니다. 이 명령은 pg_trgm 확장 및 GIN 인덱스를 설치하고 ANALYZE합니다. 인덱스는 `CONCURRENTLY`로 만들며, 이전 중단으로 invalid 인덱스가 남았으면 다시 생성합니다. 확장 설치 권한이 없다면 DBA가 설치해야 합니다.
5. 웹·작업자를 시작하고 `/api/ready`를 확인합니다. `/api/health`는 프로세스 생존, `/api/ready`는 DB 연결 확인용입니다. 실제 스키마 버전 검증은 배포 마이그레이션 검사를 사용합니다.

연결 설정은 프로세스별입니다. 기본 `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5`, `DB_POOL_TIMEOUT=10`입니다. 웹 프로세스 4개와 작업자 4개라면 최대 80개 연결에 관리·마이그레이션 여유가 필요합니다. 처음에는 더 작은 풀로 시작해 연결 대기·DB CPU·작업 지연을 측정합니다. statement timeout 30초, lock timeout 5초, idle transaction timeout 10분을 설정합니다. 인덱스 설치 명령은 해당 연결에서 statement timeout을 해제합니다. 대규모 최초 마이그레이션은 별도 운영 엔진 설정을 사용해 제한 시간을 조정해야 할 수 있습니다.

Compose의 DB 계정은 초기 개발용 단일 계정입니다. 실제 운영에서는 마이그레이션/DDL 계정과 최소 권한 앱 계정을 분리하세요. API의 소유권 검사는 구현되어 있지만 모든 부모-자식 관계에 소유자 복합 FK 또는 PostgreSQL RLS가 적용된 것은 아닙니다. 관리자 SQL과 ETL은 이 경계를 우회할 수 있으므로 별도 검증이 필요합니다.

## 용량 예약과 정리

`STORAGE_LIMIT_BYTES` 기본값은 사용자당 10GiB입니다. 업로드 시작 시 선언한 파일 크기를 예약합니다. 동시 요청도 `used + reserved + requested <= limit` 조건을 한 번의 DB UPDATE로 확인합니다. 완료 시 예약에서 사용량으로 이동하고, 취소/만료 시 예약을 반환하며, 자료 삭제 시 사용량을 줄입니다. 파일당 512MB 제한은 별도입니다.

```sh
flask --app app db-report
flask --app app expire-uploads
flask --app app expire-uploads --apply --batch-size 100
flask --app app prune-job-snapshots --days 30
flask --app app prune-job-snapshots --days 30 --apply --batch-size 100
```

정리 명령은 실행당 한 배치만 처리합니다. `--apply` 없는 실행은 읽기 전용입니다. 만료 대상은 pending 업로드만이며, 조립 중인 업로드를 시간만으로 취소하지 않습니다. 프로세스가 조립 중 죽었다면 웹·작업자를 멈추고 DB 상태/원본/임시 파일을 확인하는 운영 복구가 필요합니다. 파일 삭제와 DB 커밋은 하나의 트랜잭션이 아니므로 커밋 후 파일 삭제 실패나 조립 도중 장애로 고아 파일이 남을 수 있습니다. 디스크 공간 경보를 별도로 설정해야 합니다.

스냅샷 정리는 완료된 작업의 JobBatch만 지우며 생성 노트·출처·사용자 원문은 유지합니다. 실패·대기 작업의 재시도용 스냅샷은 보존합니다. 실행 주기는 호스팅 환경의 스케줄러에서 구성하며, 이 작업은 실제 서버의 정리 일정까지 등록하지 않습니다.

## 백업과 복원 확인

원본 파일과 DB의 일관성이 필요하면 쓰기를 중지한 뒤 같은 시점에 보관합니다. 비밀 키는 별도 비밀 저장소로 관리합니다. 아래 도구는 **DB만** 백업합니다.

```sh
python scripts/backup-database.py --output backups/2026-10-12
# SQLite: 존재하지 않는 새 파일에만 복원
python scripts/verify-backup.py --backup backups/2026-10-12 --sqlite-output backups/2026-10-12/restored.sqlite3
```

PostgreSQL은 같은 서버 메이저 버전 이상인 `pg_dump` 및 `pg_restore` 클라이언트가 PATH에 있어야 합니다. 연결 비밀번호는 프로세스 환경에 전달하며 명령 인자나 출력에 넣지 않습니다. SSL 설정은 DB URL의 `sslmode/sslrootcert/sslcert/sslkey`를 전달합니다. DB 백업에는 민감한 학습 데이터와 비밀번호 해시가 포함되므로 접근 제한·암호화·보관 기한을 설정하고 Git에 올리지 않습니다.

PostgreSQL 복원 확인은 운영 DB와 다른 **빈** DB를 만들고 `RESTORE_DATABASE_URL`로 지정합니다. 이 DB 이름은 `_restore_check`로 끝나야 합니다. `verify-backup.py --backup ...`는 체크섬을 검증하고 원자적 restore 후 테이블별 행 수를 출력합니다. 기존 데이터가 있는 대상에는 복원하지 않습니다. 사용자 자료의 정합성까지 보장하려면 원본 해시와 실제 기능을 추가 확인합니다. 관리형 PostgreSQL의 PITR/WAL 복구와 장애 조치는 별도 구성입니다.

## 검증과 용량 계획

합성 데이터 10개 사용자, 원문 구간 1,000,000행을 독립 SQLite DB에 저장했습니다. 약 799MiB이며 2,000행 단위 삽입 중 tracemalloc이 측정한 Python 최대 할당은 약 1.81MiB였습니다. 이는 전체 프로세스 RSS나 DB 캐시 크기가 아닙니다. [원시 결과](validation/million-segments.json)에 환경 범위와 조회 계획을 기록했습니다.

첫 페이지, 깊은 keyset 페이지, 깊은 OFFSET 비교를 각각 30회 수행했습니다. 로컬 warm-cache 단일 프로세스의 SELECT 시간일 뿐 HTTP 응답 시간이나 PostgreSQL 동시 부하의 보장이 아닙니다. 실제 사용자 데이터·AI 품질·최대 수용 인원을 나타내지 않습니다. PostgreSQL CI는 별도로 잠긴 작업 건너뛰기, 동시 용량 예약, 20,000행 pg_trgm 실행계획, 스키마 업그레이드, 백업 복원을 검증합니다.

사용자 수만으로 서버 용량을 결정하지 않습니다. 평균 원본 크기 × 업로드 수, 분당 전사 구간 수, 수정 이력 보존 기간, 생성 결과/스냅샷 배수, 인덱스와 WAL·백업 공간을 각각 산정하세요. 검증되지 않은 예상 사용자를 수용 가능 인원으로 표시하지 않습니다.

다음 확장은 실제 부하에 맞춰 선택합니다: 객체 저장소, 연결 풀 프록시, 집계 캐시, 전용 검색/벡터 인덱스, 시간별 이력 파티셔닝과 보관 정책, DB tenant 제약, 장애 복구 훈련. 무조건 샤딩하거나 초기부터 파티션을 만드는 대신 실제 느린 쿼리·락·디스크 지표로 판단합니다.

근거: [PostgreSQL pg_trgm](https://www.postgresql.org/docs/17/pgtrgm.html), [SKIP LOCKED](https://www.postgresql.org/docs/17/sql-select.html), [SQLAlchemy 대량 결과 스트리밍](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#fetching-large-result-sets-with-yield-per).


대량 적재 직후에는 GIN pending list가 검색 비용을 높일 수 있습니다. PostgreSQL 검증 스크립트는 정리 전·후 실행계획과 `gin_clean_pending_list`가 정리한 페이지 수를 함께 기록합니다. 운영에서는 autovacuum/autoanalyze 상태를 관찰하고 적재 뒤 `VACUUM (ANALYZE)` 등의 유지 관리를 계획하세요. 플래너가 항상 같은 인덱스를 선택하는 것은 아니므로 설치·유효성·정확한 검색 결과와 실제 플랜을 구분합니다. [공식 GIN 구현 설명](https://www.postgresql.org/docs/17/gin-implementation.html).
