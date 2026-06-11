import SwiftUI
import SwiftData
import EventKit

/// 메인 화면. 기기 캘린더 + 앱 일정을 날짜별 아젠다 리스트로 보여준다.
struct AgendaView: View {
    @Environment(\.modelContext) private var context
    @Environment(CalendarManager.self) private var manager

    /// 앱 자체 일정. 시작 시간순으로 정렬해 가져온다.
    @Query(sort: \LocalEvent.start) private var localEvents: [LocalEvent]

    @State private var editingTarget: EditTarget?

    /// 시트로 띄울 편집 대상. 새 일정/기존 일정 구분.
    private enum EditTarget: Identifiable {
        case new
        case existing(LocalEvent)

        var id: String {
            switch self {
            case .new: return "new"
            case .existing(let e): return e.id.uuidString
            }
        }
    }

    /// 기기 일정 + 앱 일정을 합쳐 날짜별로 묶은 결과.
    private var sections: [DaySection] {
        let local = localEvents.map(AgendaEvent.init(local:))
        return AgendaGrouper.group(manager.deviceEvents + local)
    }

    private var needsAccessBanner: Bool {
        manager.authorizationStatus == .notDetermined || !manager.hasAccess
    }

    var body: some View {
        NavigationStack {
            Group {
                if sections.isEmpty {
                    EmptyStateView(
                        needsAccess: !manager.hasAccess,
                        onRequestAccess: { Task { await manager.requestAccessAndLoad() } },
                        onAdd: { editingTarget = .new }
                    )
                } else {
                    agendaList
                }
            }
            .background(Theme.background)
            .navigationTitle("아젠다")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editingTarget = .new
                    } label: {
                        Image(systemName: "plus")
                            .font(.body.weight(.semibold))
                    }
                    .accessibilityLabel("일정 추가")
                }
            }
            .sheet(item: $editingTarget) { target in
                switch target {
                case .new:
                    EventEditView()
                case .existing(let event):
                    EventEditView(editing: event)
                }
            }
        }
        .task {
            // 첫 진입 시 권한 요청 및 기기 일정 로드.
            await manager.requestAccessAndLoad()
        }
        .refreshable {
            manager.loadDeviceEvents()
        }
    }

    private var agendaList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing, pinnedViews: [.sectionHeaders]) {
                if needsAccessBanner {
                    accessBanner
                }
                ForEach(sections) { section in
                    Section {
                        VStack(spacing: Theme.cardSpacing) {
                            ForEach(section.events) { event in
                                eventRow(event)
                            }
                        }
                    } header: {
                        DayHeaderView(section: section)
                            .padding(.vertical, 6)
                            .background(Theme.background)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
    }

    @ViewBuilder
    private func eventRow(_ event: AgendaEvent) -> some View {
        if event.isEditable, let id = event.localID, let local = localEvent(for: id) {
            Button {
                editingTarget = .existing(local)
            } label: {
                EventRow(event: event)
            }
            .buttonStyle(.plain)
            .swipeable(onDelete: { context.delete(local) })
        } else {
            EventRow(event: event)
        }
    }

    private func localEvent(for id: UUID) -> LocalEvent? {
        localEvents.first { $0.id == id }
    }

    /// 권한이 없을 때 리스트 위에 띄우는 안내 배너.
    private var accessBanner: some View {
        Button {
            Task { await manager.requestAccessAndLoad() }
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "calendar.badge.exclamationmark")
                VStack(alignment: .leading, spacing: 2) {
                    Text("기기 캘린더가 연결되지 않았어요")
                        .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    Text("탭하면 기존 일정도 함께 볼 수 있어요")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
            .padding(14)
            .background(Theme.accent.opacity(0.12), in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))
            .foregroundStyle(.primary)
        }
        .buttonStyle(.plain)
    }
}

/// 카드 형태 행에 스와이프 삭제를 붙이기 위한 헬퍼.
private extension View {
    func swipeable(onDelete: @escaping () -> Void) -> some View {
        // ScrollView의 LazyVStack에는 List의 swipeActions가 없으므로
        // 컨텍스트 메뉴로 삭제를 제공한다.
        contextMenu {
            Button("삭제", systemImage: "trash", role: .destructive, action: onDelete)
        }
    }
}

#Preview {
    AgendaView()
        .environment(CalendarManager())
        .modelContainer(for: LocalEvent.self, inMemory: true)
}
