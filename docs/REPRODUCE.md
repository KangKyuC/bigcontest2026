# M3 재현 안내

## 복원 범위와 환경

2026-10-22 M3의 전처리·모델 선택·평가·추론을 복원합니다. 2026-10-25에 원 연구를 유지한 채 `repro/m3/`에 실행 경로를 정리한 사본을 만들었습니다. 통계 설정·변수·후보·시드·평가 방식은 유지했습니다.

원본 8개와 이 저장소만 있으면 이전 DuckDB·공간 중간 CSV·특정 PC 경로 없이 재집계할 수 있습니다. 원자료가 없으면 코드 시험과 보존 결과 열람까지만 가능합니다.

Windows·CPython 3.9를 실제 검증에 사용했습니다. 통계 핵심은 `requirements.txt`, 보고서까지 만들려면 `requirements-report.txt`를 설치합니다.

검증에 사용한 전이 의존성까지 고정한 전체 목록은 [requirements-lock-py39.txt](../requirements-lock-py39.txt)입니다. 같은 Python 3.9 환경을 복원하려면 이 파일을 설치할 수 있습니다.

PowerShell:

```powershell
py -3.9 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -r requirements-report.txt
```

macOS/Linux:

```bash
python3.9 -m venv .venv
.venv/bin/python -m pip install -r requirements-report.txt
```

아래의 `python`은 설치한 가상환경 실행 파일을 뜻합니다. PowerShell에서는 `& ./.venv/Scripts/python.exe`, macOS/Linux에서는 `.venv/bin/python`으로 바꿔 실행할 수 있습니다. 가상환경 활성화는 필수가 아닙니다.

## 원본 파일 배치

```text
data/raw/
├── public/
│   ├── seoul_citizen_202510.xlsx
│   └── seoul_citizen_202512.xlsx
└── contest/
    ├── sk/
    │   ├── flow_age_pop_202507.csv
    │   ├── flow_age_pop_202508.csv
    │   ├── flow_age_pop_202509.csv
    │   ├── flow_age_pop_202510.csv
    │   ├── flow_age_pop_202511.csv
    │   └── flow_age_pop_202512.csv
    └── card/                     # 선택 EDA에서만 사용
        └── 신한카드_빅콘테스트2026_데이터2.txt  # 또는 검증된 UTF-8 CSV 한 개
```

SK의 구분자는 `|`입니다. 공식 대회 경로에서 권한을 가지고 확보한 성·연령별 유동 파일을 배치합니다. 크기·SHA-256은 [출처 명세](../data/sources.json)에 있습니다.

서울 공개 원본 2개는 다음 명령으로 내려받습니다. POST 인자·원본 지문을 고정했고, 2026-10-25에 실제 서버에서 새 다운로드를 확인했습니다.

```bash
python repro/m3/fetch_public.py
python repro/m3/verify_sources.py
```

다른 경로를 사용하면 두 명령과 실행기에 `--data-root /path/to/raw`를 지정합니다. 그 아래의 `public/`, `contest/sk/` 구조는 같습니다. 공개 파일이 바뀌거나 HTML 오류가 반환되면 저장 전에 실패하며, 기존의 다른 지문 파일을 자동 덮어쓰지 않습니다.

## 전체 모델 재현

```bash
python repro/run.py
```

| 단계 | 코드 | 생성 결과 |
| --- | --- | --- |
| `prepare` | `prepare_data.py`, `spatial_frame.py` | 원본 공통점·연령 표준화·두 창 440셀·품질 검사 |
| `train` | `train_evaluate.py`, `m3lib.py` | 후보 비교·중첩 평가·안정성·모델·220셀 프로필·인계 |
| `diagnostics` | `additional_diagnostics.py` | 사후 공간 4·6블록 민감도·잔차 공간진단 |
| `validate` | `validate_model.py` | 실제 데이터 25개 검증 |
| `compare` | `compare_reference.py` | 보존 수치와 23개 항목 대조·220셀 추론 |

시드 `20261022`, 내부 5-fold, 동 부트스트랩 200회, 고정 OOF 오차 구간 재표집 10,000회를 사용합니다. 각 단계는 새 Python 프로세스에서 실행합니다.

부분 실행과 보고서 생성:

```bash
python repro/run.py --stages train,diagnostics,validate,compare
python repro/run.py --stages report
```

보고서 의존성이 설치되어 있어야 합니다. 한글 그림은 맑은 고딕·Noto Sans CJK KR·나눔고딕 중 설치된 글꼴을 사용합니다. Linux에서 한글 글꼴이 없으면 모델은 동작해도 그림 문자가 깨질 수 있으므로 글꼴을 설치합니다. 저장소의 PNG는 Windows에서 렌더링한 결과입니다.

## 생성 파일

아래 경로는 모두 `repro/m3/` 기준이며 Git에서 제외됩니다.

