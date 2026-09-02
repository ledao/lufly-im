// 候选窗：横排「序号.词 剩余编码」，首位高亮，aux 提示行。
// 显示格式对齐 fcitx5（lufly.cpp:570-599 CommonCandidateList + 序号标签）；
// 定位对齐 tsf cand.rs show(): 贴光标下方、贴底翻转、已显示则钉住原位置
// 不随输入漂移（fcitx5/TSF 同款行为，Squirrel 同样锚在 preedit 首字符）。
// 视觉定稿（2026-09-02 三样式试验，用户挑定「极简加大」并收拢为唯一实现）:
//   **透明底 + 细圆角描边**——面板 clear，draw 不刷底色只裁圆角，文字直接浮
//   在屏幕内容上；用户看过透明实锤截图后明确拍板「别修，就这样，好看」，
//   透明是特性不是 bug，勿再补背景色；后补 1pt separatorColor 圆角描边
//   （透明底要有边界感、别太粗，用户裁定）。候选词 18pt light 字重（透明窗
//   AA 偏重，降一档字重视觉补偿回「常规」感，用户确认「这次才对了」；加粗
//   16pt semibold / 18pt bold 均已否）、高亮浅灰 systemGray 0.15、提亮行带
//   （浅色 plusLighter 加法增亮渐变、暗色 50% 深底渐变；50% 白罩压灰被否）、
//   辅助编码品牌青绿。
//   被否方案勿再试: 磨砂底+数字徽章（样式1）、实色绿高亮条+白字、
//   辅助编码等宽字体、首选加粗（16pt semibold / 18pt bold 都试过，都不要）。
import AppKit

final class CandidateWindow {
    private let panel: NSPanel
    private let view = CandidateView()

    init() {
        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 10, height: 10),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered, defer: false)
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.level = .statusBar
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false
        panel.contentView = view
    }

    /// items: (词, 全码)；typed: 已敲编码（计算剩余后缀）；aux: 顶部提示行（反查"拼音"）
    func show(_ items: [(text: String, code: String)], typed: String, aux: String? = nil, at caret: NSRect) {
        guard !items.isEmpty, caret.width > 0 || caret.height > 0 else {
            hide()
            return
        }
        view.items = items
        view.typed = typed
        view.aux = aux
        present(at: caret)
    }

    /// 无候选仅提示行（ojc 加词两阶段的操作提示，对齐 fcitx5 setAuxUp）
    func showAux(_ aux: String, at caret: NSRect) {
        view.items = []
        view.typed = ""
        view.aux = aux
        present(at: caret)
    }

    private func present(at caret: NSRect) {
        view.needsDisplay = true
        let size = view.fittingSize
        var origin: NSPoint
        if panel.isVisible {
            // 钉住: 保留当前位置（上缘对齐），只按新内容调尺寸（对齐 tsf cand.rs pinned）
            let old = panel.frame
            origin = NSPoint(x: old.minX, y: old.maxY - size.height)
        } else {
            // 首次出现: 光标矩形下方 2pt；贴屏幕底边翻到上方，钳进可视区
            let screen = NSScreen.screens.first(where: { NSPointInRect(caret.origin, $0.frame) })
                ?? NSScreen.main
            var p = NSPoint(x: caret.minX, y: caret.minY - size.height - 2)
            if let screen, p.y < screen.visibleFrame.minY {
                p.y = caret.maxY + 2
            }
            if let screen {
                p.x = min(p.x, screen.visibleFrame.maxX - size.width)
                p.x = max(p.x, screen.visibleFrame.minX)
            }
            origin = p
        }
        panel.setFrame(NSRect(origin: origin, size: size), display: true)
        panel.orderFrontRegardless()
    }

    func hide() {
        panel.orderOut(nil)
    }
}

final class CandidateView: NSView {
    var items: [(text: String, code: String)] = []
    var typed = ""
    var aux: String? = nil

    // 品牌青绿（鹭羽/湿地色）: 浅色模式深一档保对比，深色模式提亮。
    // 只用于辅助编码——选中态高亮永远浅灰（用户多轮裁定）
    private static let accent = NSColor(name: nil) { ap in
        ap.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(srgbRed: 0.33, green: 0.78, blue: 0.64, alpha: 1)
            : NSColor(srgbRed: 0.02, green: 0.50, blue: 0.41, alpha: 1)
    }

    private let wordFont = NSFont.systemFont(ofSize: 18, weight: .light)  // light 补偿透明窗 AA 偏重（用户裁定）
    private let codeFont = NSFont.systemFont(ofSize: 12)
    private let labelFont = NSFont.systemFont(ofSize: 13)
    private let auxFont = NSFont.systemFont(ofSize: 12)
    private let padX: CGFloat = 10
    private let itemGap: CGFloat = 12
    private let vpad: CGFloat = 5

    private var hasAux: Bool { !(aux ?? "").isEmpty }
    private var auxH: CGFloat { hasAux ? auxFont.ascender - auxFont.descender + 8 : 0 }

    // MARK: - 布局量测

    /// 序号标签（fcitx5 selectionKeys 1-5 → 每项 "1." 前缀）
    private func label(_ i: Int) -> String { "\(i + 1)." }

    /// 剩余编码后缀（exact 或无后缀为空，对齐 fcitx5 updateUI 规则 lufly.cpp:583-589）
    private func suffix(_ i: Int) -> String {
        let full = items[i].code
        guard !full.isEmpty, full.count > typed.count, full.hasPrefix(typed) else { return "" }
        return " " + String(full.dropFirst(typed.count))
    }

    private func attr(_ s: String, _ font: NSFont, _ color: NSColor) -> NSAttributedString {
        NSAttributedString(string: s, attributes: [.font: font, .foregroundColor: color])
    }

