# 이음 대시보드 (사회적 고립 지원 연결 에이전트)

공개 화면: https://ieum-pink-psi.vercel.app

지자체 담당자용 화면임. 동 × 성별 × 나이대 집계 신호로 가상 페르소나를 만들고, 강남 37개·춘천 17개 지원사업의 신청 조건과 한 명씩 대조해 단계(1~4)·할 일·정책 추천을 보여 줌.
- 페르소나는 모두 가상 인물임. 숫자는 실제 주민 수나 고립된 사람 수가 아님
- 단계는 정해 둔 규칙의 출력임(학습된 개인 고립 확률이 아님). 같은 입력이면 늘 같은 결과가 나옴

## 폴더

| 경로 | 내용 |
| --- | --- |
| `src/agent/` | 화면 (React · Leaflet). `AgentApp.tsx` 브리핑·목록, `AgentMap.tsx` 지도, `PersonaPanel.tsx` 인물 분석 창, `PolicyPanel.tsx` 정책 추천 상세 |
| `public/data/` | 화면이 읽는 결과 3개(`agent.json`, `personas.json`, `policy.json`). 서버 없이 이 파일만 읽음 |
| `pipeline/` | 결과 3개를 만드는 파이썬 (아래) |

## 화면 실행

```sh
npm --prefix dashboard ci
npm --prefix dashboard run dev      # http://127.0.0.1:5173
npm --prefix dashboard run build    # dashboard/dist
```

`public/data/`에 결과가 들어 있어서 파이썬 없이 바로 열림.

## 결과를 다시 만드는 순서 (`pipeline/`)

| 순서 | 파일 | 하는 일 |
| --- | --- | --- |
| 1 | `run_dong_personas.py` | 동 × 성별 × 나이대 집단 중 연락·외출(M3 서울 동년배 백분위)·주말 사람 흐름(SK, 평일 유입 보정)이 하위 20%인 곳을 페르소나로 고름. 연락 상위 20%는 뺌 |
| 2 | `policy_gap_engine.py` | 사업 조건(나이·가구·소득·대상·신청 방법·운영 시간·지역·모집 기간)과 페르소나 조건을 하나씩 대조 |
| 3 | `run_persona_recommend.py` | 같은 분야 안에서 맞는 방식 → 지역 안 시설 → 시간 → 신청 경로 순으로 사업 순위 |
| 4 | `dashboard_agent.py` | 단계 판정·할 일·판단 기록. 신호 강함(개인 신호가 하위 5%, 또는 하위 20% 둘 이상, 연락 상위 20% 아님) × 지원 공백 유무 → 1~4단계. 동 전체 값(주말 사람 흐름)만으로는 강함이 되지 않음 |
| 5 | `dashboard_policy.py` | 조건 하나 바꾸기·새 사업·공고 보완 추천 |
| 6 | `export_dashboard_static.py` | 위 결과를 `public/data/`에 씀 (`dashboard_server.py`의 자료 읽기를 씀) |

```sh
python dashboard/pipeline/run_dong_personas.py
python dashboard/pipeline/export_dashboard_static.py
python -m pytest dashboard/pipeline/tests
```

**이 저장소만으로는 다시 만들 수 없음.** 파이썬은 원래 작업 폴더 루트에서 돌던 코드를 그대로 옮긴 것이고, 다음 입력을 로컬에서 읽음. 저장소의 [데이터 공개 범위](../docs/DATA_POLICY.md)에 따라 넣지 않음.
- `data/policy/personas/m3_group_profiles.csv` (M3 220셀 결합 입력), `sk_weekend_by_dong.csv` (SK 집계) — 대회 자료에서 만든 입력
- `data/policy/` 아래 사업 조건표·출처·운영 장소, `data/reference/` 행정동 경계, `data/external/` 동 인구
  - 사업 조건표는 공개 공고를 조사해 만든 자료임. 공개 여부는 팀이 정하면 추가함

## 배포

`pipeline/deploy_dashboard.sh`: 결과 생성 → 빌드 → Vercel 배포 → 공개 사이트 자료가 로컬과 같은지 확인. Vercel 로그인은 각자 함(`npx vercel login`).

## 알려진 한계

- 화면의 "연락·외출 예측" 표기: 실제 값은 M3 관측 백분위(`contact_seoul_peer_percentile` 등)임. 발표자료와 맞추려고 발표 뒤 "연락·외출 집계"로 고칠 예정
- 춘천은 서울 통신 자료가 없어 신호가 주말 사람 흐름 하나뿐 → 모두 3단계. 교동(한림대)·효자2동(강원대)은 대학가 영향일 수 있음
- 동별 페르소나는 모두 혼자 산다고 가정함. 가족과 산다고 바꾸면 닫히는 분야는 주거·안전뿐임(강남 36·춘천 6 조합)
- "60세 미만은 평일 낮에 못 감" 가정: 강남 결론은 가정과 무관, 춘천 "저녁·주말 회차 → 29명"은 일하는 사람 기준
