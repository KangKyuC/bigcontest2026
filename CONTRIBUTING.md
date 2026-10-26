# 변경과 검증

변경 목적과 실제 동작을 설명하는 Pull Request를 작성합니다. 통계 설정이나 결과를 변경할 때는 기존 기준 수치를 덮어쓰지 말고 새 실행의 입력 지문·설정·검증 근거를 함께 남깁니다.

Python 3.11 환경의 공개 검사:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q -m "not local_data"
python scripts/check_public_release.py
```

Node.js 24 이상의 대시보드 검사:

```sh
npm --prefix dashboard ci --ignore-scripts
npm --prefix dashboard audit --audit-level=low
npm --prefix dashboard run build
```

원자료·전체 행별 결합 입력·모델 바이너리·정책 조사 원본·인증정보는 커밋하지 않습니다. 필요한 생성 경로는 `.gitignore`와 [데이터 정책](docs/DATA_POLICY.md)을 따릅니다. 스냅샷을 변경할 때는 `python scripts/update_snapshot_manifest.py`로 파일 지문을 갱신합니다.

지원사업 조건·페르소나 가정·관측값·학습 결과를 구분하고, 실제 주민 수나 개인 고립 확률로 바꾸어 서술하지 않습니다. 라이브러리와 글꼴의 기존 이용조건 및 [제3자 고지](dashboard/THIRD_PARTY_NOTICES.md)를 보존합니다.
