// 小鹭音形 —— IMK 输入控制器。
//
// 前端逻辑移植自 ime/fcitx5/src/lufly.cpp（参照真源），方法注释标注对齐行号。
// IMK 事件模型对齐 fcitx5-macos controller.swift（Shift 判定/防误切经其实证）。
// 按键语义（lufly.cpp:10-20）:
//   a-z       进编码缓冲（6/8/10…偶数全码唯一 → 顶功挂起，下一键顶出）
//   空格      上屏首选 / 确认挂起字；编码 miss 时清屏（回车上屏英文）
//   1-5       选当前页候选；- /= Tab PageUp/Down 翻页；$/| 选次选候选
//   回车      编码字母原样上屏；退格删一码；Esc 清空缓冲
//   Shift     单击: 切换中/英文模式（编码中先原样上屏字母再转英文）
//   `         拼音反查（fuzhu 码表）
//   标点      中文全角化（编码中先顶字；上下文半角: 数字/英文后、miss、Ctrl+0）
import Cocoa
import InputMethodKit
import Carbon.HIToolbox // kVK_* 虚键码 + kTSMHiliteConvertedText

@objc(LuflyInputController)
final class LuflyInputController: IMKInputController {
    private let state = LuflyState()
    private let cand = CandidateWindow()
    /// 当前 marked text 的 UTF-16 长度（光标定位用，对齐 fcitx5-macos u16pos）
    private var preeditU16 = 0
    /// 上次事件修饰键状态（flagsChanged 按下/抬起判定，对齐 fcitx5-macos lastModifiers）
    private var lastModifiers = NSEvent.ModifierFlags(rawValue: 0)
    /// Shift 按下瞬间的应用选区（Shift+Click 选文本防误切的对比基线；
    /// 不用上次 keyDown 的值——marked text 会使 selectedRange 抖动误判）
    private var selAtShiftDown = NSRange(location: NSNotFound, length: 0)

    // 页大小对齐 fcitx5 kPageSize（lufly.cpp:63，数字 1-5 对应本页 5 个候选）
    private let pageSize = 5

    // MARK: - 生命周期

    override func activateServer(_ sender: Any!) {
        LuflyLog.shared.info("activateServer")
        LuflyEngine.shared.preload()
    }

    /// 对齐 fcitx5 LuflyIm::reset（lufly.cpp:1217-1235）:
    /// 焦点切走挂起字落地防丢，会话状态清空（ascii 跨焦点保留）
    override func deactivateServer(_ sender: Any!) {
        if !state.pending.isEmpty, let client = sender as? IMKTextInput {
            commit(client, state.pending)
        }
        state.pending = ""
        state.pendingCode = ""
        state.reset()
        if let client = sender as? IMKTextInput {
            updateUI(client)
        }
        LuflyLog.shared.info("deactivateServer")
    }

    /// IMK 默认只转发 keyDown；flagsChanged/keyUp 须显式声明
    /// （flagsChanged: Shift 切换；keyUp: $/| 抬键补标点，对齐 fcitx5 release 分支）
    override func recognizedEvents(_ sender: Any!) -> Int {
        let events: NSEvent.EventTypeMask = [.keyDown, .keyUp, .flagsChanged]
        return Int(events.rawValue)
    }

    // MARK: - 按键主链路（对齐 LuflyIm::keyEvent lufly.cpp:628-1211）

