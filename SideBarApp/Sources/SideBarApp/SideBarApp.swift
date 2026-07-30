import SwiftUI
import AppKit
import Combine
import IOKit
import ServiceManagement

let stockTimer = Timer.publish(every: 10, on: .main, in: .common).autoconnect()
let countdownTimer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
let stopwatchTimer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

// MARK: - Models

func t(_ key: String, _ lang: String) -> String {
    let dict: [String: [String: String]] = [
        "Settings": ["en": "Settings", "zh": "侧边栏模块管理"],
        "CPU": ["en": "CPU", "zh": "CPU"],
        "GPU": ["en": "GPU", "zh": "GPU"],
        "Memory": ["en": "RAM", "zh": "内存"],
        "Disk": ["en": "Disk", "zh": "磁盘"],
        "Fan": ["en": "Fan", "zh": "风扇"],
        "Network": ["en": "Network", "zh": "网络"],
        "Stock": ["en": "Stock", "zh": "股票"],
        "Countdown": ["en": "Countdown", "zh": "倒计时"],
        "Stopwatch": ["en": "Stopwatch", "zh": "秒表"],
        "Screen Record": ["en": "Screen Record", "zh": "录屏"],
        "Calculator": ["en": "Calculator", "zh": "计算器"],
        "Keyboard": ["en": "Keyboard", "zh": "键盘监视"],
        "Not Set": ["en": "Not Set", "zh": "未设置"],
        "Add Module": ["en": "Add Module", "zh": "新增模块"],
        "Add": ["en": "Add", "zh": "添加"],
        "Launch at Login": ["en": "Launch at Login", "zh": "随系统启动"],
        "Hint": ["en": "Hint: Drag to reorder, click trash to delete.", "zh": "提示：按住行可以拖拽排序，点击右侧垃圾桶图标即可删除。"],
        "Language": ["en": "Language", "zh": "语言"],
        "Min": ["en": "Min", "zh": "分"],
        "KEYS": ["en": "KEYS", "zh": "按键"],
        "Loading...": ["en": "Loading...", "zh": "加载中..."],
        "Invalid Code": ["en": "Invalid Code", "zh": "无效代码"],
        "Waiting...": ["en": "Waiting...", "zh": "等待输入..."],
        "No Accessibility": ["en": "No Accessibility", "zh": "无辅助功能权限"],
        "SettingsTitle": ["en": "Settings", "zh": "后台设置"]
    ]
    return dict[key]?[lang] ?? key
}

enum ModuleType: String, CaseIterable, Codable, Identifiable {
    case cpu = "CPU"
    case gpu = "GPU"
    case memory = "Memory"
    case disk = "Disk"
    case fan = "Fan"
    case network = "Network"
    case stock = "Stock"
    case countdown = "Countdown"
    case stopwatch = "Stopwatch"
    case screenRecord = "Screen Record"
    case calculator = "Calculator"
    case keyboard = "Keyboard"
    
    var id: String { self.rawValue }
}

struct AppModule: Identifiable, Codable, Equatable {
    var id: UUID = UUID()
    var type: ModuleType
    var customData: String = "" // e.g., stock symbol
}

class ModuleStore: ObservableObject {
    static let shared = ModuleStore()
    
    @Published var modules: [AppModule] = [] {
        didSet {
            if let data = try? JSONEncoder().encode(modules) {
                UserDefaults.standard.set(data, forKey: "savedModules")
            }
        }
    }
    
    init() {
        if let data = UserDefaults.standard.data(forKey: "savedModules"),
           let saved = try? JSONDecoder().decode([AppModule].self, from: data) {
            modules = saved
        } else {
            // Defaults
            modules = [
                AppModule(type: .cpu),
                AppModule(type: .gpu),
                AppModule(type: .memory),
                AppModule(type: .disk),
                AppModule(type: .fan),
                AppModule(type: .network),
                AppModule(type: .stock, customData: "sh000001"),
                AppModule(type: .countdown),
                AppModule(type: .stopwatch),
                AppModule(type: .screenRecord)
            ]
        }
    }
}

// MARK: - App Entry
@main
struct SideBarApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

// MARK: - Settings View (后台)
struct SettingsView: View {
    @EnvironmentObject private var store: ModuleStore
    @State private var selectedModuleType: ModuleType = .cpu
    @AppStorage("launchAtLogin") private var launchAtLogin = false
    @AppStorage("language") private var lang = "zh"
    
