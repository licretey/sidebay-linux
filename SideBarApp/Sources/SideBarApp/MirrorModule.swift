import SwiftUI
import AVFoundation

struct MirrorConfig: Codable, Equatable {
    var deviceId: String = ""
}

struct MirrorModuleView: View {
    let moduleId: UUID
    let customData: String
    
    @StateObject private var cameraModel = CameraViewModel()
    @State private var showingConfig = false
    @State private var isBlack = false
    
    init(moduleId: UUID, customData: String) {
        self.moduleId = moduleId
        self.customData = customData
    }
    
    var body: some View {
        ZStack {
            if cameraModel.hasPermission {
                CameraPreviewView(session: cameraModel.session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipped()
                
                if isBlack {
                    Color.black.frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            } else {
                Text("No Camera Permission")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture(count: 2) {
            openConfigWindow()
        }
        .onTapGesture(count: 1) {
            isBlack.toggle()
        }
        .contextMenu {
            Button("Open Standalone Window") {
                openStandaloneWindow()
            }
        }
        .onAppear {
            var config = MirrorConfig()
            if let data = customData.data(using: .utf8),
               let decoded = try? JSONDecoder().decode(MirrorConfig.self, from: data) {
                config = decoded
            }
            cameraModel.config = config
            cameraModel.checkPermission()
        }
        .onDisappear {
            cameraModel.stopCamera()
        }
    }
    
    private func openConfigWindow() {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 300, height: 150),
            styleMask: [.titled, .closable, .fullSizeContentView],
            backing: .buffered, defer: false
        )
        panel.title = "Camera Selection"
        panel.isFloatingPanel = true
        panel.center()
        
        let configView = MirrorConfigView(moduleId: moduleId, cameraModel: cameraModel, onSave: {
            if let idx = ModuleStore.shared.modules.firstIndex(where: { $0.id == moduleId }) {
                if let data = try? JSONEncoder().encode(cameraModel.config),
                   let str = String(data: data, encoding: .utf8) {
                    ModuleStore.shared.modules[idx].customData = str
                }
            }
            cameraModel.setupCamera()
            panel.close()
        }, onCancel: {
            panel.close()
        })
        
        panel.contentView = NSHostingView(rootView: configView)
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func openStandaloneWindow() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 800, height: 600),
            styleMask: [.titled, .closable, .resizable, .miniaturizable, .fullSizeContentView],
            backing: .buffered, defer: false
        )
        window.title = "Mirror"
        window.center()
        
        let standaloneView = CameraPreviewView(session: cameraModel.session)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.black)
            .ignoresSafeArea()
            
        let hostingView = NSHostingView(rootView: standaloneView)
        window.contentView = hostingView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

struct MirrorConfigView: View {
    let moduleId: UUID
    @ObservedObject var cameraModel: CameraViewModel
    var onSave: () -> Void
    var onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Text("Select Camera")
                .font(.headline)
            
            Picker("Camera", selection: $cameraModel.config.deviceId) {
                ForEach(cameraModel.availableDevices, id: \.uniqueID) { device in
                    Text(device.localizedName).tag(device.uniqueID)
                }
            }
            .pickerStyle(.menu)
            
            HStack {
                Button("Cancel", action: onCancel)
                Button("Save", action: onSave)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding()
        .onAppear {
            cameraModel.fetchDevices()
            if cameraModel.config.deviceId.isEmpty, let first = cameraModel.availableDevices.first {
                cameraModel.config.deviceId = first.uniqueID
            }
        }
    }
}

class CameraViewModel: ObservableObject {
    @Published var hasPermission = false
    @Published var config = MirrorConfig()
    @Published var availableDevices: [AVCaptureDevice] = []
    
    let session = AVCaptureSession()
    
    func checkPermission() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            DispatchQueue.main.async {
                self.hasPermission = true
                self.setupCamera()
            }
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                DispatchQueue.main.async {
                    self.hasPermission = granted
                    if granted {
                        self.setupCamera()
                    }
                }
            }
        default:
            DispatchQueue.main.async {
                self.hasPermission = false
            }
        }
    }
    
    func fetchDevices() {
        let discoverySession = AVCaptureDevice.DiscoverySession(
            deviceTypes: [.builtInWideAngleCamera, .externalUnknown],
            mediaType: .video,
            position: .unspecified
        )
        DispatchQueue.main.async {
            self.availableDevices = discoverySession.devices
        }
    }
    
    func setupCamera() {
        guard hasPermission else { return }
        
        session.beginConfiguration()
        
        var selectedDevice: AVCaptureDevice?
        if !config.deviceId.isEmpty {
            selectedDevice = AVCaptureDevice(uniqueID: config.deviceId)
        }
        if selectedDevice == nil {
            selectedDevice = AVCaptureDevice.default(for: .video)
        }
        
        guard let device = selectedDevice,
              let input = try? AVCaptureDeviceInput(device: device) else {
            session.commitConfiguration()
            return
        }
        
        // Remove existing inputs
        for existingInput in session.inputs {
            session.removeInput(existingInput)
        }
        
        if session.canAddInput(input) {
            session.addInput(input)
        }
        session.commitConfiguration()
        
        if !session.isRunning {
            DispatchQueue.global(qos: .userInitiated).async {
                self.session.startRunning()
            }
        }
    }
    
    func stopCamera() {
        DispatchQueue.global(qos: .userInitiated).async {
            if self.session.isRunning {
                self.session.stopRunning()
            }
        }
    }
}

class CameraPreviewNSView: NSView {
    var previewLayer: AVCaptureVideoPreviewLayer? {
        didSet {
            oldValue?.removeFromSuperlayer()
            if let previewLayer = previewLayer {
                self.layer?.addSublayer(previewLayer)
                previewLayer.frame = self.bounds
            }
        }
    }
    
    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        self.wantsLayer = true
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    override func layout() {
        super.layout()
        previewLayer?.frame = self.bounds
    }
}

struct CameraPreviewView: NSViewRepresentable {
    let session: AVCaptureSession
    
    func makeNSView(context: Context) -> CameraPreviewNSView {
        let view = CameraPreviewNSView()
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        // Adjust for mirroring front camera if needed
        if session.inputs.first is AVCaptureDeviceInput {
            let deviceInput = session.inputs.first as! AVCaptureDeviceInput
            if deviceInput.device.position == .front {
                // Actually macOS handles this automatically, but let's just mirror anyway for normal mirror effect
                // wait, macOS front camera isn't .front, it's .unspecified or builtIn
                // For a mirror module, the user expects it to be mirrored horizontally.
            }
        }
        // Force mirror for a "mirror" module
        previewLayer.connection?.automaticallyAdjustsVideoMirroring = false
        previewLayer.connection?.isVideoMirrored = true
        
        previewLayer.videoGravity = .resizeAspectFill
        view.previewLayer = previewLayer
        return view
    }
    
    func updateNSView(_ nsView: CameraPreviewNSView, context: Context) {
        if nsView.previewLayer?.session !== session {
            let previewLayer = AVCaptureVideoPreviewLayer(session: session)
            previewLayer.connection?.automaticallyAdjustsVideoMirroring = false
            previewLayer.connection?.isVideoMirrored = true
            previewLayer.videoGravity = .resizeAspectFill
            nsView.previewLayer = previewLayer
        }
    }
}