    override func handle(_ event: NSEvent!, client sender: Any!) -> Bool {
        guard let event = event, let client = sender as? IMKTextInput else {
            return false
        }

        // ---- 抬键（release）: $/| 补标点（对齐 lufly.cpp:634-648）----
        if event.type == .keyUp {
            if let punct = state.pendingPunct, event.keyCode == state.pendingPunctKey {
                state.pendingPunct = nil
                commit(client, punct)
                state.autoBuf = "" // 标点 = 断链
                state.lastCls = 0
                return true
            }
            return false
        }

        // ---- 修饰键（flagsChanged）: Shift 单击切中英 ----
        if event.type == .flagsChanged {
            return handleFlagsChanged(event, client: client)
        }
        guard event.type == .keyDown else {
            return false
        }

        // 任何其他按下键解除 Shift 单击武装（对齐 lufly.cpp:686）
        state.shiftArmed = false

        // ---- 修饰键组合（lufly.cpp:699-712）----
        let mods = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        if mods.contains(.control) {
            if event.keyCode == kVK_ANSI_0 {
                // Ctrl+0: 标点强制半角开关（对齐 rime ascii_punct）
                state.asciiPunct.toggle()
                LuflyLog.shared.info("标点\(state.asciiPunct ? "强制半角" : "跟随中文")")
                updateUI(client)
                return true
            }
            return false
        }
        if mods.contains(.option) || mods.contains(.command) {
            return false
        }

        // 英文模式: 一律透传，Shift 单击切回中文（lufly.cpp:714-716）
        if state.ascii {
            return false
        }

        // 码表未就绪 → 首键兜底同步加载；缺失则全透传（lufly.cpp:717-719）
        guard LuflyEngine.shared.ensureReady() else {
            return false
        }
        // 用户词典热重载（ojc 管线追加词后合并；对齐 checkUserReload lufly.cpp:720）
        LuflyEngine.shared.checkUserReload()

        // ---- ojc 加词·编码阶段 (stage2): 编辑编码，回车/空格确认 ----
        // （对齐 lufly.cpp:729-777）
        if state.addStage == 2 {
            if event.keyCode == kVK_Escape {
                cancelAddWord()
                updateUI(client)
                return true
            }
            if event.keyCode == kVK_Delete {
                if state.addCode.isEmpty {
                    state.addStage = 1 // 码删空: 退回选词阶段
                } else {
                    state.addCode.removeLast()
                }
                updateUI(client)
                return true
            }
            if event.keyCode == kVK_Return || event.keyCode == kVK_Space {
                if state.addCode.count < 2 {
                    updateUI(client) // 编码太短: 等待继续输入
                    return true
                }
                if LuflyEngine.shared.userAddWord(code: state.addCode, text: state.addWord) {
                    // 保存成功: 词直接上屏（立即可用）
                    let word = state.addWord
                    cancelAddWord()
                    commit(client, word)
                    state.lastCls = 0
                } else {
                    cancelAddWord()
                }
                updateUI(client)
                return true
            }
            if let c = printableChar(event), c.isASCII, c >= "a", c <= "z" {
                state.addCode.append(c)
                updateUI(client)
                return true
            }
            // 加词编辑中吞掉其他简单键，防误触（对齐 isSimple accept）
            return true
        }

        // ---- ` 进入拼音反查（对齐 lufly.cpp:779-787）----
        if !state.reverse, event.keyCode == kVK_ANSI_Grave, state.buffer.isEmpty {
            if LuflyEngine.shared.ensureRev() {
                state.reverse = true
                updateUI(client)
                return true
            }
            return false // 码表缺失: ` 透传
        }

        // 反查用 rev 引擎，普通输入用主引擎（lufly.cpp:723-727）
        let rev = state.reverse
        // 重放恢复到该会话的编码状态（lufly.cpp:790）
        LuflyEngine.shared.replay(state.buffer, rev)

        // 是否有候选 / 是否编码 miss，以刚重放的引擎为准（lufly.cpp:794-796）
        let hasMenu = LuflyEngine.shared.candidateCount(rev) > 0
        let miss = !hasMenu && !state.buffer.isEmpty
        let pc = printableChar(event)

        // ---- 翻页: PageUp/PageDown、- 前翻 = 后翻、Tab/Shift+Tab（lufly.cpp:798-858）----
        if let paging = pagingAction(event) {
            switch paging {
            case .flip:
                updateUI(client)
                return true
            case .swallow:
                return true // 到头/单页: 消费不动作（防半角 - = 漏进文档）
            case .pass:
                return false // PageUp/PageDown 非简单键，保持透传
            }
        }

        // ---- 选词: 数字 1-5 与 ; ' [ ] = 第2/3/4/5（对齐 lufly.cpp:860-902）----
        var sel = -1
        var digitSel = false
        if let c = pc, c >= "1", c <= "5" {
            sel = Int(c.unicodeScalars.first!.value - Unicode.Scalar("1").value)
            digitSel = true
        } else if pc == ";" {
            sel = 1
        } else if pc == "'" {
            sel = 2
        } else if pc == "[" {
            sel = 3
        } else if pc == "]" {
            sel = 4
        }
        if sel >= 0, !state.buffer.isEmpty, hasMenu {
            let idx = sel + state.page * pageSize
            if let text = LuflyEngine.shared.candidateText(idx, rev) {
                if state.addStage == 1 {
                    // 加词·选字阶段: 选中的字进词槽，继续选下一个字
                    appendAddWord(text)
                    updateUI(client)
                    return true
                }
                LuflyEngine.shared.learn(code: state.buffer, text: text, rev)
                noteAutoCommit(state.buffer, text)
                commit(client, text)
                state.lastCls = 0
                state.buffer = ""
                state.reverse = false
                updateUI(client)
                return true
            }
            if digitSel {
                return true // 数字越界: 消费不动作（原行为）
            }
            // ;'[] 越界: 落到标点顶字
        }

        // ---- $ / |: 选次选候选，抬键补标点（对齐 lufly.cpp:904-930）----
        if (pc == "$" || pc == "|"), !state.buffer.isEmpty, hasMenu {
            let idx = 1 + state.page * pageSize
            if let text = LuflyEngine.shared.candidateText(idx, rev) {
                if state.addStage == 1 {
                    appendAddWord(text)
                    updateUI(client)
                    return true
                }
                LuflyEngine.shared.learn(code: state.buffer, text: text, rev)
                noteAutoCommit(state.buffer, text)
                commit(client, text)
                state.lastCls = 0
                state.buffer = ""
                state.reverse = false
                state.pendingPunct = pc == "$" ? "。" : "，"
                state.pendingPunctKey = event.keyCode
                updateUI(client)
                return true
            }
        }

        // ---- 空格（lufly.cpp:932-982）----
        if event.keyCode == kVK_Space {
            if state.buffer.isEmpty {
                if !state.pending.isEmpty {
                    if state.addStage == 1 {
                        // 加词中: 挂起字进词槽（不能漏进文档）
                        state.addWord += state.pending
                    } else {
                        // 空格确认挂起字（空格被消费，不会漏成真空格）
                        LuflyEngine.shared.learn(code: state.pendingCode, text: state.pending)
                        noteAutoCommit(state.pendingCode, state.pending)
                        commit(client, state.pending)
                    }
                    state.pending = ""
                    state.pendingCode = ""
                    state.lastCls = 0
                    updateUI(client)
                    return true
                }
                if state.reverse {
                    state.reverse = false // 反查空缓冲: 空格退出反查
                    updateUI(client)
                    return true
                }
                return false // 空缓冲透传
            }
            let code = state.buffer
            if let text = LuflyEngine.shared.key(UInt32(Unicode.Scalar(" ").value), rev) {
                if state.addStage == 1 {
                    // 加词·选字阶段: 空格选中首选进词槽，不提交
                    appendAddWord(text)
                    updateUI(client)
                    return true
                }
                // miss 时引擎返回 None → 只清屏不上屏
                LuflyEngine.shared.learn(code: code, text: text, rev)
                noteAutoCommit(code, text)
                commit(client, text)
            }
            state.buffer = ""
            state.reverse = false
            state.lastCls = 0
            updateUI(client)
            return true
        }

        // ---- 回车（lufly.cpp:984-1032）----
        if event.keyCode == kVK_Return {
            if state.addStage == 1 {
                if !state.buffer.isEmpty {
                    // 加词·选字阶段: 编码中回车 = 反悔（字母上屏退出）
                    cancelAddWord()
                    commit(client, state.buffer)
                    state.lastCls = 2
                    state.buffer = ""
                    updateUI(client)
                    return true
                }
                // 空缓冲: 挂起字进词槽，完成选字 → 编码阶段
                if !state.pending.isEmpty {
                    state.addWord += state.pending
                    state.pending = ""
                    state.pendingCode = ""
                }
                if state.addWord.isEmpty {
                    cancelAddWord() // 一个字都没选: 视为取消
                } else {
                    finishAddWord()
                }
                state.reverse = false
                updateUI(client)
                return true
            }
            if state.buffer.isEmpty {
                if !state.pending.isEmpty {
                    // 挂起字先送出，Enter 本身不消费（换行照常，顺序正确）
                    commit(client, state.pending)
                    state.pending = ""
                    state.pendingCode = ""
                    state.autoBuf = "" // 回车换行 = 断链
                    updateUI(client)
                }
                return false
            }
            commit(client, state.buffer) // 编码字母原样上屏
            state.lastCls = 2
            state.buffer = ""
            state.reverse = false
            updateUI(client)
            return true
        }

        // ---- 退格（lufly.cpp:1034-1077）----
        if event.keyCode == kVK_Delete {
            if state.buffer.isEmpty {
                if !state.pending.isEmpty {
                    // 撤销顶功挂起: 恢复原编码供继续编辑
                    state.buffer = state.pendingCode
                    state.pending = ""
                    state.pendingCode = ""
                    LuflyEngine.shared.replay(state.buffer, false)
                    updateUI(client)
                    return true
                }
                if state.reverse {
                    state.reverse = false // 退过 ` 本身: 退出反查
                    updateUI(client)
                    return true
                }
                if state.addStage == 1 {
                    if !state.addWord.isEmpty {
                        state.addWord.removeLast() // 删词槽最后一个字
                    } else {
                        cancelAddWord() // 退无可退: 退出加词
                    }
                    updateUI(client)
                    return true
                }
                return false // 真删字符
            }
            _ = LuflyEngine.shared.key(8, rev) // \b
            state.buffer = LuflyEngine.shared.input(rev)
            updateUI(client)
            return true
        }

        // ---- Esc（lufly.cpp:1079-1100）----
        if event.keyCode == kVK_Escape {
            if !state.buffer.isEmpty {
                state.buffer = ""
                state.reverse = false
                cancelAddWord() // 清空缓冲（rime send Escape）
                updateUI(client)
                return true
            }
            if state.addStage == 1 {
                cancelAddWord() // 选字中 Esc: 取消加词
                updateUI(client)
                return true
            }
            if state.reverse {
                state.reverse = false
                updateUI(client)
            }
            return false
        }

        // ---- 字母 a-z 进编码缓冲（lufly.cpp:1102-1136）----
        if let c = printableChar(event), c.isASCII, c >= "a", c <= "z" {
            let ch = UInt32(c.asciiValue!)
            if !state.pending.isEmpty {
                // 顶功: 下一字词的首键把挂起字顶出（快打全程不用空格）
                commit(client, state.pending)
                state.pending = ""
                state.pendingCode = ""
                state.lastCls = 0
            }
            let prev = state.buffer
            if let text = LuflyEngine.shared.key(ch, rev) {
                // 全码唯一: 不立即发送，挂起等顶出/空格确认（顶功）
                state.pending = text
                state.pendingCode = prev + String(c)
            }
            state.buffer = LuflyEngine.shared.input(rev)
            // ojc: 命令引导符 o + jc(加词声母) → 进入加词·选词阶段（码表无
            // o 开头编码，与正常打字零冲突；对齐 lufly.cpp:1125-1132）
            if state.buffer == "ojc" {
                state.buffer = ""
                state.reverse = false
                state.addStage = 1
                LuflyEngine.shared.replay(state.buffer, rev)
            }
            updateUI(client)
            return true
        }

        // ---- 标点: 中文全角化（lufly.cpp:1138-1176）----
        // 上下文半角: 前一字符是数字/英文、miss、或 Ctrl+0 强制时，标点不映射、
        // 原样透传（编码中仍先顶字）—— 3.14 / hello. / english,
        if state.addStage == 1 {
            state.addStage = 0 // 标点退出加词（视为反悔），照常处理标点
        }
        let composing = !state.buffer.isEmpty
        let halfPunct = state.asciiPunct || state.lastCls != 0 || miss
        var punct: String? = nil
        if let c = pc, !halfPunct {
            punct = chinesePunct(c, dqOpen: &state.dqOpen, sqOpen: &state.sqOpen)
        }
        if let punct = punct {
            if !state.pending.isEmpty {
                // 挂起字随标点顶出
                noteAutoCommit(state.pendingCode, state.pending)
                commit(client, state.pending)
                state.pending = ""
                state.pendingCode = ""
            }
            if miss {
                commit(client, state.buffer) // 英文原样上屏
            } else if composing {
                let code = state.buffer
                if let text = LuflyEngine.shared.key(UInt32(Unicode.Scalar(" ").value), rev) {
                    LuflyEngine.shared.learn(code: code, text: text, rev)
                    noteAutoCommit(code, text)
                    commit(client, text)
                }
            }
            state.buffer = ""
            state.reverse = false
            commit(client, punct)
            state.autoBuf = "" // 标点 = 断链
            state.lastCls = 0
            updateUI(client)
            return true
        }

        // ---- 未映射的简单键（lufly.cpp:1177-1210）----
        // miss 时透传不清屏（英文继续）；编码中顶出首选后放行原字符。
        if composing {
            if miss {
                // 英文原样上屏，标点等符号不消费、半角自然插入
                commit(client, state.buffer)
                state.buffer = ""
                state.reverse = false
                state.lastCls = 2
                state.autoBuf = "" // 英文 = 断链
                updateUI(client)
                return false
            }
            let code = state.buffer
            if let text = LuflyEngine.shared.key(UInt32(Unicode.Scalar(" ").value), rev) {
                LuflyEngine.shared.learn(code: code, text: text, rev)
                noteAutoCommit(code, text)
                commit(client, text)
            }
            state.buffer = ""
            state.reverse = false
            state.lastCls = 0
            state.autoBuf = "" // 透传的原字符插在字间 = 断链
            updateUI(client)
            // 不消费，让原字符自然插入
            return false
        }
        // 空缓冲透传的数字: 记录上下文（3.14 / 1,000 后续标点保持半角）
        if let c = pc, c >= "0", c <= "9" {
            state.lastCls = 1
        }
        return false
    }