    var body: some View {
        VStack {
            Text(t("Settings", lang))
                .font(.title2)
                .padding()
            
            List {
                ForEach(store.modules) { module in
                    HStack {
                        Text(t(module.type.rawValue, lang))
                        Spacer()
                        if module.type == .stock {
                            Text(module.customData.isEmpty ? t("Not Set", lang) : module.customData)
                                .foregroundColor(.secondary)
                        }
                        Button(action: {
                            if let idx = store.modules.firstIndex(of: module) {
                                store.modules.remove(at: idx)
                            }
                        }) {
                            Image(systemName: "trash")
                                .foregroundColor(.red)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .padding(.leading, 8)
                    }
                    .padding(.vertical, 4)
                }
                .onMove { indices, newOffset in
                    store.modules.move(fromOffsets: indices, toOffset: newOffset)
                }
                .onDelete { indexSet in
                    store.modules.remove(atOffsets: indexSet)
                }
            }
            .frame(minHeight: 250)
            HStack {
                Picker(t("Language", lang), selection: $lang) {
                    Text("中文").tag("zh")
                    Text("English").tag("en")
                }
                .pickerStyle(SegmentedPickerStyle())
                .frame(width: 250)
            }
            .padding(.horizontal)
            .padding(.top, 4)

            
            Toggle(t("Launch at Login", lang), isOn: $launchAtLogin)
                .onChange(of: launchAtLogin) { newValue in
                    do {
                        if newValue {
                            try SMAppService.mainApp.register()
                        } else {
                            try SMAppService.mainApp.unregister()
                        }
                    } catch {
                        print("Failed to change launch at login: \(error)")
                        launchAtLogin = SMAppService.mainApp.status == .enabled
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 4)
            
            HStack {
                Picker(t("Add Module", lang), selection: $selectedModuleType) {
                    ForEach(ModuleType.allCases) { type in
                        Text(t(type.rawValue, lang)).tag(type)
                    }
                }
                .frame(width: 150)
                
                Button(t("Add", lang)) {
                    let custom = selectedModuleType == .stock ? "sh000001" : ""
                    store.modules.append(AppModule(type: selectedModuleType, customData: custom))
                }
            }
            .padding()
            
            Text(t("Hint", lang))
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(.bottom, 8)
                
            Link("Visit sunnydodo.top", destination: URL(string: "https://sunnydodo.top")!)
                .font(.footnote)
                .foregroundColor(.blue)
                .padding(.bottom)
        }
        .frame(width: 400, height: 530)
        .onAppear {
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
    }
}

// MARK: - NSPanel and AppDelegate
class SidebarPanel: NSPanel {
    override var canBecomeKey: Bool { return true }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    static private(set) var shared: AppDelegate!
    
    var panel: SidebarPanel!
    var moduleStore = ModuleStore.shared
    
    override init() {
        super.init()
        AppDelegate.shared = self
    }
    
    lazy var settingsWindow: NSWindow = {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 350, height: 500),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = UserDefaults.standard.string(forKey: "language") == "en" ? "Settings" : "后台设置"
        window.center()
        window.isReleasedWhenClosed = false
        window.contentView = NSHostingView(rootView: SettingsView().environmentObject(moduleStore))
        return window
    }()
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory) // Hide Dock icon
        
        let screen = NSScreen.main ?? NSScreen.screens[0]
        let screenRect = screen.visibleFrame
        let defaultWidth = screen.frame.width / 20
        let savedWidth = UserDefaults.standard.double(forKey: "sidebarWidth")
        let width = savedWidth > 0 ? CGFloat(savedWidth) : defaultWidth
        let rect = NSRect(x: screenRect.minX, y: screenRect.minY, width: width, height: screenRect.height)
        
        panel = SidebarPanel(
            contentRect: rect,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
        panel.isOpaque = false
        panel.backgroundColor = NSColor.clear
        panel.hasShadow = false
        
        let hostingController = NSHostingController(rootView: MainSidebarView())
        panel.contentView = hostingController.view
        panel.makeKeyAndOrderFront(nil)
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }
    
    func openSettings() {
        settingsWindow.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

struct VisualEffectBackground: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.blendingMode = .behindWindow
        view.state = .active
        view.material = .sidebar
        return view
    }
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
}

struct WindowAccessor: NSViewRepresentable {
    @Binding var window: NSWindow?
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async { self.window = view.window }
        return view
    }
    func updateNSView(_ nsView: NSView, context: Context) {}
}

