import SwiftUI
import Combine

struct ServerConfig: Codable, Equatable {
    var name: String? = ""
    var ip: String = ""
    var port: String = "22"
    var username: String = "root"
    var password: String = ""
    var keyPath: String = ""
}

class ServerMonitorService: ObservableObject {
    let id: UUID
    @Published var config: ServerConfig
    
    @Published var cpuUsage: Double = 0
    @Published var memoryUsed: Double = 0
    @Published var memoryTotal: Double = 0
    @Published var diskUsed: Double = 0
    @Published var diskTotal: Double = 0
    @Published var netTx: Double = 0
    @Published var netRx: Double = 0
    @Published var isConnected: Bool = false
    
    private var timer: AnyCancellable?
    private var lastNetStats: (rx: Double, tx: Double, time: TimeInterval)?
    private var lastCpuStats: (idle: Double, total: Double)?
    
    private var socketPath: String {
        "/tmp/sidebay_ssh_\(id.uuidString)"
    }
    
    init(id: UUID, config: ServerConfig) {
        self.id = id
        self.config = config
    }
    
    func start() {
        stop()
        guard !config.ip.isEmpty else { return }
        
        setupConnection { [weak self] success in
            guard let self = self, success else { return }
            DispatchQueue.main.async {
                self.isConnected = true
            }
            self.startPolling()
        }
    }
    
    func stop() {
        timer?.cancel()
        timer = nil
        
        // Terminate multiplexing connection
        let task = Process()
        task.launchPath = "/usr/bin/ssh"
        task.arguments = ["-S", socketPath, "-O", "exit", "\(config.username)@\(config.ip)"]
        try? task.run()
        
        DispatchQueue.main.async {
            self.isConnected = false
            self.cpuUsage = 0
            self.memoryUsed = 0
            self.memoryTotal = 0
            self.diskUsed = 0
            self.diskTotal = 0
            self.netTx = 0
            self.netRx = 0
        }
    }
    
    private func setupConnection(completion: @escaping (Bool) -> Void) {
        let fileManager = FileManager.default
        if fileManager.fileExists(atPath: socketPath) {
            try? fileManager.removeItem(atPath: socketPath)
        }
        
        DispatchQueue.global().async {
            if !self.config.keyPath.isEmpty {
                // Key-based auth
                let task = Process()
                task.launchPath = "/usr/bin/ssh"
                task.arguments = [
                    "-M", "-S", self.socketPath,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=5",
                    "-i", self.config.keyPath,
                    "-N", "-f", "-p", self.config.port,
                    "\(self.config.username)@\(self.config.ip)"
                ]
                task.launch()
                task.waitUntilExit()
                
                completion(task.terminationStatus == 0)
            } else {
                // Password-based auth via expect
                let expectScript = """
                set timeout 10
                spawn ssh -M -S \(self.socketPath) -o StrictHostKeyChecking=no -o ConnectTimeout=5 -N -f -p \(self.config.port) \(self.config.username)@\(self.config.ip)
                expect {
                    "*assword:*" {
                        send "\(self.config.password)\\r"
                        exp_continue
                    }
                    eof
                }
                """
                let scriptPath = "/tmp/sidebay_expect_\(self.id.uuidString).exp"
                try? expectScript.write(toFile: scriptPath, atomically: true, encoding: .utf8)
                
                let task = Process()
                task.launchPath = "/usr/bin/expect"
                task.arguments = [scriptPath]
                task.launch()
                task.waitUntilExit()
                
                try? fileManager.removeItem(atPath: scriptPath)
                
                // Wait briefly for socket creation
                usleep(500_000)
                completion(fileManager.fileExists(atPath: self.socketPath))
            }
        }
    }
    
    private func startPolling() {
        timer = Timer.publish(every: 3.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.fetchStats()
            }
        fetchStats() // Fetch immediately
    }
    
    private func fetchStats() {
        DispatchQueue.global().async {
            let task = Process()
            task.launchPath = "/usr/bin/ssh"
            task.arguments = [
                "-S", self.socketPath,
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=3",
                "\(self.config.username)@\(self.config.ip)",
                "cat /proc/stat && echo '---' && cat /proc/meminfo && echo '---' && df -k / && echo '---' && cat /proc/net/dev"
            ]
            
            let pipe = Pipe()
            task.standardOutput = pipe
            
            do {
                try task.run()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                task.waitUntilExit()
                
                guard task.terminationStatus == 0 else {
                    DispatchQueue.main.async {
                        self.isConnected = false
                    }
                    self.stop()
                    return
                }
                
                if let output = String(data: data, encoding: .utf8) {
                    self.parseOutput(output)
                }
            } catch {
                DispatchQueue.main.async { self.isConnected = false }
                self.stop()
            }
        }
    }
    