| 경로 | 내용 |
| --- | --- |
| `data/model_input_primary.csv` | 주 입력 220셀 |
| `data/model_input_sensitivity.csv` | 중첩 관측창 220셀 |
| `data/reference_non_gangnam.csv` | 두 창의 서울 402동 비교기준 |
| `data/input_checks.json` | 재현 전처리 49개 검사 |
| `models/m3_bundle.joblib` | 선택 모델·전처리 |
| `models/m3_parameters.json` | 보고서 단계에서 저장하는 파라미터 JSON |
| `results/group_profiles.csv` | 전체 220셀 특성·비교위치·품질 |
| `results/policy_handoff.json` | 관측·미확인 정책 조건을 분리한 인계 |
| `results/reference_comparison.json` | 보존 결과와 수치 대조 |
| `report/` | Markdown·Word·Excel·PDF·PNG |

재실행은 생성 경로의 이전 결과를 갱신합니다. 새 설정·자료를 시험하려면 저장소 사본을 사용합니다. `results/m3_20261022/`의 원 연구 기준을 새 결과로 바꾸지 않습니다.

## 별도 추론

```bash
python repro/m3/predict.py --input repro/m3/data/model_input_primary.csv --output repro/m3/results/predictions.csv
```

`--model`로 다른 로컬 모델을 지정할 수 있습니다. 입력은 일반 원본이 아니라 전처리를 마친 입력표입니다. 미지원 지역·연령, 중복, 결측, 기간 불일치, 품질 기준 초과는 거절합니다. 미채택 `published_type`과 단일 성분의 `membership_probability`는 비웁니다. 신뢰하는 파일만 `joblib`으로 읽습니다.

## 선택: 24집단 활동 EDA

카드 데이터2와 SK로 강남·춘천의 24집단·6개월을 서술 비교합니다. 카드1·TXT 복사본을 추가 합산하지 않습니다.

```bash
python repro/m3/analyze_activity.py
```

다른 카드 경로는 `--card-file /path/to/data2.txt` 또는 CSV로 지정합니다. 공식 원 TXT는 CP949·탭 구분자로 직접 읽고, 연구에 사용한 변환 CSV는 UTF-8·쉼표로 읽습니다. 두 파일 모두 명세의 SHA-256으로 확인하며, 어느 하나만 분석합니다. 기본 위치에 CSV가 없으면 TXT를 찾습니다. 별도 CSV 변환 도구나 두 형식의 합산은 필요하지 않습니다.

`results/activity_monthly.csv` 144행과 `activity_contrasts.csv` 24행을 만듭니다. 7~8월 62일 대비 11~12월 61일의 제공 결제 건수/일·일평균 유동을 비교합니다. SK는 완전히 동일한 중복 행만 제거하고 점별 값이 충돌하면 실패합니다.

전체 24집단의 결과를 저장소의 고정 서술 비교표와 절대허용오차 `1e-6`으로 대조합니다. 대표 세 사례만 맞는지 보는 검사는 아닙니다.

범위는 업종별 원 변화·전체 집단의 서술 비교입니다. 예전 기상·공휴일 보정 회귀, 시설/식료품 상대 모형의 신뢰구간, 정책 프로토타입 전체를 복원하는 명령은 아닙니다. 보고서 전에 실행하면 강남 카드 맥락이 별도 시트에 들어갑니다. 선택 EDA의 실행 여부는 M3 모델 결과를 바꾸지 않습니다.

## 검증 종류

| 명령·단계 | 데이터 | 의미 |
| --- | --- | --- |
| `python -m unittest discover -s tests -v` | 명시적 합성 입력 | 10개 코드 계약 시험 |
| `prepare_data.py` | 원본 8개 | 49개 입력 검사 |
| `validate_model.py` | 실제 입력·모델·평가 출력 | 25개 분할·저장·추론 검사 |
| `compare_reference.py` | 실제 재실행 결과 | 23개 수치 대조, 절대허용오차 `1e-6` |

코드 검사와 수치 복원은 고립 실제 정답·정책 수요·지원 효과의 검증을 대신하지 않습니다. 머신별 소수점 차이를 고려해 실행시간·시각·전체 파일 바이트의 일치까지 요구하지 않습니다. 선택 모델이나 주요 성능이 달라지면 원본 지문·환경·분할부터 확인합니다.

## 원 구현에서 변경한 부분

- 고정 Windows 경로를 저장소 상대 경로와 `--data-root`로 바꿨습니다.
- 공간 중간표 대신 원본 6개에서 공통점을 재구성합니다. 공공 코드 대응표를 포함했습니다.
- 과거 중간표 비교는 역사적 감사 기록으로 분리하고 현재 입력·관측창은 새로 검사합니다. 원 실행의 입력 검사 50개와 공개 재현판 49개는 완전히 같은 검사 목록이 아닙니다.
- 보고서가 README·의존성 설정을 덮어쓰지 않도록 하고, 카드 맥락을 선택 분석으로 분리했습니다.
- 재현 실행기·고정 수치 대조·계약 시험을 추가했습니다. 통계 핵심 설정은 결과에 맞춰 바꾸지 않았습니다.

원 파일 지문은 [source_provenance.json](../repro/m3/source_provenance.json)에 있습니다. 원 연구 폴더는 로컬에 보존했습니다.
