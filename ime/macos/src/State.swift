// 输入会话状态 —— 与 fcitx5 前端 LuflyState（lufly.cpp:66-97）/ tsf state.rs
// 逐字段对齐。macOS 单焦点，全局一份；字段随阶段推进补齐。
final class LuflyState {
    /// 编码缓冲（引擎 input 之外前端再留一份，miss 时引擎也持有）。
    /// 变化 = 候选列表重建，翻页归零（对齐 fcitx5 每键重建候选列表的语义，
    /// 否则上一个词翻过的页残留到下一个词，会切错页甚至空页）
    var buffer = "" {
        didSet {
            if buffer != oldValue { page = 0 }
        }
    }
    /// 反查模式: ` 已按下（阶段5）。切换 = 换引擎候选重建，翻页归零
    var reverse = false {
        didSet {
            if reverse != oldValue { page = 0 }
        }
    }
    /// 英文直通模式（Shift 单击切换）
    var ascii = false
    /// Shift 已按下且其后无其他按键（单击切中英）
    var shiftArmed = false
    /// 顶功挂起: 全码唯一已自动选字、但未发送，等下一键顶出/空格确认
    var pending = ""
    /// 挂起对应的编码（退格撤销时恢复）
    var pendingCode = ""
    /// 上一个输出/透传字符的类别（0=中文/其他 1=ASCII 数字 2=ASCII 字母），
    /// 数字/英文后的标点保持半角（3.14 / hello.）—— 标点逻辑阶段4
    var lastCls = 0
    /// 候选当前页（页大小 5，翻页键 -/= Tab PageUp/Down）
    var page = 0
    /// 引号配对状态（“‘ 已开待闭）—— 标点阶段
    var dqOpen = false
    var sqOpen = false
    /// Ctrl+0 切换: 标点强制半角（对齐 rime ascii_punct）
    var asciiPunct = false
    /// $/| 已选次选候选，抬键时补发该标点（"。" / "，"）
    var pendingPunct: String?
    /// 补标点时匹配的键码（keyUp 与 keyDown 同码）
    var pendingPunctKey: UInt16 = 0
    /// 自动造词: 连续全码(4键)上屏的单字链，≥2 字即成词。
    /// 任何非「单字+4码」的上屏（简码/选词/标点/英文/回车原样）都断链。
    var autoBuf = ""
    /// ojc 加词模式: 1=选词阶段 2=编码编辑阶段（0=非加词）。
    /// 全程复用候选窗/预编辑，无外部弹窗（对齐 fcitx5 lufly.cpp:89-94）
    var addStage = 0
    var addWord = "" // 已选定的词（stage1 逐字拼，stage2 显示）
    var addCode = "" // 编码，初始为自动推导（stage2）

    /// 会话级 reset（对齐 fcitx5 LuflyIm::reset lufly.cpp:1217-1235）:
    /// 挂起字需由调用方先落地；ascii 跨焦点保留。含 cancelAddWord（lufly.cpp:380-385）。
    func reset() {
        buffer = ""
        reverse = false
        shiftArmed = false
        lastCls = 0
        page = 0
        dqOpen = false
        sqOpen = false
        pendingPunct = nil
        autoBuf = ""
        addStage = 0
        addWord = ""
        addCode = ""
    }
}
