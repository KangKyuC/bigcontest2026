# 2026-10-22 고정 결과

원 연구의 통계 수치를 보존한 비교 기준입니다. 새 실행 결과는 이 폴더를 덮어쓰지 않고 `repro/m3/results/`에 저장합니다.

| 파일 | 내용 |
| --- | --- |
| `summary.json` | 선택 모형·안정성·SK 개선량 구간·보조 예측 성능·유형 미채택 |
| `candidate_cv.csv` | 같은 특성 공간의 동 그룹 5-fold 보류 점수 |
| `candidate_fit_diagnostics.csv` | 보조 BIC·silhouette·적합 진단 |
| `contact_prediction_metrics.csv` | 고립이 아닌 통화대상자 지수의 MAE·RMSE·R² |
| `sensitivity.csv` | 변수·연령 보정·품질·관측창 대체 결과 |
| `additional_diagnostics.json` | 결과를 본 뒤 추가한 공간 4·6블록 및 잔차 진단 |
| `activity_contrasts.csv` | 기존 전체 24집단의 7~8월 대비 11~12월 서술 변화 |

실행시간은 당시 환경의 기록이며 재현 성능 기준이 아닙니다. 단일 성분의 안정성 ARI는 `null`입니다. 예측 성능과 분포 밀도를 사회적 고립 위험 예측 정확도로 해석하지 않습니다.
