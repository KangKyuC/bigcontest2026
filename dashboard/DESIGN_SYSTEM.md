# 이음 지도 작업 화면

Felt의 지도·선택 상세 배치, Palantir Map의 선택 이후 행동, CARTO의 조건·지표 배치를 참고해 다시 구성함. [조사와 실제 화면](../docs/research/2026-10-25-dashboard-ux-reference-review.md)에 근거를 남김.

기본 화면에서 지도 전체를 사용함.
  - 상단72px에 서비스명·지역·자료 정보를 둠. 지도 위에는 검색과 지원 분류만 표시함.
  - Aceternity Floating Dock의 공식 소스를 적용한 하단 도구에 지도·지원 사업·주민 조건·지역 현황을 명칭과 함께 표시함.
  - 동·장소를 선택하면 닫을 수 있는 오른쪽 창이 열림. 사업을 고르면 같은 창의 사업 안내·판정 근거·조건 변경 탭으로 이어짐.
  - 같은 좌표의 사업은 숫자 핀 하나와 전체 사업 목록으로 묶음. 지도에 없는 방문형·비대면 사업도 지원 사업 목록에서 확인함.
  - 주민 조건은 별도 Dialog에서 편집함. 취소는 반영하지 않고 적용 시 선택 사업·동을 유지함.
  - 데스크톱 비교는 넓어진 오른쪽 창에서 전후를 나란히 표시함. 모바일은 지도 위 하단 창에서 세로로 비교함.

세 층의 토큰을 사용함. 원래 값 → 의미 → 컴포넌트 역할 순서임.

| 층 | 예시 | 연결 |
| --- | --- | --- |
| Primitive | gray-950 #17212b, gray-50 #f7f9fc, blue-600 #216be8, green-700 #00765e | 실제 색상 값 |
| Semantic | text-primary, text-secondary, surface-panel, action-primary, status-review, map-selected | 본문·표면·행동·판정·지도 의미 |
| Component | button-bg, input-border, panel-bg, font-body, radius-panel | 버튼·입력·선택 상세의 일관된 표현 |

판정 상태와 지도 선택 색을 구분함.
  - 파랑은 선택·검색·주요 행동·장소임. 주민의 위험 등급을 뜻하지 않음.
  - 초록은 충족·이용 가능, 빨강은 충돌, 보라는 심사, 갈색은 기관 발굴, 회색은 확인 필요임.
  - 상태는 색과 글자를 함께 표시함. 가상 변경 후에는 사후 보조 분석 문구를 유지함.
  - 지도 경계·선택·장소는 map-boundary·map-selected·map-site 토큰을 사용함.

Pretendard Variable을 로컬로 제공함.
  - 제목22~24px/굵기700, 섹션16px/650, 본문15px/400, 입력14~15px/400~550, 보조13px/400을 사용함.
  - 긴 사업명은 줄바꿈하고 본문 줄 높이는1.7~1.75로 둠. 표·수치는 숫자 폭을 일정하게 유지함.
  - 지도 출처·축척·보조 도구처럼 작은 공간의 정보는10~12px를 사용함.
  - 일반 목록은 선과 여백으로 구분함. 지도 도구·선택 창·모달만 표면과 그림자로 위계를 높임.
  - hover 확대는 작게 제한하고 reduced-motion에서 생략함. 숫자가 바뀌는 동안 잘못된 중간 값처럼 보이던 Number Ticker는 핵심 지표에서 제거함.

요청한 자료의 실제 적용 위치임.

| 자료 | 현재 적용 |
| --- | --- |
| [shadcn](https://ui.shadcn.com/docs/components/command) | 공식 Command의 동·사업 검색, Dialog의 주민 조건, Tabs의 같은 사업 내 작업 전환, Popover의 지도 레이어. Button·Select·Input·Label·Switch·Badge·Tooltip도 공식 소스를 사용함 |
| [Aceternity Floating Dock](https://ui.aceternity.com/components/floating-dock) | 거리·spring 기반 도구 모음을 명칭이 항상 보이는 업무용 버튼으로 조정함. 큰 hover 확대는 줄임 |
| [Magic UI Animated Beam](https://magicui.design/docs/components/animated-beam) | 선택 사업과 같은 분류에 속한 대안의 관계 그림에 적용함. 최초 한 번만 전환하며 실제 이동·실적이 아님을 표시함 |
| [Realtime Colors](https://www.realtimecolors.com/?colors=17212b-f7f9fc-216be8-e9eef5-00765e) | 실제 브라우저에서 해당 조합과 primary #216be8을 확인함. 본문·선택 배경·버튼·상태의11개 대비 조합을 따로 계산해 조정함 |
| [FontShare Satoshi](https://www.fontshare.com/fonts/satoshi) | 실제 스타일 표본의 Regular·Medium·Bold와 크기 선택을 확인함. 최종 UI는 Pretendard로 통일하며 서체 파일을 추가하지 않음 |

본문·상태의11개 조합은 모두 대비4.5:1 이상임.
  - 본문/흰 배경16.29, 보조 본문7.11, 낮은 강조 설명5.49, 버튼 흰 글자4.85임.
  - 충족5.04, 충돌4.61, 심사5.32, 기관 발굴4.79, 확인 필요5.28임.
  - 원래 기관 발굴 색은 배경과4.45여서 #946200으로 조정함.
  - 계산한 값은 [대비 기록](../docs/research/2026-10-26-dashboard-color-contrast.json)에 보관함. 지도 배경 이미지 위의 모든 픽셀 대비를 측정한 것은 아님. 읽는 UI는 불투명하거나 충분히 밝은 표면에 배치함.

배경 지도는 OpenStreetMap을 사용함. 인터넷 연결이 필요하며 원자료의 경계·근사 좌표·정책 판정은 로컬에서 제공함. M3 원본이 없어 위험 지도는 생성하지 않음.
