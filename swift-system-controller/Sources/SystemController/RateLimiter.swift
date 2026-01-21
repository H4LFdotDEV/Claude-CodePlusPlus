// RateLimiter.swift
// Claude Code++ System Controller
// Jeremiah Kroesche | Halfservers LLC

import Foundation

public class RateLimiter {
    
    private let config: RateLimitConfig
    private var clickTimestamps: [Date] = []
    private var keyCount: Int = 0
    private var keyWindowStart: Date = Date()
    private let lock = NSLock()
    
    public init(config: RateLimitConfig) {
        self.config = config
    }
    
    public func allowClick() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        
        let now = Date()
        let oneSecondAgo = now.addingTimeInterval(-1)
        
        // Remove old timestamps
        clickTimestamps = clickTimestamps.filter { $0 > oneSecondAgo }
        
        // Check limit
        if clickTimestamps.count >= config.maxClicksPerSecond {
            return false
        }
        
        clickTimestamps.append(now)
        return true
    }
    
    public func allowKeys(count: Int) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        
        let now = Date()
        
        // Reset window if more than 1 second has passed
        if now.timeIntervalSince(keyWindowStart) > 1.0 {
            keyWindowStart = now
            keyCount = 0
        }
        
        // Check if adding these keys would exceed limit
        if keyCount + count > config.maxKeysPerSecond {
            return false
        }
        
        keyCount += count
        return true
    }
    
    public func reset() {
        lock.lock()
        defer { lock.unlock() }
        
        clickTimestamps = []
        keyCount = 0
        keyWindowStart = Date()
    }
}