// MARK: - Main Sidebar View
struct MainSidebarView: View {
    @StateObject private var monitor = SystemMonitor()
    @StateObject private var store = ModuleStore.shared
    @AppStorage("bgOpacity") var bgOpacity: Double = 1.0
    @State private var window: NSWindow?
    @State private var initialWidth: CGFloat = 0
    @AppStorage("language") private var lang = "zh"
    
    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    ForEach(store.modules) { module in
                        Divider()
                        moduleView(for: module)
                            .frame(height: 100)
                    }
                }
            }
            
            Divider()
            
            // Bottom controls
            HStack {
                Slider(value: $bgOpacity, in: 0...1)
                    .help("调节背景透明度")
                
                Button(action: {
                    AppDelegate.shared.openSettings()
                }) {
                    Image(systemName: "gearshape.fill")
                        .foregroundColor(.primary)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(VisualEffectBackground().opacity(bgOpacity))
        .background(WindowAccessor(window: $window))
        .overlay(
            HStack {
                Spacer()
                Rectangle()
                    .fill(Color.white.opacity(0.001))
                    .frame(width: 8)
                    .onHover { isHovering in
                        if isHovering { NSCursor.resizeLeftRight.push() } else { NSCursor.pop() }
                    }
                    .gesture(
                        DragGesture()
                            .onChanged { value in
                                guard let win = window else { return }
                                if initialWidth == 0 { initialWidth = win.frame.width }
                                let newWidth = max(50, initialWidth + value.translation.width)
                                var frame = win.frame
                                frame.size.width = newWidth
                                win.setFrame(frame, display: true)
                            }
                            .onEnded { _ in
                                initialWidth = 0
                                if let win = window {
                                    UserDefaults.standard.set(win.frame.width, forKey: "sidebarWidth")
                                }
                            }
                    )
            }
        )
    }
    
    @ViewBuilder
    private func moduleView(for module: AppModule) -> some View {
        switch module.type {
        case .cpu:
            UsageView(title: t("CPU", lang), usage: monitor.cpuUsage, color: .blue)
        case .gpu:
            UsageView(title: t("GPU", lang), usage: monitor.gpuUsage, color: .purple)
        case .memory:
            UsageView(title: t("Memory", lang), usage: monitor.memoryUsage, color: .orange)
        case .disk:
            UsageView(title: t("Disk", lang), usage: monitor.diskUsagePercent, color: .brown)
        case .fan:
            FanSpeedView(speed: monitor.fanSpeed)
        case .network:
            NetworkSpeedView(up: monitor.networkUp, down: monitor.networkDown)
        case .stock:
            StockView(moduleId: module.id, initialSymbol: module.customData)
        case .countdown:
            CountdownView()
        case .stopwatch:
            StopwatchView()
        case .screenRecord:
            ScreenRecordView()
        case .calculator:
            CalculatorView()
        case .keyboard:
            KeyboardMonitorView()
        }
    }
}

// MARK: - Views
struct UsageView: View {
    let title: String
    let usage: Double
    let color: Color
    