    // MARK: - 自动造词（对齐 LuflyIm::noteAutoCommit lufly.cpp:387-412）

    /// 用户连续以 4 键全码打字上屏时，把这些字拼成自动词（≥2 字成词，
    /// 上限 4 字）。其余任何上屏断链。走 user_add_word: rank0/计数1/落盘。
    private func noteAutoCommit(_ code: String, _ text: String) {
        guard code.count == 4, text.count == 1 else {
            state.autoBuf = ""
            return
        }
        state.autoBuf += text
        let n = state.autoBuf.count
        if n < 2 {
            return
        }
        if n > 4 { // 词长上限 4 字，超长断链防串词
            state.autoBuf = ""
            return
        }
        if let d = LuflyEngine.shared.deriveWord(state.autoBuf) {
            _ = LuflyEngine.shared.userAddWord(code: d, text: state.autoBuf)
        }
    }

    // MARK: - ojc 加词（对齐 LuflyIm appendAddWord/finishAddWord/cancelAddWord
    //         lufly.cpp:361-385）

    /// 加词·选字: 选中候选追加进词槽，留在选字阶段继续选下一个字；
    /// 反查选中后一并退出反查
    private func appendAddWord(_ text: String) {
        state.addWord += text
        state.buffer = ""
        state.reverse = false
        state.addStage = 1
    }

