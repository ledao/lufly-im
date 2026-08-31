// Rust 引擎（lufly-capi）的 Swift 包装。
//
// 加载策略对齐 TSF 端: 启动后台预载，首键兜底同步加载。
// 重放模型对齐 fcitx5（lufly.cpp:480 replay）: 引擎是确定性状态机，
// 每键前把 IC 缓冲重放进去。macOS 单焦点其实可持久持有引擎不重放，
// 但保持与参照真源同构，对齐审计容易（重放 ≤10 次 key() 调用，微秒级）。
// 双引擎对齐 fcitx5（scratch_/rev_ lufly.cpp:227-228）: 主码表 + 拼音反查。
import Foundation

final class LuflyEngine {
    static let shared = LuflyEngine()

    private var handle: OpaquePointer?
    private var revHandle: OpaquePointer? // 反查码表（懒加载，无热更新）
    private let lock = NSLock()
    private var loadAttempted = false
    private var triedRev = false

    var ready: Bool {
        lock.lock(); defer { lock.unlock() }
        return handle != nil
    }

    private var revReady: Bool {
        lock.lock(); defer { lock.unlock() }
        return revHandle != nil
    }

    /// 启动时后台预载（43MB 码表约 150-300ms），首键零延迟
    func preload() {
        DispatchQueue.global(qos: .userInitiated).async { [self] in
            _ = loadBlocking()
        }
    }

    /// 首键兜底: 未就绪时同步加载。false = 码表缺失/损坏（按键全透传）
    @discardableResult
    func ensureReady() -> Bool {
        if ready { return true }
        return loadBlocking()
    }

    /// 反查码表懒加载（对齐 fcitx5 LuflyIm::ensureRev lufly.cpp:414-452）:
    /// 首次按 ` 时才读。false = fuzhu.bin 缺失（` 透传）
    @discardableResult
    func ensureRev() -> Bool {
        if revReady { return true }
        lock.lock()
        if triedRev { lock.unlock(); return false }
        triedRev = true
        lock.unlock()

        guard let url = Bundle.main.url(forResource: "fuzhu", withExtension: "bin"),
              let data = try? Data(contentsOf: url) else {
            LuflyLog.shared.error("未找到反查码表（bundle Resources/fuzhu.bin）")
            return false
        }
        let bytes = [UInt8](data)
        let h = bytes.withUnsafeBufferPointer { buf -> OpaquePointer? in
            guard let base = buf.baseAddress else { return nil }
            return lufly_new(base, buf.count)
        }
        lock.lock()
        revHandle = h
        lock.unlock()
        if h == nil {
            LuflyLog.shared.error("反查码表解析失败 fuzhu.bin")
            return false
        }
        LuflyLog.shared.info("反查码表加载成功 \(data.count) 字节")
        return true
    }

    private func loadBlocking() -> Bool {
        lock.lock()
        if handle != nil { lock.unlock(); return true }
        if loadAttempted { lock.unlock(); return false }
        loadAttempted = true
        lock.unlock()

        guard let url = Bundle.main.url(forResource: "dict", withExtension: "bin"),
              let data = try? Data(contentsOf: url) else {
            LuflyLog.shared.error("码表读取失败（bundle Resources/dict.bin）")
            return false
        }
        let bytes = [UInt8](data)
        let h = bytes.withUnsafeBufferPointer { buf -> OpaquePointer? in
            guard let base = buf.baseAddress else { return nil }
            return lufly_new(base, buf.count)
        }
        lock.lock()
        handle = h
        lock.unlock()
        if h == nil {
            LuflyLog.shared.error("码表解析失败 dict.bin")
            return false
        }
        LuflyLog.shared.info("码表加载成功 \(data.count) 字节")
        openUserDict()
        return true
    }

