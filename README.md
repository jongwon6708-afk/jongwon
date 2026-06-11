# ClearCal (맑은 캘린더)

iOS에서 **일정을 더 가독성 좋게** 보여주는 SwiftUI 앱입니다.
날짜 격자(달력 그리드) 대신, 다가오는 일정을 **시간순 아젠다 리스트**로
크고 또렷하게 보여주는 데 집중했습니다.

## 핵심 컨셉

- **아젠다 중심 보기** — 날짜 칸을 일일이 누를 필요 없이, 오늘부터의 일정이
  날짜별 섹션으로 위에서 아래로 쭉 읽힙니다.
- **두 가지 일정을 한 화면에** — 기기 기본 캘린더(EventKit)의 일정을 읽어오고,
  앱에서 직접 추가한 일정(SwiftData)도 함께 합쳐서 보여줍니다.
- **가독성 우선 디자인** — 큼직한 둥근 서체, 충분한 여백, 분류별 색·아이콘 태그,
  Dynamic Type / VoiceOver 대응.

## 화면 구성

| 화면 | 설명 |
|------|------|
| 아젠다 리스트 | 날짜별 섹션 + 일정 카드. 오늘/내일은 라벨로 강조 |
| 일정 추가·수정 | 제목·시간·종일·분류·장소·메모 입력. 앱 자체 일정만 편집 가능 |
| 빈 상태 / 권한 안내 | 캘린더 접근이 없을 때 안내 및 허용 버튼 |

## 프로젝트 구조

```
ClearCal/
├── ClearCal.xcodeproj
└── ClearCal/
    ├── ClearCalApp.swift        # 앱 진입점, SwiftData 컨테이너
    ├── Models/
    │   ├── AgendaEvent.swift     # 기기/앱 일정을 합친 통합 모델
    │   ├── EventCategory.swift   # 분류(색·아이콘) 정의
    │   ├── LocalEvent.swift      # 앱 자체 일정 (SwiftData @Model)
    │   └── DaySection.swift      # 날짜별 그룹핑 로직
    ├── Services/
    │   └── CalendarManager.swift # EventKit 권한·일정 로딩
    ├── Views/
    │   ├── AgendaView.swift      # 메인 화면
    │   ├── EventRow.swift        # 일정 한 줄(카드)
    │   ├── DayHeaderView.swift   # 날짜 섹션 헤더
    │   ├── EmptyStateView.swift  # 빈 상태/권한 안내
    │   └── EventEditView.swift   # 추가·수정 폼
    ├── Theme/
    │   └── Theme.swift           # 폰트·색·간격 등 공통 스타일
    └── Assets.xcassets           # 앱 아이콘, 강조색
```

## 실행 방법

1. **Xcode 15.2 이상**에서 `ClearCal/ClearCal.xcodeproj`를 엽니다.
2. 시뮬레이터 또는 기기(iOS 17+)를 선택하고 ⌘R로 실행합니다.
3. 첫 실행 시 캘린더 접근 권한을 물어봅니다. 허용하면 기기 일정이 함께 보이고,
   허용하지 않아도 `+` 버튼으로 앱 자체 일정을 추가할 수 있습니다.

> 요구 사항: iOS 17.0+ (SwiftData, `@Observable`, EventKit 전체 접근 API 사용)

## 앞으로 더해볼 만한 것

- 분류/캘린더별 필터링 및 검색
- 위젯 / 잠금화면 라이브 액티비티
- 일정 알림(리마인더)과 반복 일정
- 폰트 크기·고대비 등 가독성 옵션 화면