    private func itemWidth(_ i: Int) -> CGFloat {
        let l = attr(label(i), labelFont, .labelColor).size().width
        let w = attr(items[i].text, wordFont, .labelColor).size().width
        let s = attr(suffix(i), codeFont, .labelColor).size().width
        return l + w + s
    }

    override var fittingSize: NSSize {
        var w: CGFloat = 0
        var h: CGFloat = 0
        if hasAux {
            w = max(w, attr(aux!, auxFont, .secondaryLabelColor).size().width)
            h += auxH
        }
        if !items.isEmpty {
            var row = padX * 2
            for i in items.indices {
                row += itemWidth(i) + itemGap
            }
            row -= itemGap
            w = max(w, row)
            h += wordFont.ascender - wordFont.descender + 4 + vpad * 2
        }
        return NSSize(width: max(w, 20), height: h)
    }

    // MARK: - 绘制

    override func viewDidChangeEffectiveAppearance() {
        needsDisplay = true  // 动态品牌色随外观重解析
    }

    override func draw(_ dirtyRect: NSRect) {
        // 透明底定稿: 不刷任何背景色，只裁圆角防高亮块直角顶出窗口。
        // （曾有「补底色」修复方案，用户看过透明截图后拍板「别修，就这样，好看」）
        NSBezierPath(roundedRect: bounds, xRadius: 6, yRadius: 6).setClip()

        // 细圆角描边: 透明底要有边界感（用户后补裁定），1pt 别太粗；
        // 内缩 0.5、半径 5.5 与裁剪圆角同心，避免四角被裁出毛边
        let border = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: 5.5, yRadius: 5.5)
        NSColor.separatorColor.setStroke()
        border.lineWidth = 1
        border.stroke()

        // aux 提示行（顶部小字，对齐 fcitx5 auxUp）
        if hasAux {
            let s = attr(aux!, auxFont, .secondaryLabelColor)
            s.draw(at: NSPoint(x: padX, y: bounds.height - 4 - auxFont.ascender))
        }

        // 候选行: 「序号.词 剩余编码」，首位高亮块（fcitx5/TSF 同款: 选中项始终带底色）。
        // 不能按 items.count>1 省略——唯一候选时字块兜底成纯文本窗（实测坑）。
        // 文字行带不透明、行带上下到边框保持透明（2026-09-02 用户裁定）；带高 =
        // 行框高、在候选区内垂直居中。早期「高亮须全高防漏底」是基于实底窗的
        // 顾虑，透明底+行带设计下不适用。（曾加过橙色指示方块，用户裁定太抢眼已撤）
        guard !items.isEmpty else { return }
        let rowTop = bounds.height - auxH
        let baseline = vpad + 2 + wordFont.ascender
        // 全透明底 + 提亮行带: 50% 白罩会显得灰扑扑（用户反馈「不亮不透」——
        // 半透明白是压灰不是提亮），改 plusLighter 加法混合只增亮不浑浊：
        // 白底上无痕迹（透）、深色内容上提亮（亮）；暗色模式回落 50% 深底渐变
        let bandH = wordFont.ascender - wordFont.descender
        let bandBottom = (rowTop - bandH) / 2
        let bandTop = bandBottom + bandH
        let locs: [CGFloat] = [0, bandBottom / bounds.height, bandTop / bounds.height, 1]
        let isDark = effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        let wash: NSGradient?
        if isDark {
            let bg = NSColor.controlBackgroundColor
            wash = NSGradient(colors: [bg.withAlphaComponent(0), bg.withAlphaComponent(0.5),
                                       bg.withAlphaComponent(0.5), bg.withAlphaComponent(0)],
                              atLocations: locs, colorSpace: .deviceRGB)
        } else {
            wash = NSGradient(colors: [NSColor.white.withAlphaComponent(0), NSColor.white.withAlphaComponent(0.45),
                                       NSColor.white.withAlphaComponent(0.45), NSColor.white.withAlphaComponent(0)],
                              atLocations: locs, colorSpace: .deviceRGB)
        }
        let bandPath = NSBezierPath(roundedRect: bounds.insetBy(dx: 1, dy: 1), xRadius: 5, yRadius: 5)
        if let ctx = NSGraphicsContext.current, !isDark {
            let prev = ctx.compositingOperation
            ctx.compositingOperation = .plusLighter
            wash?.draw(in: bandPath, angle: 90)
            ctx.compositingOperation = prev
        } else {
            wash?.draw(in: bandPath, angle: 90)
        }

        var x = padX
        for (i, item) in items.enumerated() {
            let hl = i == 0
            let lStr = attr(label(i), labelFont, hl ? .labelColor : .secondaryLabelColor)
            let wStr = attr(item.text, wordFont, .labelColor)
            let sStr = attr(suffix(i), codeFont, Self.accent)
            let lW = lStr.size().width, wW = wStr.size().width, sW = sStr.size().width

            if hl {
                let rect = NSRect(x: x - 6, y: bandBottom, width: lW + wW + sW + 12, height: bandH)
                NSColor.systemGray.withAlphaComponent(0.15).setFill()
                NSBezierPath(roundedRect: rect, xRadius: 6, yRadius: 6).fill()
            }

            lStr.draw(at: NSPoint(x: x, y: baseline - labelFont.ascender))
            wStr.draw(at: NSPoint(x: x + lW, y: baseline - wordFont.ascender))
            if sW > 0 {
                sStr.draw(at: NSPoint(x: x + lW + wW, y: baseline - codeFont.ascender))
            }
            x += lW + wW + sW + itemGap
        }
    }
}
