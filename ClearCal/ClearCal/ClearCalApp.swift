import SwiftUI
import SwiftData

/// 앱 진입점.
///
/// ClearCal("맑은 캘린더")은 일정을 날짜 격자 대신 시간순 아젠다 리스트로
/// 크고 또렷하게 보여주는 데 집중한다. 기기의 기본 캘린더(EventKit)와
/// 앱에서 직접 만든 일정(SwiftData)을 한 화면에 합쳐서 보여준다.
@main
struct ClearCalApp: App {
    /// EventKit 접근과 기기 일정 로딩을 담당.
    @State private var calendarManager = CalendarManager()

    var body: some Scene {
        WindowGroup {
            AgendaView()
                .environment(calendarManager)
                .tint(Theme.accent)
        }
        // 앱 자체 일정 저장소.
        .modelContainer(for: LocalEvent.self)
    }
}
