import Foundation

/// 같은 날짜의 일정을 묶은 아젠다 섹션.
struct DaySection: Identifiable {
    /// 자정 기준 날짜. 그룹 키이자 식별자.
    let id: Date
    var date: Date
    var events: [AgendaEvent]

    /// "오늘", "내일", "어제" 또는 nil(그 외 날짜).
    var relativeLabel: String? {
        let cal = Calendar.current
        if cal.isDateInToday(date) { return "오늘" }
        if cal.isDateInTomorrow(date) { return "내일" }
        if cal.isDateInYesterday(date) { return "어제" }
        return nil
    }

    /// "6월 11일 (수)" 형태의 날짜 제목.
    var dateTitle: String {
        DateFormatter.dayHeader.string(from: date)
    }

    var isToday: Bool { Calendar.current.isDateInToday(date) }
}

enum AgendaGrouper {
    /// 통합 일정들을 날짜별로 묶고 시간순으로 정렬.
    static func group(_ events: [AgendaEvent]) -> [DaySection] {
        let cal = Calendar.current
        let grouped = Dictionary(grouping: events) { cal.startOfDay(for: $0.start) }
        return grouped
            .map { key, value in
                DaySection(
                    id: key,
                    date: key,
                    events: value.sorted { lhs, rhs in
                        // 종일 일정을 맨 위로, 그다음 시작 시간순.
                        if lhs.isAllDay != rhs.isAllDay { return lhs.isAllDay }
                        return lhs.start < rhs.start
                    }
                )
            }
            .sorted { $0.date < $1.date }
    }
}

extension DateFormatter {
    /// "6월 11일 (수)" 형태의 날짜 헤더 포매터.
    static let dayHeader: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        f.setLocalizedDateFormatFromTemplate("M월 d일 (E)")
        return f
    }()
}
