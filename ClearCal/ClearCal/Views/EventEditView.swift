import SwiftUI
import SwiftData

/// 앱 자체 일정 추가·수정 화면.
///
/// 기존 `LocalEvent`를 넘기면 수정, 없으면 새 일정 추가로 동작한다.
struct EventEditView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var context

    /// 수정 대상. nil이면 새로 추가.
    var editing: LocalEvent?

    @State private var title: String
    @State private var start: Date
    @State private var end: Date
    @State private var isAllDay: Bool
    @State private var location: String
    @State private var notes: String
    @State private var category: EventCategory

    init(editing: LocalEvent? = nil, defaultDate: Date = Date()) {
        self.editing = editing
        let base = editing
        let startDate = base?.start ?? Self.defaultStart(on: defaultDate)
        _title = State(initialValue: base?.title ?? "")
        _start = State(initialValue: startDate)
        _end = State(initialValue: base?.end ?? startDate.addingTimeInterval(3600))
        _isAllDay = State(initialValue: base?.isAllDay ?? false)
        _location = State(initialValue: base?.location ?? "")
        _notes = State(initialValue: base?.notes ?? "")
        _category = State(initialValue: base?.category ?? .general)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("제목", text: $title)
                        .font(.system(.body, design: .rounded, weight: .semibold))
                }

                Section {
                    Toggle("종일", isOn: $isAllDay.animation())
                    DatePicker("시작", selection: $start,
                               displayedComponents: isAllDay ? .date : [.date, .hourAndMinute])
                    if !isAllDay {
                        DatePicker("종료", selection: $end,
                                   in: start..., displayedComponents: [.date, .hourAndMinute])
                    }
                }

                Section("분류") {
                    Picker("분류", selection: $category) {
                        ForEach(EventCategory.allCases) { cat in
                            Label(cat.title, systemImage: cat.symbol).tag(cat)
                        }
                    }
                    .pickerStyle(.navigationLink)
                }

                Section("추가 정보") {
                    TextField("장소", text: $location)
                    TextField("메모", text: $notes, axis: .vertical)
                        .lineLimit(3...6)
                }

                if editing != nil {
                    Section {
                        Button("일정 삭제", role: .destructive, action: delete)
                            .frame(maxWidth: .infinity)
                    }
                }
            }
            .navigationTitle(editing == nil ? "새 일정" : "일정 수정")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("취소") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("저장", action: save)
                        .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }

    private func save() {
        // 종일 일정은 종료를 시작과 같은 날로 맞춰 둔다.
        if isAllDay { end = start }
        if let event = editing {
            event.title = title
            event.start = start
            event.end = end
            event.isAllDay = isAllDay
            event.location = location
            event.notes = notes
            event.category = category
        } else {
            let event = LocalEvent(
                title: title, start: start, end: end, isAllDay: isAllDay,
                location: location, notes: notes, category: category
            )
            context.insert(event)
        }
        dismiss()
    }

    private func delete() {
        if let event = editing {
            context.delete(event)
        }
        dismiss()
    }

    /// 새 일정의 기본 시작 시각: 선택한 날의 다음 정시.
    private static func defaultStart(on date: Date) -> Date {
        let cal = Calendar.current
        let now = Date()
        // 오늘이면 다음 정시, 다른 날이면 오전 9시로.
        if cal.isDate(date, inSameDayAs: now) {
            let nextHour = cal.date(bySettingHour: cal.component(.hour, from: now) + 1,
                                    minute: 0, second: 0, of: now) ?? now
            return nextHour
        }
        return cal.date(bySettingHour: 9, minute: 0, second: 0, of: date) ?? date
    }
}

#Preview {
    EventEditView()
        .modelContainer(for: LocalEvent.self, inMemory: true)
}