    private func parseOutput(_ output: String) {
        let parts = output.components(separatedBy: "---")
        guard parts.count >= 4 else { return }
        
        let statStr = parts[0]
        let memStr = parts[1]
        let dfStr = parts[2]
        let netStr = parts[3]
        
        let currentTime = Date().timeIntervalSince1970
        
        var newCpuUsage: Double = 0
        var newMemUsed: Double = 0
        var newMemTotal: Double = 0
        var newDiskUsed: Double = 0
        var newDiskTotal: Double = 0
        var newTx: Double = 0
        var newRx: Double = 0
        
        // Parse CPU
        if let cpuLine = statStr.components(separatedBy: .newlines).first(where: { $0.starts(with: "cpu ") }) {
            let vals = cpuLine.split(separator: " ").compactMap { Double($0) }
            if vals.count >= 4 {
                let idle = vals[3]
                let total = vals.reduce(0, +)
                
                if let last = lastCpuStats {
                    let totalDiff = total - last.total
                    let idleDiff = idle - last.idle
                    if totalDiff > 0 {
                        newCpuUsage = (1.0 - (idleDiff / totalDiff)) * 100.0
                    }
                }
                lastCpuStats = (idle: idle, total: total)
            }
        }
        
        // Parse Memory
        var memTotal: Double = 0
        var memFree: Double = 0
        var memBuffers: Double = 0
        var memCached: Double = 0
        
        for line in memStr.components(separatedBy: .newlines) {
            let cols = line.split(separator: " ", omittingEmptySubsequences: true)
            if cols.count >= 2 {
                let val = Double(cols[1]) ?? 0
                if cols[0] == "MemTotal:" { memTotal = val }
                else if cols[0] == "MemFree:" { memFree = val }
                else if cols[0] == "Buffers:" { memBuffers = val }
                else if cols[0] == "Cached:" { memCached = val }
            }
        }
        var memAvailable: Double = -1
        for line in memStr.components(separatedBy: .newlines) {
            let cols = line.split(separator: " ", omittingEmptySubsequences: true)
            if cols.count >= 2 {
                let val = Double(cols[1]) ?? 0
                if cols[0] == "MemAvailable:" { memAvailable = val }
            }
        }
        if memTotal > 0 {
            newMemTotal = memTotal * 1024 // Bytes
            let available = memAvailable >= 0 ? memAvailable : (memFree + memBuffers + memCached)
            newMemUsed = (memTotal - available) * 1024
        }
        
        // Parse Disk
        let dfLines = dfStr.components(separatedBy: .newlines).filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        if dfLines.count >= 2 {
            // Usually the last line is the data for /
            let lastLine = dfLines.last!
            let cols = lastLine.split(separator: " ", omittingEmptySubsequences: true)
            // Filesystem 1K-blocks Used Available Use% Mounted
            if cols.count >= 4 {
                let totalStr = cols[cols.count - 5]
                let usedStr = cols[cols.count - 4]
                if let total = Double(totalStr), let used = Double(usedStr) {
                    newDiskTotal = total * 1024
                    newDiskUsed = used * 1024
                }
            }
        }
        
        // Parse Network
        var rxTotal: Double = 0
        var txTotal: Double = 0
        for line in netStr.components(separatedBy: .newlines) {
            if line.contains(":") {
                let parts = line.split(separator: ":")
                if parts.count == 2 {
                    let interface = parts[0].trimmingCharacters(in: .whitespaces)
                    if interface != "lo" {
                        let cols = parts[1].split(separator: " ", omittingEmptySubsequences: true)
                        if cols.count >= 9 {
                            rxTotal += Double(cols[0]) ?? 0
                            txTotal += Double(cols[8]) ?? 0
                        }
                    }
                }
            }
        }
        
        if let last = lastNetStats {
            let timeDiff = currentTime - last.time
            if timeDiff > 0 {
                newRx = max(0, rxTotal - last.rx) / timeDiff
                newTx = max(0, txTotal - last.tx) / timeDiff
            }
        }
        lastNetStats = (rx: rxTotal, tx: txTotal, time: currentTime)
        
        DispatchQueue.main.async {
            if self.lastCpuStats != nil {
                self.cpuUsage = max(0, min(100, newCpuUsage))
            }
            self.memoryUsed = newMemUsed
            self.memoryTotal = newMemTotal
            self.diskUsed = newDiskUsed
            self.diskTotal = newDiskTotal
            if self.lastNetStats != nil {
                self.netRx = newRx
                self.netTx = newTx
            }
        }
    }
}

struct ServerView: View {
    let moduleId: UUID
    let configData: String
    
    @StateObject private var service: ServerMonitorService
    
    init(moduleId: UUID, configData: String) {
        self.moduleId = moduleId
        self.configData = configData
        
        var config = ServerConfig()
        if let data = configData.data(using: .utf8),
           let decoded = try? JSONDecoder().decode(ServerConfig.self, from: data) {
            config = decoded
        }
        
        _service = StateObject(wrappedValue: ServerMonitorService(id: moduleId, config: config))
    }
    