    /// 选字完成 → 编码阶段: 推导默认码（固定查主码表，反查态的引擎是 fuzhu）
    private func finishAddWord() {
        state.addCode = LuflyEngine.shared.deriveWord(state.addWord) ?? ""
        state.buffer = ""
        state.reverse = false
        state.addStage = 2
    }

    /// 退出/取消加词模式
    private func cancelAddWord() {
        state.addStage = 0
        state.addWord = ""
        state.addCode = ""
        state.autoBuf = ""
    }

    // MARK: - Shift 单击切中英（对齐 lufly.cpp:634-695 + fcitx5-macos 防误切）

    private func handleFlagsChanged(_ event: NSEvent, client: IMKTextInput) -> Bool {
        let mods = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        // 本次变化的修饰位；此前有、现在无 = 抬起（对齐 fcitx5-macos change/isRelease）
        let change = NSEvent.ModifierFlags(rawValue: mods.rawValue ^ lastModifiers.rawValue)
        let isRelease = (lastModifiers.rawValue & change.rawValue) != 0
        var handled = false
        if !change.isDisjoint(with: [.shift]) {
            handled = processShift(event.keyCode, mods, isRelease, client: client)
        }
        lastModifiers = mods
        return handled
    }

    private func processShift(
        _ keyCode: UInt16, _ mods: NSEvent.ModifierFlags, _ isRelease: Bool,
        client: IMKTextInput
    ) -> Bool {
        guard keyCode == kVK_Shift || keyCode == kVK_RightShift else {
            return false
        }
        if !isRelease {
            // 按下: 仅当 Shift 是唯一修饰（可带 CapsLock）时武装单击
            // （对齐 fcitx5-macos modsVal == shift 判定）
            let pure = mods == .shift || mods == [.shift, .capsLock]
            state.shiftArmed = pure
            if pure {
                selAtShiftDown = client.selectedRange()
            }
            return false
        }
        // 抬起: 武装中才可能是单击
        guard state.shiftArmed else {
            return false
        }
        state.shiftArmed = false

        // Shift+Click 改变了选区 → 是选择操作不是单击，不切换。
        // 仅在无编码/无挂起时检查: marked text 会使 selectedRange 在按键与
        // flagsChanged 之间抖动，编码中误拦 Shift 单击（fcitx5 语义: 编码中
        // Shift 单击 = 字母上屏转英文，是明确意图）。
        if state.buffer.isEmpty && state.pending.isEmpty {
            let newSel = client.selectedRange()
            if selAtShiftDown.location != NSNotFound, newSel.location != NSNotFound,
               selAtShiftDown != newSel {
                LuflyLog.shared.info("Shift 抬起选区已变（疑似选择操作）不切换")
                return false
            }
        }

        // ---- 切换（对齐 lufly.cpp:652-681）----
        if !state.buffer.isEmpty {
            // 编码中先原样上屏字母再转英文（定向切换）
            commit(client, state.buffer)
            state.lastCls = 2
            state.buffer = ""
            state.reverse = false
            state.ascii = true
            LuflyLog.shared.info("切换到英文模式")
            StatusWindow.shared.flash(ascii: true)
            updateUI(client)
            return false
        }
        if !state.pending.isEmpty {
            // 挂起字随模式切换落地
            commit(client, state.pending)
            state.pending = ""
            state.pendingCode = ""
        }
        state.autoBuf = "" // 切英文模式 = 断链
        state.reverse = false
        state.lastCls = 0
        state.ascii.toggle()
        LuflyLog.shared.info("切换到\(state.ascii ? "英文" : "中文")模式")
        StatusWindow.shared.flash(ascii: state.ascii)
        updateUI(client)
        return false
    }

