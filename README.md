# IFPK V45 | 노트북을 끄고도 경제지표를 확인하는 클라우드 자동수집

**정확한 상태: 배포 준비 패키지 · 사용자 클라우드 계정에는 아직 미배포.** 기존 V44를 바탕으로 GitHub Actions(예약 실행), Supabase PostgreSQL(원장·정정 이력), GitHub Pages(공개 사이트)를 연결하도록 만들었습니다. **기존 재무설계 확정 계산값과 구글시트는 자동 변경하지 않습니다.**

## 무엇이 실제로 들어 있나요?

| 기능 | 상태 |
| --- | --- |
| KOSIS 전국 소비자물가지수 API 수집 | ✅ V44 코드 재사용, V45 예약 실행에 연결 |
| GitHub Actions 자동 실행 | ✅ 워크플로 구성. 계정·Secrets·Pages 설정 후 활성화 |
| Supabase PostgreSQL 저장 및 중복 방지 | ✅ SQL/코드 구현. DB 생성·실전 연결 테스트는 필요 |
| 통계 원자료 정정 감사이력 | ✅ PostgreSQL 트리거(실제 저장은 배포 후) |
| GitHub Pages 공개 사이트 자동 갱신 | ✅ GitHub Actions 배포 워크플로 구성. 배포 전 화면은 샘플 |
| 전국 CPI 원자료 34개월 미리보기 | ✅ 사용자가 이전에 공식 API로 저장한 2024-01~2026-10 자료로 구성, 미배포로 명시 |
| 다른 지표(자동차·여행·예적금·주담대) | ⚠️ V44에 검증 전 자리표시자만 보존, 활성화하지 않음 |
| 기관별 공식 발표일 캘린더 | ⏳ 추후 구현. 현재 매일 2회 API 재조회로 발표 시점 차이를 흡수 |
| 6개월 재무계획 전체 재계산·고객 승인 | ⏳ 별도 V46+ 개발. 수집했다고 승인 계획을 바꾸지 않음 |

## 실행 구조

```text
KOSIS (공식 전국 CPI) ---> GitHub Actions (매일 KST 12:17·23:17에 조회)
                                   |
                                   v
                         Supabase PostgreSQL 원장
                       (지표월별 upsert + 수정이력)
                                   |
                                   v
                        공개 지표 JSON 스냅샷
                                   |
                                   v
                         GitHub Pages 웹사이트
                                   |
                                   v
                        고객은 현재 확정 계획 조회
                      (구글시트 연 2.5% 계산값 유지)
```

**예약 실행은 정확한 시각을 보장하지 않습니다.** GitHub Actions `schedule`은 지연되거나 간혹 생략될 수 있고, 장기간 저장소 비활동 시 실행이 비활성화될 수 있습니다. 운영 중 `Actions` 기록과 사이트의 마지막 배포 시각을 점검해야 합니다. 노트북은 꺼도 됩니다.

## 따라하기 — 배포 순서 (Windows 포함)

### 1. GitHub와 Supabase 가입

- GitHub: https://github.com 계정 만들기.
- Supabase: https://supabase.com/dashboard 계정/새 프로젝트 만들기. 무료 요금제 이용 가능 여부와 한도는 실제 대시보드에서 확인하세요.
- Supabase의 **Project Settings → API Keys**에서 `Project URL`과 **Secret API key (`sb_secret_...`)** 확인하기. 비밀키는 **절대 채팅으로 보내지 말고, GitHub Secrets에만** 등록하세요. `sb_publishable_...`는 DB 쓰기용이 아닙니다.

### 2. Supabase SQL 실행

- Supabase 프로젝트 → **SQL Editor** → New query → `supabase/setup.sql` 전체 내용 붙여넣기 → Run.
- 테이블 `ifpk_observations`, `ifpk_revisions`, `ifpk_collection_runs` 생성 확인.
- RLS 활성화, anon/authenticated 권한 차단, 수정값 트리거 설치.
- 실제 고객 이름, 소득, 자산, 계좌번호 등 민감정보는 여기에 입력하지 마세요. **현재 공개 사이트는 가상 사례용**입니다.

### 3. GitHub 저장소에 패키지 업로드

- GitHub에서 새 저장소 `ifpk-v45-cloud` 만들기 (공개 사이트를 만들 경우 해당 저장소 내용도 공개될 수 있으므로 **가상 고객 데이터만** 사용).
- 이 압축 파일 안의 내용을 **압축 없이 저장소 루트**에 업로드하기. `.github/workflows/ifpk-cloud-refresh.yml` 파일이 **숨김 폴더 `.github`를 포함해** 정확히 올라가야 합니다.
- 저장소의 기본 브랜치 이름이 `main`인지 확인하기. 다르면 `.github/workflows/ifpk-cloud-refresh.yml`의 `branches: [main]` 수정하기.

### 4. GitHub Secrets 등록 (가장 중요)

저장소 → **Settings → Secrets and variables → Actions → New repository secret**에서 다음 이름을 정확히 등록해 주세요.

| 이름 | 넣는 값 | 노출 금지 |
| --- | --- | --- |
| `KOSIS_API_KEY` | 네가 이미 발급받아 V44에서 사용한 키 | 🔒 |
| `SUPABASE_URL` | `https://프로젝트ID.supabase.co` | URL 자체는 공개 가능 |
| `SUPABASE_SECRET_KEY` | Supabase의 `sb_secret_...` 키 | 🔒 최중요 |
| `ECOS_API_KEY` | *현재는 비워도 됨.* 미래에 ECOS 계열 활성화 시 추가 | 🔒 |

