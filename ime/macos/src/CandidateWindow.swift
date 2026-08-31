// 候选窗：横排「序号.词 剩余编码」，首位高亮，aux 提示行。
// 显示格式对齐 fcitx5（lufly.cpp:570-599 CommonCandidateList + 序号标签）；
// 定位对齐 tsf cand.rs show(): 贴光标下方、贴底翻转、已显示则钉住原位置
// 不随输入漂移（fcitx5/TSF 同款行为，Squirrel 同样锚在 preedit 首字符）。
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

    private let wordFont = NSFont.systemFont(ofSize: 16)
    private let codeFont = NSFont.systemFont(ofSize: 12)
    private let labelFont = NSFont.systemFont(ofSize: 13)
    private let auxFont = NSFont.systemFont(ofSize: 12)
    private let padX: CGFloat = 10
    private let gap: CGFloat = 12
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

    private func itemWidth(_ i: Int, hl: Bool) -> CGFloat {
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
                row += itemWidth(i, hl: false) + itemGap
            }
            row -= itemGap
            w = max(w, row)
            h += wordFont.ascender - wordFont.descender + 4 + vpad * 2
        }
        return NSSize(width: max(w, 20), height: h)
    }

    // MARK: - 绘制

    override func draw(_ dirtyRect: NSRect) {
        let bg = NSBezierPath(roundedRect: bounds, xRadius: 6, yRadius: 6)
        NSColor.controlBackgroundColor.setFill()
        bg.fill()
        NSColor.separatorColor.setStroke()
        bg.lineWidth = 1
        bg.stroke()

        // aux 提示行（顶部小字，对齐 fcitx5 auxUp）
        if hasAux {
            let s = attr(aux!, auxFont, .secondaryLabelColor)
            s.draw(at: NSPoint(x: padX, y: bounds.height - 4 - auxFont.ascender))
        }

        // 候选行: 「序号.词 剩余编码」，首位高亮块（对齐 fcitx5 横排高亮）
        guard !items.isEmpty else { return }
        let rowTop = bounds.height - auxH
        let baseline = vpad + 2 + wordFont.ascender
        var x = padX
        for (i, item) in items.enumerated() {
            let hl = i == 0
            let lStr = attr(label(i), labelFont,
                            hl ? .white : NSColor.secondaryLabelColor)
            let wStr = attr(item.text, wordFont, hl ? .white : .labelColor)
            let sStr = attr(suffix(i), codeFont,
                            hl ? NSColor.white.withAlphaComponent(0.85) : .secondaryLabelColor)
            let lW = lStr.size().width, wW = wStr.size().width, sW = sStr.size().width

            // 首位恒有高亮块（fcitx5/TSF 同款: 选中项始终带底色）。
            // 不能按 items.count>1 省略——唯一候选时白字落在白底上 = 白窗（实测坑）
            if hl {
                let rect = NSRect(
                    x: x - 4, y: vpad - 2,
                    width: lW + wW + sW + 8,
                    height: rowTop - vpad + 2)
                NSColor.controlAccentColor.setFill()
                NSBezierPath(roundedRect: rect, xRadius: 4, yRadius: 4).fill()
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
