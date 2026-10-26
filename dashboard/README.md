# 이음 대시보드 (사회적 고립 지원 연결 에이전트)

공개 화면: https://ieum-pink-psi.vercel.app

지자체 담당자용 정책 검토 화면입니다. 동 × 성별 × 나이대 집계 신호로 가상 페르소나를 만들고, 강남 37개·춘천 17개 지원사업의 신청 조건과 대조해 검토 단계(1~4)·할 일·정책 추천을 보여 줍니다. 공개 스냅샷에는 대표 사례 5개와 동별 사례 70개가 있습니다.
- 페르소나는 모두 가상 인물임. 숫자는 실제 주민 수나 고립된 사람 수가 아님
- 단계는 정해 둔 규칙의 출력임(학습된 개인 고립 확률이 아님). 같은 입력이면 늘 같은 결과가 나옴

## 폴더

| 경로 | 내용 |
| --- | --- |
| `src/agent/` | 화면 (React · Leaflet). `AgentApp.tsx` 브리핑·목록, `AgentMap.tsx` 지도, `PersonaPanel.tsx` 인물 분석 창, `PolicyPanel.tsx` 정책 추천 상세 |
| `public/data/` | 화면이 읽는 결과 3개(`agent.json`, `personas.json`, `policy.json`). 서버 없이 이 파일만 읽음 |
| `pipeline/` | 결과 3개를 만드는 파이썬 (아래) |

## 화면 실행

Node.js 24 이상과 npm이 필요합니다. 명령은 저장소 루트에서 실행합니다.

```sh
npm --prefix dashboard ci --ignore-scripts
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
python -m pytest -q -m "not local_data"
```

**화면 실행은 공개 저장소만으로 가능하지만, 스냅샷 전체 재생성에는 별도 입력이 필요합니다.** Python 3.11 환경에 `requirements-dev.txt`를 설치합니다. 파이프라인의 데이터 기본 위치는 저장소의 `data/`이며, `IEUM_DATA_ROOT` 환경변수로 다른 데이터 폴더를 지정할 수 있습니다. 작업 디렉터리와 무관하게 같은 경로를 사용합니다. 다음 입력은 [데이터 공개 범위](../docs/DATA_POLICY.md)에 따라 포함하지 않았습니다.
- `data/policy/personas/m3_group_profiles.csv` (M3 220셀 결합 입력), `sk_weekend_by_dong.csv` (SK 집계) — 대회 자료에서 만든 입력
- `data/policy/` 아래 사업 조건표·출처·운영 장소, `data/reference/` 행정동 경계, `data/external/` 동 인구
  - 사업 조건표는 공개 공고를 조사해 만든 자료임. 공개 여부는 팀이 정하면 추가함

공개 시험은 합성 정책 조건·검토 규칙·스냅샷 정합성·로컬 서버 보안을 확인합니다. `local_data` 표시가 붙은 6개 통합 시험은 정책 입력이 있을 때만 실행합니다. 공개 화면을 보는 데 이 통합 시험이나 Python 서버는 필요하지 않습니다. 원자료 없는 시험을 전체 정책 분석 재현으로 설명하지 않습니다.

공개 스냅샷의 출처와 파일 SHA-256은 [snapshot-manifest.json](snapshot-manifest.json)에 있습니다. 스냅샷을 의도적으로 갱신했으면 저장소 루트에서 `python scripts/update_snapshot_manifest.py`를 실행합니다.

## 배포

Vercel에서 프로젝트 루트를 `dashboard/`로 설정하면 `vercel.json`의 Vite 빌드와 보안 헤더를 사용합니다. 공개 저장소에는 배포 토큰·조직 ID·프로젝트 ID를 저장하지 않습니다.

기존 프로젝트에 수동 배포할 때는 `pipeline/deploy_dashboard.sh`를 사용합니다. 로컬에 설치한 Vercel CLI에 로그인하고 `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_CLI`를 환경변수로 지정합니다. 기본적으로 공개 스냅샷을 빌드하며, 원본으로 다시 생성하려면 `REBUILD_DATA=1`과 필요한 입력을 준비합니다. 배포 후 원격 화면과 세 JSON의 해시를 확인해야 합니다.

선택적인 `dashboard_server.py`는 원자료를 가진 로컬 분석용이며 `127.0.0.1`에만 바인딩합니다. 허용된 Host·동일 출처·JSON 크기를 검사합니다. 인터넷 공개 서버로 사용하지 않습니다.

## 알려진 한계

- 연락·외출은 M3 입력의 관측 백분위입니다. 화면과 스냅샷은 이를 "연락·외출 집계"로 표시하며, 학습 모델의 개인 위험 예측값으로 해석하지 않습니다.
- 춘천은 서울 통신 자료가 없어 신호가 주말 사람 흐름 하나뿐 → 모두 3단계. 교동(한림대)·효자2동(강원대)은 대학가 영향일 수 있음
- 동별 페르소나는 모두 혼자 산다고 가정함. 가족과 산다고 바꾸면 닫히는 분야는 주거·안전뿐임(강남 36·춘천 6 조합)
- "60세 미만은 평일 낮에 못 감" 가정: 강남 결론은 가정과 무관, 춘천 "저녁·주말 회차 → 29명"은 일하는 사람 기준
- 정책 조건은 조사 시점의 스냅샷이며, 현재 모집 여부·정원·예외·선정 가능성은 운영기관 확인이 필요합니다. 조건 대조 결과는 행정기관의 실제 자격 판정이나 고립 감소 효과를 보장하지 않습니다.
