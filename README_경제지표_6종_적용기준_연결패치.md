# IFPK · V59 경제지표 적용기준·현금흐름 연결 보완 패치

## 적용 범위

**이번 패치는 고객실적의 Supabase 저장이나 기기 간 동기화를 구현하지 않습니다.** 현재 브라우저 로컬 저장키와 경제지표 수집기·GitHub Actions·원장 JSON 생성 기능을 변경하지 않습니다.

1. **전체요약 남색 영역**: 조회월, 공식 지표별 적용 기준월, 사용 여부, 5개 비용 구성요소(일반생활비/양육비/주담대/차량할부/별도 보험·건보료)와 기준 가정 대비 지표 영향 금액을 보여줍니다. 과거월에는 실적이 보존되고 최신 지표가 소급 변경되지 않음을 표시합니다.
2. **경제지표·설계갱신 탭**: 6개 지표(일반 CPI, 자동차 MA3, 여행 MA12, 세후 예금 60개월 금리, 신규 주담대 5·10년 혼합금리, R-ONE 지역 아파트가격지수 5·10년 CAGR)의 검증 기준월과 실제 사용 상태를 모두 표시합니다. 기존 변경 항목 목록과 별도로 전체 지표 상태를 볼 수 있습니다.
3. **R-ONE 연결**: 새 `HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606`와 기존 `HOME_PRICE_APT_DAEJEON_SEOGU` 계열을 각각 식별하고, 검증된 5·10년 CAGR만 선택합니다. 기준이 다른 시계열을 이어 붙이지 않습니다. 신규 기준에서 필요한 과거 관측기간이 부족하면 유효한 기존 계열 또는 최초 설계 가정으로 대체합니다.
4. **경제지표별 민감도 및 계산 확인**: 검증자료가 실제 반영되었을 때 지표 한 종류만 기준 가정으로 되돌린 반사실 시뮬레이션과 비교합니다. 일반소비·양육비, 차량할부, 여행목표, 목적저축 수익률, 신규 주담대, 주택이사 자기자금의 연결을 별도로 검증합니다.

## 실제 자동 연동의 범위

- 현금흐름에 연결된 부분은 기존 V55 엔진과 같은 계산 경로를 사용합니다.
- 보험·건보료의 최신 제도·요율 자동 계산, 주담대 LTV/DSR 한도 전체 재산정, 주택 매각대금 원장 전면 재작성, 국민연금 재추정, 승인 계획 자동 반영은 **여전히 미구현**입니다.
- 기존 V59의 월별 실적과 4대 목표 배정·순필요저축 준비율은 변경하지 않았습니다.
- 경제지표가 아직 발표되지 않았거나 정합성 검사를 통과하지 못하면 **해당 지표의 마지막 검증값 또는 최초 가정**을 유지합니다.
- **과거 확정 저축실적은 최신 지표 때문에 자동 수정되지 않습니다.** 미래의 예상치만 조건부로 갱신됩니다.

## 수동 배포

1. ZIP 압축을 풀고 기존 `enormbase/ifpk-v45-cloud` GitHub 저장소의 **동일 폴더 경로**에 업로드합니다.
2. 변경되는 파일은 `docs/index.html`, `docs/js/v55_savings_ui.js`, `docs/js/v55_savings_engine.js`, `docs/js/v59_economic_adapter.js`입니다.
3. 새로 생성되는 파일은 `docs/js/v60_indicator_trace.js`, `tests/run_v60_tests.js`, `tests/test_v60_indicator_trace.py`입니다.
4. `.github/workflows/`, `collector/`, Supabase, 기존 `docs/data/` 원장 파일은 건드리지 마세요.
5. 커밋 메시지 예시: `feat: show six indicator vintages and audit monthly cashflow`
6. GitHub Actions 초록색 체크를 확인한 뒤 공개 사이트에서 강력 새로고침(`Ctrl+Shift+R`)하세요.

## 검증 결과

- `node tests/run_v55_tests.js`, `node tests/run_v57_tests.js`, `node tests/run_v59_tests.js`, `node tests/run_v59_net_progress_tests.js`, `node tests/run_v60_tests.js` 통과.
- 관련 Python 테스트 19개와 6개 subtest 통과.
- Chromium PC(1440px), 모바일(390px)에서 남색 상세·6개 지표 카드·지표별 독립 계산 결과가 표시되고 JS 오류 없이 동작하는 것 확인.
- 이 브라우저 검증에는 6개 **가상 검증값**을 주입했습니다. 공개 사이트의 최신 실제 지표 수치·Supabase 적재 상태는 이 환경에서 직접 조회하지 못했습니다. 배포 후 실제 공개 원장 `docs/data/status.json`, `docs/data/public_indicators.json` 갱신 여부와 기준월을 확인해야 합니다.
- 로컬에 최신 `collector/`가 없어 GitHub 저장소의 모든 Python 89개 테스트를 이 환경에서 동일 조건으로 실행하지는 못했습니다. 최종 배포 성공 여부는 GitHub Actions에서 확인해 주세요.

## HTML 단독 미리보기

단독 HTML은 실제 GitHub Pages 공개지표 파일을 자동으로 읽을 수 없으므로 기본 가정 기준 화면으로 표시됩니다. 브라우저별 저장기록도 공개 GitHub Pages 사이트와 공유되지 않습니다.
