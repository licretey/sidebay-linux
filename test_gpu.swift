import Foundation
import IOKit

func getGPUUsage() {
    let matchingDict = IOServiceNameMatching("IntelAccelerator") // This is for Intel. For Apple Silicon: "AGXAccelerator" or just class "IOAccelerator"
    // Actually, creating the dictionary directly:
    let classDict = [ "IOProviderClass": "IOAccelerator" ] as CFDictionary
    
    var iterator: io_iterator_t = 0
    let result = IOServiceGetMatchingServices(kIOMasterPortDefault, classDict, &iterator)
    
    if result == KERN_SUCCESS {
        var service = IOIteratorNext(iterator)
        while service != 0 {
            var props: Unmanaged<CFMutableDictionary>?
            if IORegistryEntryCreateCFProperties(service, &props, kCFAllocatorDefault, 0) == KERN_SUCCESS {
                if let dict = props?.takeRetainedValue() as? [String: Any] {
                    if let perfStats = dict["PerformanceStatistics"] as? [String: Any] {
                        print("Found stats: \(perfStats)")
                    }
                }
            }
            IOObjectRelease(service)
            service = IOIteratorNext(iterator)
        }
        IOObjectRelease(iterator)
    }
}

getGPUUsage()
