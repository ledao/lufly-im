// 中文标点全角化映射 —— 从 tsf/src/state.rs chinese_punct 平移，
// 对齐 rime punctuator half_shape（fcitx5 真源 lufly.cpp:109-139）。
// 引号按对交替；返回 nil 表示半角放行键（` ~ @ # 等与字母数字）。
func chinesePunct(_ ch: Character, dqOpen: inout Bool, sqOpen: inout Bool) -> String? {
    switch ch {
    case ",": return "，"
    case ".": return "。"
    case "<": return "《"
    case ">": return "》"
    case "/": return "、"
    case "?": return "？"
    case ";": return "；"
    case ":": return "："
    case "'":
        sqOpen.toggle()
        return sqOpen ? "‘" : "’"
    case "\"":
        dqOpen.toggle()
        return dqOpen ? "“" : "”"
    case "\\": return "、"
    case "|": return "·"
    case "!": return "！"
    case "$": return "￥"
    case "^": return "……"
    case "(": return "（"
    case ")": return "）"
    case "_": return "——"
    case "[": return "「"
    case "]": return "」"
    case "{": return "『"
    case "}": return "』"
    default: return nil
    }
}
