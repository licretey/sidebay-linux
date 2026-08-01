import SwiftUI
import AVFoundation

struct MirrorModuleView: View {
    let moduleId: UUID
    let customData: String
    
    @StateObject private var cameraModel = CameraViewModel()
    
    var body: some View {
        ZStack {
            if cameraModel.hasPermission {
                CameraPreviewView(session: cameraModel.session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipped()
            } else {
                Text("No Camera Permission")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .onAppear {
            cameraModel.checkPermission()
        }
        .onDisappear {
            cameraModel.stopCamera()
        }
    }
}

class CameraViewModel: ObservableObject {
    @Published var hasPermission = false
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
    
    private func setupCamera() {
        guard !session.isRunning else { return }
        
        session.beginConfiguration()
        guard let device = AVCaptureDevice.default(for: .video),
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
        
        DispatchQueue.global(qos: .userInitiated).async {
            self.session.startRunning()
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
        previewLayer.videoGravity = .resizeAspectFill
        view.previewLayer = previewLayer
        return view
    }
    
    func updateNSView(_ nsView: CameraPreviewNSView, context: Context) {
        if nsView.previewLayer?.session !== session {
            let previewLayer = AVCaptureVideoPreviewLayer(session: session)
            previewLayer.videoGravity = .resizeAspectFill
            nsView.previewLayer = previewLayer
        }
    }
}