    // MARK: - 翻页（对齐 lufly.cpp:798-858）

    private enum PagingAction { case flip, swallow, pass }

    /// nil = 非翻页键
    private func pagingAction(_ event: NSEvent) -> PagingAction? {
        guard !state.buffer.isEmpty else { return nil }
        let total = LuflyEngine.shared.candidateCount(state.reverse)
        let hasNext = (state.page + 1) * pageSize < total
        let hasPrev = state.page > 0

        let shiftHeld = event.modifierFlags.contains(.shift)
        // - = 用字符判定（跨布局稳）；Page/Tab 用虚键码
        let isMinus = printableChar(event) == "-"
        let isEqual = printableChar(event) == "="
        let pagePrev = event.keyCode == kVK_PageUp || isMinus
            || (event.keyCode == kVK_Tab && shiftHeld)
        let pageNext = event.keyCode == kVK_PageDown || isEqual
            || (event.keyCode == kVK_Tab && !shiftHeld)
        guard pagePrev || pageNext else {
            return nil
        }
        if (pageNext && hasNext) || (pagePrev && hasPrev) {
            state.page += pageNext ? 1 : -1
            return .flip
        }
        // - = Tab 到头/单页: 消费不动作；PageUp/PageDown 保持透传（lufly.cpp:821-827）
        return (hasMenuCheck() && event.keyCode != kVK_PageUp && event.keyCode != kVK_PageDown)
            ? .swallow : .pass
    }

