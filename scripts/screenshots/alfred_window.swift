// Print "<window-id> <x> <y> <width> <height>" for Alfred's visible search
// window, or exit 1 if it is not on screen. Used by scripts/screenshots.sh.
//
// Owner names are readable without Screen Recording permission; capturing the
// window afterwards (screencapture -l) is what needs it.
import CoreGraphics
import Foundation

let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    exit(1)
}

// Alfred's search window is the largest on-screen window owned by "Alfred"
// (the menu-bar item is a small separate window).
var best: (id: Int, x: Int, y: Int, w: Int, h: Int)?
for window in windows {
    guard (window[kCGWindowOwnerName as String] as? String) == "Alfred",
          let id = window[kCGWindowNumber as String] as? Int,
          let boundsDict = window[kCGWindowBounds as String] as? NSDictionary,
          let bounds = CGRect(dictionaryRepresentation: boundsDict as CFDictionary),
          bounds.height > 40
    else { continue }
    let area = Int(bounds.width * bounds.height)
    if best == nil || area > best!.w * best!.h {
        best = (id, Int(bounds.minX), Int(bounds.minY), Int(bounds.width), Int(bounds.height))
    }
}

guard let found = best else { exit(1) }
print("\(found.id) \(found.x) \(found.y) \(found.w) \(found.h)")
