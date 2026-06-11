import SwiftUI

/// 보여줄 일정이 없을 때의 안내 화면.
struct EmptyStateView: View {
    var needsAccess: Bool
    var onRequestAccess: () -> Void
    var onAdd: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "calendar.day.timeline.left")
                .font(.system(size: 56))
                .foregroundStyle(Theme.accent)

            Text(needsAccess ? "캘린더에 연결해 주세요" : "예정된 일정이 없어요")
                .font(.system(.title3, design: .rounded, weight: .bold))

            Text(needsAccess
                 ? "기기 캘린더 일정을 함께 보려면 접근을 허용해 주세요. 허용하지 않아도 앱에서 직접 일정을 추가할 수 있어요."
                 : "오른쪽 위 + 버튼으로 첫 일정을 추가해 보세요.")
                .font(Theme.detail)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            if needsAccess {
                Button("캘린더 접근 허용", action: onRequestAccess)
                    .buttonStyle(.borderedProminent)
            } else {
                Button("일정 추가", action: onAdd)
                    .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}
