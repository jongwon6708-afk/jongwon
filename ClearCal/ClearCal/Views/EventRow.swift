import SwiftUI

/// 아젠다 리스트의 일정 한 줄.
///
/// 왼쪽엔 시간(또는 "종일"), 가운데 색 막대로 분류를 표시하고,
/// 큼직한 제목과 보조 정보를 둔다. 한눈에 "언제 / 무엇을 / 어디서"가
/// 읽히도록 정보 위계를 잡았다.
struct EventRow: View {
    let event: AgendaEvent

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            timeColumn
                .frame(width: 64, alignment: .leading)

            // 분류/캘린더 색 막대.
            RoundedRectangle(cornerRadius: 3)
                .fill(event.tint)
                .frame(width: 6)

            VStack(alignment: .leading, spacing: 4) {
                Text(event.title)
                    .font(Theme.eventTitle)
                    .foregroundStyle(.primary)
                    .lineLimit(2)

                if let location = event.location {
                    Label(location, systemImage: "mappin.and.ellipse")
                        .font(Theme.detail)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                categoryTag
            }

            Spacer(minLength: 0)
        }
        .padding(.vertical, 14)
        .padding(.horizontal, 16)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityText)
    }

    private var timeColumn: some View {
        VStack(alignment: .leading, spacing: 2) {
            if event.isAllDay {
                Text("종일")
                    .font(Theme.time)
                    .foregroundStyle(event.tint)
            } else {
                Text(DateFormatter.agendaTime.string(from: event.start))
                    .font(Theme.time)
                    .foregroundStyle(.primary)
                Text(DateFormatter.agendaTime.string(from: event.end))
                    .font(Theme.detail)
                    .foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private var categoryTag: some View {
        // 기기 일정은 분류가 없으니(general) 앱 일정에서만 태그를 보여준다.
        if event.source == .local {
            Label(event.category.title, systemImage: event.category.symbol)
                .font(.caption.weight(.semibold))
                .foregroundStyle(event.category.color)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(event.category.color.opacity(0.15), in: Capsule())
                .padding(.top, 2)
        }
    }

    private var accessibilityText: String {
        var parts: [String] = [event.isAllDay ? "종일 일정" : event.timeRangeText, event.title]
        if let location = event.location { parts.append("장소 \(location)") }
        return parts.joined(separator: ", ")
    }
}

#Preview {
    VStack(spacing: 12) {
        EventRow(event: AgendaEvent(
            id: "1", title: "팀 주간 회의", start: .now, end: .now.addingTimeInterval(3600),
            isAllDay: false, location: "3층 회의실", notes: nil,
            category: .work, source: .local, tint: EventCategory.work.color,
            localID: UUID()
        ))
        EventRow(event: AgendaEvent(
            id: "2", title: "워크숍", start: .now, end: .now,
            isAllDay: true, location: nil, notes: nil,
            category: .general, source: .device, tint: EventCategory.travel.color,
            localID: nil
        ))
    }
    .padding()
    .background(Theme.background)
}