    private func hasMenuCheck() -> Bool {
        LuflyEngine.shared.candidateCount(state.reverse) > 0
    }

    // MARK: - UI（对齐 LuflyIm::updateUI lufly.cpp:487-603）

    private func updateUI(_ client: IMKTextInput) {
        let eng = LuflyEngine.shared
        let rev = state.reverse
        if state.buffer.isEmpty {
            // ojc 加词·编码阶段: 显示词与编码（可编辑），回车/空格确认
            if state.addStage == 2 {
                setPreedit(client, "加词:\(state.addWord) · 编码:\(state.addCode)")
                cand.showAux("回车/空格确认 · 退格删码(退空回选词) · Esc 取消",
                             at: caretRect(client))
                return
            }
            // 加词·选字阶段空缓冲: 词槽（已选的字）+ 操作提示（fcitx5 setAuxUp）
            if state.addStage == 1 {
                setPreedit(client, "加词:\(state.addWord)")
                cand.showAux("输入新词 · 回车完成保存 · 退格删字 · Esc 取消",
                             at: caretRect(client))
                return
            }
            var preedit = ""
            if rev {
                // 裸 ` 已按下、还没输入拼音: 只显示模式提示
                preedit = "`"
            }
            if !state.pending.isEmpty {
                // 顶功挂起: 已选字显示在光标处（预编辑），但还没发给应用
                preedit += state.pending
            }
            setPreedit(client, preedit)
            if rev {
                cand.showAux("拼音", at: caretRect(client)) // fcitx5 setAuxUp("拼音")
            } else {
                cand.hide()
            }
            return
        }

        // 编码字母跟随光标内联显示；加词前缀 → ` 前缀（反查）→ 挂起字 → 编码
        // （顺序对齐 lufly.cpp:551-561）
        var preedit = ""
        if state.addStage == 1 {
            preedit += "加词:\(state.addWord)\(state.addWord.isEmpty ? "" : "·")"
        }
        if rev {
            preedit += "`"
        }
        preedit += state.pending + eng.input(rev)
        setPreedit(client, preedit)

        // 候选窗: 当前页（翻页 page 偏移），「序号.词 + 剩余编码」；反查带"拼音"提示
        let total = eng.candidateCount(rev)
        let start = state.page * pageSize
        var items: [(text: String, code: String)] = []
        for i in start..<min(start + pageSize, total) {
            if let t = eng.candidateText(i, rev), let code = eng.candidateCode(i, rev) {
                items.append((t, code))
            }
        }
        cand.show(items, typed: state.buffer, aux: rev ? "拼音" : nil, at: caretRect(client))
    }

