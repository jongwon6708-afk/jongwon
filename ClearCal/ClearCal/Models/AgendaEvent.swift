import SwiftUI
import EventKit

/// 화면에 그릴 통합 일정 모델.
///
/// 기기 캘린더(EventKit)의 `EKEvent`와 앱 자체 `LocalEvent`는 형태가 다르다.
/// 둘을 한 리스트에서 똑같이 다루기 위해 이 값 타입으로 평탄화한다.
struct AgendaEvent: Identifiable, Hashable {
    enum Source {
        case device   // 기기 기본 캘린더 (읽기 전용)
        case local    // 앱에서 만든 일정 (편집 가능)
    }

    let id: String
    var title: String
    var start: Date
    var end: Date
    var isAllDay: Bool
    var location: String?
    var notes: String?
    var category: EventCategory
    var source: Source
    /// 좌측 색 막대 등에 쓰는 강조색.
    var tint: Color
    /// 편집 화면으로 연결하기 위한 로컬 일정 식별자(로컬 일정일 때만).
    var localID: UUID?

    var isEditable: Bool { source == .local }

    /// 종일 일정이 아닐 때의 표시용 시간 범위 문자열. 예: "오후 2:00 – 3:30".
    var timeRangeText: String {
        if isAllDay { return "종일" }
        let f = DateFormatter.agendaTime
        return "\(f.string(from: start)) – \(f.string(from: end))"
    }
}

extension AgendaEvent {
    /// 기기 기본 캘린더 일정에서 생성.
    init(ekEvent: EKEvent) {
        self.id = "ek-\(ekEvent.eventIdentifier ?? UUID().uuidString)"
        self.title = ekEvent.title ?? "(제목 없음)"
        self.start = ekEvent.startDate ?? Date()
        self.end = ekEvent.endDate ?? ekEvent.startDate ?? Date()
        self.isAllDay = ekEvent.isAllDay
        self.location = ekEvent.location?.isEmpty == false ? ekEvent.location : nil
        self.notes = ekEvent.notes?.isEmpty == false ? ekEvent.notes : nil
        self.category = .general
        self.source = .device
        // 캘린더가 가진 색을 그대로 강조색으로 사용.
        if let cg = ekEvent.calendar?.cgColor {
            self.tint = Color(cgColor: cg)
        } else {
            self.tint = EventCategory.general.color
        }
        self.localID = nil
    }

    /// 앱 자체 일정에서 생성.
    init(local: LocalEvent) {
        self.id = "local-\(local.id.uuidString)"
        self.title = local.title.isEmpty ? "(제목 없음)" : local.title
        self.start = local.start
        self.end = local.end
        self.isAllDay = local.isAllDay
        self.location = local.location.isEmpty ? nil : local.location
        self.notes = local.notes.isEmpty ? nil : local.notes
        self.category = local.category
        self.source = .local
        self.tint = local.category.color
        self.localID = local.id
    }
}

extension DateFormatter {
    /// "오후 2:00" 형태의 시간 포매터.
    static let agendaTime: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        f.setLocalizedDateFormatFromTemplate("a h:mm")
        return f
    }()
}
