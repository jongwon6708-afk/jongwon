import Foundation
import SwiftData

/// 앱 안에서 직접 만든 일정. SwiftData로 기기에 저장된다.
///
/// 기기 기본 캘린더(EventKit) 일정은 읽기 전용으로만 합쳐 보여주고,
/// 새로 추가·수정·삭제가 가능한 일정은 이 모델로 관리한다.
@Model
final class LocalEvent {
    var id: UUID
    var title: String
    var start: Date
    var end: Date
    var isAllDay: Bool
    var location: String
    var notes: String
    /// `EventCategory.rawValue`. SwiftData가 enum을 직접 저장하기 까다로워
    /// 문자열로 보관하고 `category`로 변환해 쓴다.
    var categoryRaw: String

    init(
        id: UUID = UUID(),
        title: String,
        start: Date,
        end: Date,
        isAllDay: Bool = false,
        location: String = "",
        notes: String = "",
        category: EventCategory = .general
    ) {
        self.id = id
        self.title = title
        self.start = start
        self.end = end
        self.isAllDay = isAllDay
        self.location = location
        self.notes = notes
        self.categoryRaw = category.rawValue
    }

    var category: EventCategory {
        get { EventCategory(rawValue: categoryRaw) ?? .general }
        set { categoryRaw = newValue.rawValue }
    }
}