    var body: some View {
        VStack {
            Text(title)
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            Spacer()
            ZStack {
                Circle()
                    .stroke(lineWidth: 5)
                    .opacity(0.15)
                    .foregroundColor(color)
                Circle()
                    .trim(from: 0, to: CGFloat(min(usage / 100, 1.0)))
                    .stroke(
                        AngularGradient(
                            gradient: Gradient(colors: [color.opacity(0.4), color]),
                            center: .center,
                            startAngle: .degrees(-90),
                            endAngle: .degrees(270)
                        ),
                        style: StrokeStyle(lineWidth: 5, lineCap: .round, lineJoin: .round)
                    )
                    .rotationEffect(Angle(degrees: 270))
                    .shadow(color: color.opacity(0.6), radius: 4, x: 0, y: 0)
                
                Text(String(format: "%.0f", usage))
                    .font(.system(size: 13, weight: .heavy, design: .rounded))
                + Text("%")
                    .font(.system(size: 9, weight: .semibold, design: .rounded))
            }
            .frame(width: 44, height: 44)
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct NetworkSpeedView: View {
    let up: Double
    let down: Double
    @AppStorage("language") private var lang = "zh"
    
    var body: some View {
        VStack(spacing: 8) {
            Text(t("Network", lang))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Image(systemName: "arrow.up.forward.circle.fill")
                        .foregroundColor(.green)
                        .shadow(color: .green.opacity(0.4), radius: 2, x: 0, y: 1)
                    Text(formatBytes(up))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                }
                HStack {
                    Image(systemName: "arrow.down.right.circle.fill")
                        .foregroundColor(.blue)
                        .shadow(color: .blue.opacity(0.4), radius: 2, x: 0, y: 1)
                    Text(formatBytes(down))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    private func formatBytes(_ bytes: Double) -> String {
        if bytes > 1_048_576 { return String(format: "%.1f MB/s", bytes / 1_048_576) }
        if bytes > 1024 { return String(format: "%.0f KB/s", bytes / 1024) }
        return String(format: "%.0f B/s", bytes)
    }
}

struct FanSpeedView: View {
    let speed: Int
    @State private var rotation: Double = 0
    @AppStorage("language") private var lang = "zh"
    
    var body: some View {
        VStack {
            Text(t("Fan", lang))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            Spacer()
            Image(systemName: "fanblades.fill")
                .font(.system(size: 26))
                .symbolRenderingMode(.hierarchical)
                .foregroundColor(.teal)
                .shadow(color: .teal.opacity(0.5), radius: 4, x: 0, y: 0)
                .rotationEffect(.degrees(rotation))
                .onAppear {
                    withAnimation(.linear(duration: 0.5).repeatForever(autoreverses: false)) {
                        rotation = 360
                    }
                }
            Spacer()
            Text("\(speed) RPM")
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct StockView: View {
    let moduleId: UUID
    @State var symbol: String
    @State private var stockName: String = "加载中..."
    @State private var price: String = "加载中..."
    @State private var change: String = ""
    @State private var isUp: Bool = true
    
    @State private var isEditing = false
    @State private var inputSymbol = ""
    
    @AppStorage("language") private var lang = "zh"
        
    init(moduleId: UUID, initialSymbol: String) {
        self.moduleId = moduleId
        _symbol = State(initialValue: initialSymbol)
    }
    
    func formatStockSymbol(_ input: String) -> String {
        let clean = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        let numbers = clean.filter { $0.isNumber }
        if numbers.count == 6 {
            if numbers.hasPrefix("6") {
                return "sh" + numbers
            } else if numbers.hasPrefix("0") || numbers.hasPrefix("3") {
                return "sz" + numbers
            } else if numbers.hasPrefix("4") || numbers.hasPrefix("8") {
                return "bj" + numbers
            }
        }
        return clean
    }
    
    func fetchStock() {
        let ts = Int(Date().timeIntervalSince1970)
        guard let url = URL(string: "https://qt.gtimg.cn/q=\(symbol)&t=\(ts)") else { return }
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: request) { data, response, error in
            guard let data = data else { return }
            let nsEncoding = CFStringConvertEncodingToNSStringEncoding(CFStringEncoding(CFStringEncodings.GB_18030_2000.rawValue))
            guard let str = String(data: data, encoding: String.Encoding(rawValue: nsEncoding)) else { return }
            
            let components = str.components(separatedBy: "~")
            if components.count > 32 {
                let name = components[1]
                let currentPrice = components[3]
                let percentChange = components[32]
                let diff = Double(components[31]) ?? 0
                
                DispatchQueue.main.async {
                    self.stockName = name
                    self.price = currentPrice
                    self.change = (diff >= 0 ? "+" : "") + percentChange + "%"
                    self.isUp = diff >= 0
                }
            } else {
                DispatchQueue.main.async {
                    self.stockName = t("Invalid Code", lang)
                    self.price = "-"
                    self.change = ""
                }
            }
        }.resume()
    }
    
    var body: some View {
        VStack(spacing: 4) {
            if isEditing {
                TextField("sh000001", text: $inputSymbol)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .onSubmit {
                        let formatted = formatStockSymbol(inputSymbol)
                        symbol = formatted.isEmpty ? "sh000001" : formatted
                        isEditing = false
                        if let idx = ModuleStore.shared.modules.firstIndex(where: { $0.id == moduleId }) {
                            ModuleStore.shared.modules[idx].customData = symbol
                        }
                        fetchStock()
                    }
                Spacer()
            } else {
                Text(stockName == "加载中..." ? t("Loading...", lang) : (stockName == "无效代码" ? t("Invalid Code", lang) : stockName))
                    .font(.system(size: 13, weight: .bold, design: .rounded))
                    .foregroundColor(.primary.opacity(0.85))
                    .lineLimit(1)
                    .fixedSize(horizontal: false, vertical: true)
                
                Spacer(minLength: 0)
                
                Text(price)
                    .font(.system(size: 18, weight: .heavy, design: .rounded))
                    .foregroundColor(isUp ? .red : .green)
                    .shadow(color: (isUp ? Color.red : Color.green).opacity(0.2), radius: 2, x: 0, y: 1)
                    .lineLimit(1)
                    .fixedSize(horizontal: false, vertical: true)
                
                Spacer(minLength: 0)
                
                if !change.isEmpty {
                    Text(change)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(isUp ? .red : .green)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background((isUp ? Color.red : Color.green).opacity(0.15))
                        .cornerRadius(4)
                        .lineLimit(1)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .contentShape(Rectangle())
        .onTapGesture(count: 2) {
            inputSymbol = symbol
            isEditing = true
        }
        .onAppear { fetchStock() }
        .onReceive(stockTimer) { _ in if !isEditing { fetchStock() } }
    }
}

struct CountdownView: View {
    @State private var timeRemaining: Int = 25 * 60
    @State private var isActive = false
    @State private var isEditing = false
    @State private var inputMinutes = ""
        @AppStorage("language") private var lang = "zh"
    
    var timeString: String {
        let minutes = timeRemaining / 60
        let seconds = timeRemaining % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }
    
    var body: some View {
        VStack(spacing: 8) {
            Text(t("Countdown", lang))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            
            if isEditing {
                TextField(t("Min", lang), text: $inputMinutes)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .frame(width: 65)
                    .onSubmit {
                        if let mins = Int(inputMinutes) {
                            timeRemaining = mins * 60
                        }
                        isEditing = false
                    }
            } else {
                Text(timeString)
                    .font(.system(.title2, design: .monospaced))
                    .fontWeight(.bold)
                    .contentShape(Rectangle())
                    .onTapGesture(count: 2) {
                        inputMinutes = String(timeRemaining / 60)
                        isActive = false
                        isEditing = true
                    }
            }
            
            HStack(spacing: 16) {
                Button(action: { isActive.toggle() }) {
                    Image(systemName: isActive ? "pause.circle.fill" : "play.circle.fill")
                        .font(.system(size: 22))
                        .symbolRenderingMode(.palette)
                        .foregroundStyle(isActive ? .orange : .green, .primary.opacity(0.1))
                        .shadow(color: (isActive ? Color.orange : Color.green).opacity(0.3), radius: 3, x: 0, y: 1)
                }
                .buttonStyle(PlainButtonStyle())
                
                Button(action: {
                    isActive = false
                    timeRemaining = 25 * 60
                }) {
                    Image(systemName: "arrow.counterclockwise.circle.fill")
                        .font(.system(size: 22))
                        .symbolRenderingMode(.palette)
                        .foregroundStyle(.blue, .primary.opacity(0.1))
                        .shadow(color: .blue.opacity(0.3), radius: 3, x: 0, y: 1)
                }
                .buttonStyle(PlainButtonStyle())
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onReceive(countdownTimer) { _ in
            if isActive && timeRemaining > 0 {
                timeRemaining -= 1
            } else if isActive && timeRemaining == 0 {
                isActive = false
                NSSound(named: NSSound.Name("Glass"))?.play()
            }
        }
    }
}

struct StopwatchView: View {
    @State private var timeElapsed: Int = 0
    @State private var isActive = false
    @AppStorage("language") private var lang = "zh"
        
    var timeString: String {
        let minutes = timeElapsed / 60
        let seconds = timeElapsed % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }
    
    var body: some View {
        VStack(spacing: 8) {
            Text(t("Stopwatch", lang))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            Text(timeString)
                .font(.system(.title2, design: .monospaced))
                .fontWeight(.bold)
            HStack(spacing: 16) {
                Button(action: { isActive.toggle() }) {
                    Image(systemName: isActive ? "pause.circle.fill" : "play.circle.fill")
                        .font(.system(size: 22))
                        .symbolRenderingMode(.palette)
                        .foregroundStyle(isActive ? .orange : .green, .primary.opacity(0.1))
                        .shadow(color: (isActive ? Color.orange : Color.green).opacity(0.3), radius: 3, x: 0, y: 1)
                }
                .buttonStyle(PlainButtonStyle())
                Button(action: {
                    isActive = false
                    timeElapsed = 0
                }) {
                    Image(systemName: "stop.circle.fill")
                        .font(.system(size: 22))
                        .symbolRenderingMode(.palette)
                        .foregroundStyle(.red, .primary.opacity(0.1))
                        .shadow(color: .red.opacity(0.3), radius: 3, x: 0, y: 1)
                }
                .buttonStyle(PlainButtonStyle())
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onReceive(stopwatchTimer) { _ in
            if isActive { timeElapsed += 1 }
        }
    }
}

struct ScreenRecordView: View {
    @AppStorage("language") private var lang = "zh"
    var body: some View {
        VStack {
            Text(t("Screen Record", lang))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            Spacer()
            Button(action: {
                let task = Process()
                task.launchPath = "/usr/bin/open"
                task.arguments = ["-a", "Screenshot"]
                try? task.run()
            }) {
                Image(systemName: "record.circle.fill")
                    .font(.system(size: 32))
                    .symbolRenderingMode(.multicolor)
                    .foregroundStyle(.red)
                    .shadow(color: .red.opacity(0.6), radius: 5, x: 0, y: 0)
            }
            .buttonStyle(PlainButtonStyle())
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct CalculatorView: View {
    @State private var display = "0"
    @State private var previous = 0.0
    @State private var operation: String?
    @State private var typingNewNumber = true
    
    let buttons = [
        ["C", "±", "%", "÷"],
        ["7", "8", "9", "×"],
        ["4", "5", "6", "-"],
        ["1", "2", "3", "+"],
        ["0", ".", "="]
    ]
    
    var body: some View {
        VStack(spacing: 2) {
            Text(display)
                .font(.system(size: 16, weight: .bold, design: .monospaced))
                .lineLimit(1)
                .minimumScaleFactor(0.4)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.horizontal, 4)
                .padding(.vertical, 2)
                .background(Color.white.opacity(0.1))
                .cornerRadius(4)
            
            ForEach(buttons, id: \.self) { row in
                HStack(spacing: 2) {
                    ForEach(row, id: \.self) { btn in
                        Button(action: { buttonTapped(btn) }) {
                            Text(btn)
                                .font(.system(size: 12, weight: .medium))
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                                .background(buttonColor(btn).opacity(0.6))
                                .cornerRadius(3)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .frame(height: 18)
                    }
                }
            }
        }
        .padding(4)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    func buttonColor(_ btn: String) -> Color {
        if ["÷", "×", "-", "+", "="].contains(btn) { return .orange }
        if ["C", "±", "%"].contains(btn) { return .gray }
        return Color.secondary.opacity(0.5)
    }
    
    func buttonTapped(_ btn: String) {
        if btn == "C" {
            display = "0"
            previous = 0
            operation = nil
            typingNewNumber = true
        } else if btn == "±" {
            if let current = Double(display) {
                display = format(-current)
            }
        } else if btn == "%" {
            if let current = Double(display) {
                display = format(current / 100)
            }
        } else if btn == "." {
            if !display.contains(".") { display += "." }
            typingNewNumber = false
        } else if ["÷", "×", "-", "+"].contains(btn) {
            if let current = Double(display) {
                calculate(current)
                operation = btn
                typingNewNumber = true
            }
        } else if btn == "=" {
            if let current = Double(display) {
                calculate(current)
                operation = nil
                typingNewNumber = true
            }
        } else {
            if typingNewNumber {
                display = btn
                typingNewNumber = false
            } else {
                display += btn
            }
        }
    }
    
    func calculate(_ current: Double) {
        guard let op = operation else {
            previous = current
            return
        }
        var result = previous
        switch op {
        case "+": result += current
        case "-": result -= current
        case "×": result *= current
        case "÷": result = current != 0 ? result / current : 0
        default: break
        }
        previous = result
        display = format(result)
    }
    
    func format(_ num: Double) -> String {
        return num.truncatingRemainder(dividingBy: 1) == 0 ? String(format: "%.0f", num) : String(num)
    }
}

class KeyboardListener: ObservableObject {
    @Published var currentKeys: String = "Waiting..."
    private var runLoopSource: CFRunLoopSource?
    private var eventTap: CFMachPort?
    
    init() {
        startMonitoring()
    }
    
    deinit {
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
        if let source = runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .commonModes)
        }
    }
    
    func startMonitoring() {
        let options: NSDictionary = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String : true]
        let accessEnabled = AXIsProcessTrustedWithOptions(options)
        
        if !accessEnabled {
            currentKeys = "无辅助功能权限"
            return
        }
        
        let mask = (1 << CGEventType.keyDown.rawValue) | (1 << CGEventType.flagsChanged.rawValue)
        
        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: CGEventMask(mask),
            callback: { (proxy, type, event, refcon) -> Unmanaged<CGEvent>? in
                if let observer = refcon {
                    let mySelf = Unmanaged<KeyboardListener>.fromOpaque(observer).takeUnretainedValue()
                    mySelf.handleCGEvent(event, type: type)
                }
                return Unmanaged.passUnretained(event)
            },
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        )
        
        if let tap = eventTap {
            runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
            CGEvent.tapEnable(tap: tap, enable: true)
            currentKeys = ""
        }
    }
    
    private func handleCGEvent(_ event: CGEvent, type: CGEventType) {
        var keys = ""
        let flags = event.flags
        
        if flags.contains(.maskControl) { keys += "⌃ " }
        if flags.contains(.maskAlternate) { keys += "⌥ " }
        if flags.contains(.maskShift) { keys += "⇧ " }
        if flags.contains(.maskCommand) { keys += "⌘ " }
        
        if type == .keyDown {
            let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
            let charStr = keycodeToString(UInt16(keyCode))
            if !charStr.isEmpty { keys += charStr }
        }
        
        let finalKeys = keys.trimmingCharacters(in: .whitespaces)
        
        DispatchQueue.main.async {
            if !finalKeys.isEmpty {
                self.currentKeys = finalKeys
            } else if type == .flagsChanged {
                self.currentKeys = ""
            }
        }
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            if self.currentKeys == finalKeys {
                self.currentKeys = ""
            }
        }
    }
    
    private func keycodeToString(_ code: UInt16) -> String {
        switch code {
        case 0: return "A"
        case 1: return "S"
        case 2: return "D"
        case 3: return "F"
        case 4: return "H"
        case 5: return "G"
        case 6: return "Z"
        case 7: return "X"
        case 8: return "C"
        case 9: return "V"
        case 11: return "B"
        case 12: return "Q"
        case 13: return "W"
        case 14: return "E"
        case 15: return "R"
        case 16: return "Y"
        case 17: return "T"
        case 18: return "1"
        case 19: return "2"
        case 20: return "3"
        case 21: return "4"
        case 22: return "6"
        case 23: return "5"
        case 24: return "="
        case 25: return "9"
        case 26: return "7"
        case 27: return "-"
        case 28: return "8"
        case 29: return "0"
        case 30: return "]"
        case 31: return "O"
        case 32: return "U"
        case 33: return "["
        case 34: return "I"
        case 35: return "P"
        case 36: return "⏎"
        case 37: return "L"
        case 38: return "J"
        case 39: return "'"
        case 40: return "K"
        case 41: return ";"
        case 42: return "\\"
        case 43: return ","
        case 44: return "/"
        case 45: return "N"
        case 46: return "M"
        case 47: return "."
        case 48: return "⇥"
        case 49: return "␣"
        case 50: return "`"
        case 51: return "⌫"
        case 53: return "⎋"
        case 123: return "←"
        case 124: return "→"
        case 125: return "↓"
        case 126: return "↑"
        default: return ""
        }
    }
}

struct KeyboardMonitorView: View {
    @StateObject private var listener = KeyboardListener()
    @AppStorage("language") private var lang = "zh"
    
    var body: some View {
        VStack {
            Text(t("KEYS", lang))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            Spacer()
            
            Text(listener.currentKeys.isEmpty ? " " : listener.currentKeys)
                .font(.system(size: listener.currentKeys.count > 5 ? 12 : 16, weight: .heavy, design: .rounded))
                .foregroundColor(.primary)
                .lineLimit(2)
                .multilineTextAlignment(.center)
                .minimumScaleFactor(0.5)
                .frame(maxWidth: .infinity, maxHeight: 40)
                .background(Color.black.opacity(0.1))
                .cornerRadius(6)
            
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