    /// 用户词典: ~/Library/Application Support/lufly/user_dict.txt
    /// （对齐 fcitx5 端 XDG 数据目录 lufly/user_dict.txt 的定位习惯）
    private func openUserDict() {
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = appSupport.appendingPathComponent("lufly", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let path = dir.appendingPathComponent("user_dict.txt").path
        lufly_user_open(handle, path.cString(using: .utf8))
        userPath = path
        if let attrs = try? FileManager.default.attributesOfItem(atPath: path) {
            userMtime = attrs[.modificationDate] as? Date ?? userMtime
            userSize = (attrs[.size] as? NSNumber)?.intValue ?? 0
        }
        LuflyLog.shared.info("用户词典 \(path)")
    }

    // MARK: - 热重载（对齐 fcitx5 checkUserReload/checkDictReload lufly.cpp:337-478）

    private var userPath: String?
    private var userMtime = Date(timeIntervalSince1970: 0)
    private var userSize = 0
    /// 节流: 1s 内只 stat 一次
    private var lastUserCheck = Date.distantPast

    /// ojc 弹窗管线追加自定义词后合并（有 1s 节流）。有变化返回 true
    @discardableResult
    func checkUserReload() -> Bool {
        guard let path = userPath else { return false }
        let now = Date()
        guard now.timeIntervalSince(lastUserCheck) >= 1.0 else { return false }
        lastUserCheck = now
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: path) else {
            return false
        }
        let mtime = attrs[.modificationDate] as? Date ?? userMtime
        let size = (attrs[.size] as? NSNumber)?.intValue ?? 0
        guard mtime != userMtime || size != userSize else { return false }
        userMtime = mtime
        userSize = size
        let changed = lufly_user_reload(handle) != 0
        if changed {
            LuflyLog.shared.info("用户词典已热更新 \(path)")
        }
        return changed
    }

    // MARK: - 按键操作（主线程调用，对齐 fcitx5 LuflyIm 的调用方式）
    // rev 参数对齐 fcitx5 的 eng 指针切换（reverse ? rev_ : scratch_）

    private func eng(_ rev: Bool) -> OpaquePointer? {
        rev ? revHandle : handle
    }

    /// 清空编码缓冲（composition 被终止）
    func reset(_ rev: Bool = false) { lufly_reset(eng(rev)) }

    /// 喂入一个按键（Unicode 码位），返回需上屏的文本
    func key(_ ch: UInt32, _ rev: Bool = false) -> String? {
        lufly_key(eng(rev), ch).map { String(cString: $0) }
    }

    /// 当前编码缓冲（预编辑串）
    func input(_ rev: Bool = false) -> String {
        String(cString: lufly_input(eng(rev)))
    }

    func candidateCount(_ rev: Bool = false) -> Int {
        Int(lufly_candidate_count(eng(rev)))
    }

    func candidateText(_ i: Int, _ rev: Bool = false) -> String? {
        lufly_candidate_text(eng(rev), Int32(i)).map { String(cString: $0) }
    }

    func candidateCode(_ i: Int, _ rev: Bool = false) -> String? {
        lufly_candidate_code(eng(rev), Int32(i)).map { String(cString: $0) }
    }

    /// 该候选是否编码完全命中（非前缀扩展）
    func candidateExact(_ i: Int, _ rev: Bool = false) -> Bool {
        lufly_candidate_exact(eng(rev), Int32(i)) != 0
    }

    /// 记录一次真实上屏（词频自学习）
    func learn(code: String, text: String, _ rev: Bool = false) {
        lufly_learn(eng(rev), code.cString(using: .utf8), text.cString(using: .utf8))
    }

    /// 把编码缓冲重放进引擎（对齐 fcitx5 LuflyIm::replay lufly.cpp:480-485）
    func replay(_ buffer: String, _ rev: Bool = false) {
        reset(rev)
        for b in buffer.utf8 {
            _ = key(UInt32(b), rev)
        }
    }

    // MARK: - 造词（对齐 fcitx5 noteAutoCommit 用的 capi 接口）

    /// 推导一个词的默认全码（单字=4码全码；多字=双拼+首末形码各1）
    func deriveWord(_ word: String) -> String? {
        lufly_derive_word(handle, word.cString(using: .utf8)).map { String(cString: $0) }
    }

    /// 添加自定义词（立即生效并落盘）。成功返回 true
    func userAddWord(code: String, text: String) -> Bool {
        lufly_user_add_word(handle, code.cString(using: .utf8), text.cString(using: .utf8)) != 0
    }
}