    /// marked text 下划线属性取系统样式（对齐 fcitx5-macos setPreedit）
    private func setPreedit(_ client: IMKTextInput, _ preedit: String) {
        preeditU16 = preedit.utf16.count
        let mark = self.mark(forStyle: kTSMHiliteConvertedText,
                             at: NSRange(location: NSNotFound, length: 0))
        let attrs = (mark as? [NSAttributedString.Key: Any]) ?? [:]
        client.setMarkedText(
            NSMutableAttributedString(string: preedit, attributes: attrs),
            selectionRange: NSRange(location: preeditU16, length: 0),
            replacementRange: NSRange(location: NSNotFound, length: 0))
    }

    /// 光标屏幕矩形（对齐 fcitx5-macos getCaretCoordinates）
    private func caretRect(_ client: IMKTextInput) -> NSRect {
        var rect = NSRect.zero
        // 末尾时回退一个字符取（n 字符只有 n 个可取位置，取 n 返回 0 矩形）
        let idx = preeditU16 > 0 ? preeditU16 - 1 : 0
        client.attributes(forCharacterIndex: idx, lineHeightRectangle: &rect)
        return rect
    }

    /// 上屏（对齐 fcitx5-macos commitString: NSNotFound = 替换整个 marked 区）
    private func commit(_ client: IMKTextInput, _ text: String) {
        client.insertText(
            NSAttributedString(string: text),
            replacementRange: NSRange(location: NSNotFound, length: 0))
        preeditU16 = 0
    }

    /// 可打印单字符（无组合修饰键效果），功能键/控制字符返回 nil
    private func printableChar(_ event: NSEvent) -> Character? {
        guard let chars = event.characters, chars.count == 1 else {
            return nil
        }
        let c = chars.first!
        guard let value = c.unicodeScalars.first?.value, value >= 0x20 else {
            return nil // 控制字符（\t \r \u{7F} 等）不算可打印
        }
        return c
    }
}
