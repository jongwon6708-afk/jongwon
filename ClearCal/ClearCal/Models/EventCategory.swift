import SwiftUI

/// 일정 분류. 색·아이콘으로 종류를 한눈에 구분하기 위한 태그.
///
/// 가독성을 위해 색은 충분히 대비가 큰 값으로 골랐고, 각 분류마다
/// SF Symbol 아이콘을 함께 둬서 색을 구분하기 어려운 사용자도
/// 모양으로 알아볼 수 있게 했다.
enum EventCategory: String, CaseIterable, Identifiable, Codable {
    case general
    case work
    case personal
    case health
    case social
    case travel

    var id: String { rawValue }

    /// 화면에 보여줄 한글 이름.
    var title: String {
        switch self {
        case .general: return "일반"
        case .work: return "업무"
        case .personal: return "개인"
        case .health: return "건강"
        case .social: return "약속"
        case .travel: return "이동"
        }
    }

    /// 분류를 나타내는 SF Symbol.
    var symbol: String {
        switch self {
        case .general: return "calendar"
        case .work: return "briefcase.fill"
        case .personal: return "house.fill"
        case .health: return "heart.fill"
        case .social: return "person.2.fill"
        case .travel: return "airplane"
        }
    }

    /// 분류 색상. 라이트/다크 모두에서 또렷하게 보이는 채도로 선택.
    var color: Color {
        switch self {
        case .general: return Color(red: 0.40, green: 0.45, blue: 0.55)
        case .work: return Color(red: 0.20, green: 0.45, blue: 0.90)
        case .personal: return Color(red: 0.55, green: 0.35, blue: 0.85)
        case .health: return Color(red: 0.90, green: 0.30, blue: 0.40)
        case .social: return Color(red: 0.95, green: 0.55, blue: 0.15)
        case .travel: return Color(red: 0.15, green: 0.65, blue: 0.55)
        }
    }
}