    var body: some View {
        VStack(spacing: 6) {
            Text(service.config.ip.isEmpty ? "Server Setup" : (service.config.name?.isEmpty == false ? service.config.name! : service.config.ip))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.primary.opacity(0.85))
            
            if service.config.ip.isEmpty {
                Text("Double click to configure")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else if !service.isConnected {
                Text("Connecting...")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Image(systemName: "cpu")
                            .font(.system(size: 10, weight: .bold))
                            .frame(width: 20, alignment: .leading)
                        Text(String(format: "%.1f%%", service.cpuUsage))
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                    }
                    HStack {
                        Image(systemName: "memorychip")
                            .font(.system(size: 10, weight: .bold))
                            .frame(width: 20, alignment: .leading)
                        let memPct = service.memoryTotal > 0 ? (service.memoryUsed / service.memoryTotal) * 100 : 0
                        Text("\(formatBytes(service.memoryUsed))/\(formatBytes(service.memoryTotal)) (\(String(format: "%.1f%%", memPct)))")
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                    }
                    HStack {
                        Image(systemName: "internaldrive")
                            .font(.system(size: 10, weight: .bold))
                            .frame(width: 20, alignment: .leading)
                        let diskPct = service.diskTotal > 0 ? (service.diskUsed / service.diskTotal) * 100 : 0
                        Text("\(formatBytes(service.diskUsed))/\(formatBytes(service.diskTotal)) (\(String(format: "%.1f%%", diskPct)))")
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                    }
                    HStack {
                        Image(systemName: "network")
                            .font(.system(size: 10, weight: .bold))
                            .frame(width: 20, alignment: .leading)
                        Text("↑ \(formatNet(service.netTx))/s  ↓ \(formatNet(service.netRx))/s")
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                    }
                }
                .padding(.horizontal, 4)
            }
            Spacer(minLength: 0)
        }
        .padding(8)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .contentShape(Rectangle())
        .onTapGesture(count: 2) {
            openConfigWindow()
        }
        .onAppear {
            service.start()
        }
        .onDisappear {
            service.stop()
        }
    }
    
    private func openConfigWindow() {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 350),
            styleMask: [.titled, .closable, .fullSizeContentView],
            backing: .buffered, defer: false
        )
        panel.title = "Server Configuration"
        panel.isFloatingPanel = true
        panel.center()
        
        let configView = ServerConfigView(moduleId: moduleId, service: service, onSave: {
            if let idx = ModuleStore.shared.modules.firstIndex(where: { $0.id == moduleId }) {
                if let data = try? JSONEncoder().encode(service.config),
                   let str = String(data: data, encoding: .utf8) {
                    ModuleStore.shared.modules[idx].customData = str
                }
            }
            service.start()
            panel.close()
        }, onCancel: {
            panel.close()
        })
        
        panel.contentView = NSHostingView(rootView: configView)
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    private func formatBytes(_ bytes: Double) -> String {
        if bytes == 0 { return "0G" }
        if bytes > 1_073_741_824 { return String(format: "%.1fG", bytes / 1_073_741_824) }
        if bytes > 1_048_576 { return String(format: "%.0fM", bytes / 1_048_576) }
        return String(format: "%.0fK", bytes / 1024)
    }
    
    private func formatNet(_ bytes: Double) -> String {
        if bytes > 1_048_576 { return String(format: "%.1fM", bytes / 1_048_576) }
        if bytes > 1024 { return String(format: "%.0fK", bytes / 1024) }
        return String(format: "%.0fB", bytes)
    }
}

struct ServerConfigView: View {
    let moduleId: UUID
    @ObservedObject var service: ServerMonitorService
    var onSave: () -> Void
    var onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Text("Server Configuration")
                .font(.headline)
            
            Form {
                TextField("Server Name", text: Binding(get: { service.config.name ?? "" }, set: { service.config.name = $0 }))
                TextField("IP Address", text: $service.config.ip)
                TextField("Port", text: $service.config.port)
                TextField("Username", text: $service.config.username)
                SecureField("Password", text: $service.config.password)
                
                HStack {
                    TextField("Private Key Path", text: $service.config.keyPath)
                    Button("Select") {
                        let panel = NSOpenPanel()
                        panel.allowsMultipleSelection = false
                        panel.canChooseDirectories = false
                        panel.canChooseFiles = true
                        if panel.runModal() == .OK {
                            service.config.keyPath = panel.url?.path ?? ""
                        }
                    }
                }
            }
            .padding()
            
            HStack {
                Button("Cancel") {
                    onCancel()
                }
                Button("Save") {
                    onSave()
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding()
        .frame(width: 400)
    }
}
