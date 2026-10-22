# ATLAS AI — 미국 주식 자동 모의투자

기존 SOXL 자동 작업과 **완전히 별도**인 독립형 웹사이트·가상 거래 봇입니다.

## 구성
- `index.html` — 공개 대시보드: 가상 총자산, AI 판단, 종목 보유, 매매내역
- `bot.py` — 미국 정규장 데이터 확인 → OpenAI 판단 → 한도 검증 → 가상 거래 → JSON 장부 저장
- `data/state.json` — 초기 가상 현금 $10,000 및 거래 장부 (GitHub 저장소에 누적)
- `.github/workflows/trading.yml` — 평일 정해진 UTC 시각에 GitHub Actions 실행, 장부 업데이트
- `manual_simulator.html` — 기존 수동 모의투자 버전, 별도 보관

## 실제 인터넷 사이트 활성화 방법
1. 새 GitHub 저장소(권장: 비공개 데이터가 없다면 Public)를 만들고 이 패키지 파일을 **폴더 구조 그대로** 업로드한다. **기존 SOXL 작업은 건드리지 않는다.**
2. Settings → Secrets and variables → Actions → **Repository secrets** 에 `OPENAI_API_KEY`를 등록한다. 키를 HTML 코드나 공개 저장소에 직접 붙여넣으면 안 된다. API 이용 요금은 별도이며 ChatGPT 구독과 별개다.
3. Settings → Actions → General에서 Actions 사용이 가능한지 확인한다. `Actions` → `Atlas AI paper trading` → `Run workflow` 로 시험 실행한다. GitHub Actions 권한으로 커밋이 안 될 경우 Settings → Actions → General → Workflow permissions에서 `Read and write permissions` 허용 (저장소 권한 정책에 따라 다를 수 있음).
4. Settings → Pages → Build and deployment → `Deploy from a branch` → `main` / `/(root)` 설정. 공개 주소 `https://<사용자명>.github.io/<저장소명>/` 로 접속한다.
5. GitHub Actions의 UTC 일정은 미 동부 서머타임에 따라 미국 장중 커버리지가 달라진다. 봇은 뉴욕 현지시각 09:35~16:00, 미국 평일, 시세 최신성 조건을 만족하는 때만 가상 매매한다. GitHub cron은 실행 지연/누락 가능하며 시장 휴장일에는 최신 시세가 부족해 건너뛴다.

## 주의
- **데모가 자동으로 매매를 시작하는 것은 아닙니다.** GitHub 저장소 배포·Actions 켜기·유효한 OpenAI API 키 설정이 완료된 뒤에만 AI 주문 제안이 실행됩니다.
- AI가 25개의 대표 미국 상장 주식/ETF를 대상으로 제공된 시세 데이터만 분석합니다. 미국 모든 상장 종목을 전수 조사하는 것은 아닙니다.
- 거래는 모두 **가상 거래**이며 실제 증권사 주문, 계좌 연결, 자금 이동이 일어나지 않습니다.
- yfinance 비공식 데이터는 지연·오류·누락될 수 있습니다. 매수·매도 체결은 단일 최신 바 가격으로 가정하며 유동성·수수료·세금·슬리피지·배당은 반영하지 않습니다.
- 체결 이력과 평가액은 저장소 `data/state.json`에 기록됩니다. Public 저장소라면 거래 장부도 누구나 볼 수 있습니다.
- 매수 한도: 1회 실행 내 합산 20% 이하, 개별 종목 15% 이하, 현금 최소 30%. 공매도/레버리지/마진 없음. AI 의견과 실제 집행 여부는 다를 수 있습니다.
- 이 예제는 실거래·투자 권유 용도가 아닙니다. 프로덕션에는 테스트, 시장 캘린더, 가격 무결성, 오류 알림, 비용 모니터링 등을 더해야 합니다.
