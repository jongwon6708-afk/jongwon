import SwiftUI

/// 날짜 섹션의 헤더. "오늘 · 6월 11일 (수)" 형태로 크게 보여준다.
struct DayHeaderView: View {
    let section: DaySection

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            if let relative = section.relativeLabel {
                Text(relative)
                    .font(Theme.dayTitle)
                    .foregroundStyle(section.isToday ? Theme.accent : .primary)
            }
            Text(section.dateTitle)
                .font(Theme.dayTitle)
                .foregroundStyle(section.relativeLabel == nil ? .primary : .secondary)

            Spacer()

            Text("\(section.events.count)건")
                .font(Theme.detail)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 4)
        .padding(.bottom, 6)
    }
}
