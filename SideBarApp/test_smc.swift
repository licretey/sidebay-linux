import Foundation
import IOKit

public struct SMC {
    public static let shared = SMC()
    private var conn: io_connect_t = 0
    
    private init() {
        let service = IOServiceGetMatchingService(0, IOServiceMatching("AppleSMC"))
        if service != 0 {
            IOServiceOpen(service, mach_task_self_, 0, &conn)
            IOObjectRelease(service)
        }
    }
    
    public func getNumFans() -> Int {
        let data = readKey("FNum")
        if data.keyInfo.dataType == getDataType("ui8 ") {
            return Int(data.bytes.0)
        }
        return 0
    }
    
    public func getFanRPM(fanIndex: Int) -> Int {
        let key = String(format: "F%dAc", fanIndex)
        let data = readKey(key)
        
        print("Fan \(fanIndex) data type: \(String(cString: [UInt8(data.keyInfo.dataType >> 24), UInt8((data.keyInfo.dataType >> 16) & 0xff), UInt8((data.keyInfo.dataType >> 8) & 0xff), UInt8(data.keyInfo.dataType & 0xff), 0]))")
        
        if data.keyInfo.dataType == getDataType("fpe2") {
            let val = (UInt16(data.bytes.0) << 8) + UInt16(data.bytes.1)
            return Int(val >> 2)
        }
        if data.keyInfo.dataType == getDataType("flt ") {
            var val: Float = 0.0
            var bytes = [data.bytes.0, data.bytes.1, data.bytes.2, data.bytes.3]
            memcpy(&val, &bytes, 4)
            return Int(val)
        }
        return 0
    }
    
    private func getDataType(_ typeStr: String) -> UInt32 {
        let bytes = Array(typeStr.utf8)
        guard bytes.count == 4 else { return 0 }
        return (UInt32(bytes[0]) << 24) | (UInt32(bytes[1]) << 16) | (UInt32(bytes[2]) << 8) | UInt32(bytes[3])
    }
    
    private func getKeyCode(_ key: String) -> UInt32 {
        return getDataType(key)
    }
    
    private func readKey(_ key: String) -> SMCKeyData_t {
        var inputStruct = SMCKeyData_t()
        var outputStruct = SMCKeyData_t()
        
        inputStruct.key = getKeyCode(key)
        inputStruct.data8 = 9 // kSMCReadKeyInfo
        
        let inputSize = MemoryLayout<SMCKeyData_t>.stride
        var outputSize = MemoryLayout<SMCKeyData_t>.stride
        
        _ = IOConnectCallStructMethod(conn, 2, &inputStruct, inputSize, &outputStruct, &outputSize)
        
        inputStruct.keyInfo = outputStruct.keyInfo
        inputStruct.data8 = 5 // kSMCReadValue
        
        _ = IOConnectCallStructMethod(conn, 2, &inputStruct, inputSize, &outputStruct, &outputSize)
        
        return outputStruct
    }
}

public struct SMCKeyData_vers_t {
    var major: UInt8 = 0
    var minor: UInt8 = 0
    var build: UInt8 = 0
    var reserved: UInt8 = 0
    var release: UInt16 = 0
}

public struct SMCKeyData_pLvl_t {
    var cpuPLimit: UInt16 = 0
    var gpuPLimit: UInt16 = 0
    var memPLimit: UInt16 = 0
}

public struct SMCKeyData_keyInfo_t {
    var dataSize: UInt32 = 0
    var dataType: UInt32 = 0
    var dataAttributes: UInt8 = 0
}

public struct SMCKeyData_t {
    var key: UInt32 = 0
    var vers = SMCKeyData_vers_t()
    var pLvl = SMCKeyData_pLvl_t()
    var keyInfo = SMCKeyData_keyInfo_t()
    var result: UInt8 = 0
    var status: UInt8 = 0
    var data8: UInt8 = 0
    var data32: UInt32 = 0
    var bytes: (UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8,
                UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8,
                UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8,
                UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8) =
        (0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
}

let smc = SMC.shared
let numFans = smc.getNumFans()
print("Num fans: \(numFans)")
for i in 0..<numFans {
    print("Fan \(i) RPM: \(smc.getFanRPM(fanIndex: i))")
}
