import Foundation
import EventKit
import Observation

/// 기기 기본 캘린더(EventKit) 접근 권한과 일정 로딩을 담당.
///
/// 앱 자체 일정(`LocalEvent`)은 SwiftData의 `@Query`로 뷰에서 직접 읽고,
/// 이 매니저는 읽기 전용인 기기 일정만 책임진다. 둘은 뷰에서 합쳐진다.
@Observable
final class CalendarManager {
    private let store = EKEventStore()

    /// 현재 권한 상태. 뷰에서 안내 배너를 띄울지 판단하는 데 쓴다.
    var authorizationStatus: EKAuthorizationStatus = EKEventStore.authorizationStatus(for: .event)

    /// 로드된 기기 일정들(통합 모델로 변환된 상태).
    var deviceEvents: [AgendaEvent] = []

    /// 앞으로 며칠치 일정을 불러올지.
    var daysAhead: Int = 60

    var hasAccess: Bool {
        switch authorizationStatus {
        case .fullAccess, .authorized:
            return true
        default:
            return false
        }
    }

    /// 권한 요청 후 허용되면 일정을 로드한다.
    @MainActor
    func requestAccessAndLoad() async {
        do {
            let granted: Bool
            if #available(iOS 17.0, *) {
                granted = try await store.requestFullAccessToEvents()
            } else {
                granted = try await store.requestAccess(to: .event)
            }
            authorizationStatus = EKEventStore.authorizationStatus(for: .event)
            if granted {
                loadDeviceEvents()
            }
        } catch {
            authorizationStatus = EKEventStore.authorizationStatus(for: .event)
            deviceEvents = []
        }
    }

    /// 오늘부터 `daysAhead`일치 기기 일정을 다시 로드한다.
    func loadDeviceEvents() {
        guard hasAccess else {
            deviceEvents = []
            return
        }
        let cal = Calendar.current
        let start = cal.startOfDay(for: Date())
        guard let end = cal.date(byAdding: .day, value: daysAhead, to: start) else {
            return
        }
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
        deviceEvents = store.events(matching: predicate)
            .map(AgendaEvent.init(ekEvent:))
    }
}
