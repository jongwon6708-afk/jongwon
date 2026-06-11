import SwiftUI

/// 가독성 중심의 공통 스타일.
///
/// 핵심 원칙: 큼직한 글자, 둥근(rounded) 서체로 부드럽게, 충분한 여백,
/// 색은 분류 구분 용도로만 절제해서 사용. Dynamic Type를 존중하도록
/// 고정 크기 대신 텍스트 스타일 기반 폰트를 쓴다.
enum Theme {
    static let accent = Color(red: 0.20, green: 0.45, blue: 0.90)

    /// 화면 배경.
    static let background = Color(.systemGroupedBackground)
    /// 카드 배경.
    static let card = Color(.secondarySystemGroupedBackground)

    // MARK: 폰트 (모두 rounded 디자인 + Dynamic Type 대응)

    /// 날짜 섹션 제목용.
    static let dayTitle = Font.system(.title2, design: .rounded, weight: .bold)
    /// 일정 제목용. 리스트에서 가장 눈에 띄어야 하는 요소.
    static let eventTitle = Font.system(.headline, design: .rounded, weight: .semibold)
    /// 시간 표시용.
    static let time = Font.system(.subheadline, design: .rounded, weight: .semibold)
    /// 장소·메모 등 보조 정보용.
    static let detail = Font.system(.subheadline, design: .rounded)

    static let cardCornerRadius: CGFloat = 16
    static let cardSpacing: CGFloat = 12
    static let sectionSpacing: CGFloat = 28
}
