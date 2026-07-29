import Foundation
import Darwin

var stats = vm_statistics64()
var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64_data_t>.size / MemoryLayout<integer_t>.size)
let result = withUnsafeMutablePointer(to: &stats) {
    $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
        host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
    }
}
print(result == KERN_SUCCESS)

var ifaddr: UnsafeMutablePointer<ifaddrs>?
guard getifaddrs(&ifaddr) == 0 else { exit(1) }
var ptr = ifaddr
while ptr != nil {
    defer { ptr = ptr?.pointee.ifa_next }
    guard let interface = ptr?.pointee else { continue }
    let name = String(cString: interface.ifa_name)
    if let data = interface.ifa_data {
        let networkData = data.assumingMemoryBound(to: if_data.self).pointee
        print("\(name) up: \(networkData.ifi_obytes)")
    }
}
freeifaddrs(ifaddr)