> **기존 로컬 `secrets.env`를 GitHub 저장소에 업로드하지 마세요.** 키는 Secrets 설정 화면에만 입력하세요. 사진을 찍을 때도 키가 보이지 않게 해주세요.

### 5. GitHub Pages 설정 후 처음 실행

- 저장소 → **Settings → Pages → Build and deployment → Source: GitHub Actions** 선택.
- 저장소 → **Actions** 탭 → `IFPK V45 economic indicators cloud refresh and Pages deploy` → **Run workflow** 누르기.
- 실행 결과가 녹색이면 Jobs의 **Deploy to GitHub Pages** 단계에 배포 주소가 표시됩니다. 사이트에 `#data`를 붙여 **경제지표·설계 갱신** 탭 열기.
- 첫 성공 실행 시 SQLite 미리보기 34개월은 Supabase에 자동 복사되는 방식이 아니라 **KOSIS API가 2024년 1월 이후 지표를 다시 수집해 DB에 저장**합니다.
- 같은 날짜/통계월 데이터가 이미 DB에 있으면 중복 입력하지 않습니다. KOSIS에서 통계가 정정되면 기존값과 새값을 DB 트리거 이력에 남깁니다.
- 해당 Pages 주소는 **공개 접근 가능한 정적 사이트**입니다. 현재 가상 고객의 생활·자산 모델 외 실제 개인 재무정보를 넣으면 안 됩니다.

### 6. 이후 운영

- 워크플로는 **매일 KST 12:17 / 23:17을 목표로** 새 데이터를 확인합니다. 한국시간은 서울 UTC+9 기준이며, 실제 GitHub 실행 시각은 지연될 수 있습니다.
- KOSIS의 실제 자료 공표는 매월, 일정은 변동 가능 → 매일 재조회하여 새로운 통계월이 등록된 시점에 기록합니다. 이후 개별 공식 발표 캘린더를 붙일 수 있습니다.
- 각 성공 작업은 공개 JSON을 재생성·사이트를 다시 배포합니다. 사이트의 **관측 기준월, 수집 시각, 배포 시각**은 서로 다른 정보입니다.
- GitHub Action은 **코드가 돌았다고 공식 고객 계획을 변경하지 않습니다.** 정기 재설계 시 고객 실적 확인 및 승인 절차가 별도로 필요합니다.

## 파일 위치

- `docs/index.html` — V45 웹사이트 (원래 V44의 계산 모델을 변경하지 않았음)
- `docs/data/public_indicators.json` — **사전 미리보기** CPI 34개월 공개자료 (최초 실제 클라우드 수집 성공 시 새 값으로 교체되어 배포)
- `docs/data/status.json` — 배포 전 `"published": false` 명시
- `collector/ifpk_collector.py` — V44 공식 KOSIS/ECOS 파서 재사용
- `collector/cloud_runner.py` — 클라우드 DB 저장 + 공개 스냅샷 갱신
- `supabase/setup.sql` — PostgreSQL 테이블/RLS/수정 트리거
- `.github/workflows/ifpk-cloud-refresh.yml` — 예약실행 + 수집 + GitHub Pages 배포
- `tests/test_cloud_runner.py` — 네트워크 없이 실행 가능한 단위 테스트
- `collector/ecos_series.json` — ECOS 계열은 안전하게 비활성화된 상태

## 로컬 미리보기 (클라우드 계정 없이 테스트 가능)

터미널에서 패키지 폴더를 열고 아래 명령 실행:

```bash
python -m unittest discover -s tests -v
python -m http.server 8766 --directory docs
```

브라우저에서 `http://127.0.0.1:8766/#data` 접속. **상태는 ‘사전 데이터 샘플 · 클라우드 미배포’**로 나옵니다. 이건 실제 클라우드 연동 성공이 아닙니다.

## 필수 검증 기준

1. `Actions`에서 수집/DB 저장/Pages 배포 3개 단계가 모두 성공했는지.
2. `Supabase → Table Editor → ifpk_observations`에 KOSIS CPI 34개월 이상, 최신 통계월/수치가 저장됐는지.
3. `Supabase → ifpk_collection_runs`에 최근 성공 로그가 있는지.
4. 웹사이트의 **‘경제지표·설계 갱신’** 탭에 `published: true`인 실제 클라우드 상태가 표시되는지.
5. Pages의 공개 JSON에 Secret 키가 전혀 없는지.
6. 같은 워크플로를 재실행했을 때 동일 관측월 데이터가 중복되지 않는지.
7. 재무계획 확정값이 원본 통합 구글시트의 **미래 물가 연 2.5% 가정**을 그대로 유지하는지.

## 참고 공식 문서

- GitHub Actions 예약 작업: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Pages 사용자 워크플로: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Supabase API 및 보안: https://supabase.com/docs/guides/api , https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase 신규 Secret 키: https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys
- KOSIS API: https://kosis.kr/openapi/

**배포 상태는 아직 ‘사용자 계정 미연결’이며, V45 사이트에 포함된 34개월은 사용자가 로컬에서 수집한 검증 자료를 바탕으로 한 미리보기입니다.** 이번 작업으로 확인된 것은 코드·단위 테스트·오프라인 화면까지입니다. 실제 클라우드 수집 성공은 사용자가 계정을 연결하고 `Actions` 실행 결과를 확인해야 확정할 수 있습니다.
