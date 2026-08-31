// 中英模式提示浮窗 —— Shift 切换时在屏幕右下角闪现「中 / EN」，1 秒自动消失。
// 对齐 tsf/src/status.rs（44px 圆角深灰底白字，工作区右下角 48px 边距；
// mac 菜单栏图标由系统渲染不随中英变，浮窗补足视觉反馈）。
import AppKit

final class StatusWindow {
    static let shared = StatusWindow()

    private let panel: NSPanel
    private let label: NSTextField
    private var hideWork: DispatchWorkItem?

    private init() {
        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 44, height: 44),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered, defer: false)
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.level = .statusBar
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hasShadow = false

        label = NSTextField(labelWithString: "")
        label.font = NSFont.systemFont(ofSize: 22, weight: .semibold)
        label.textColor = .white
        label.alignment = .center
        label.frame = NSRect(x: 0, y: 0, width: 44, height: 44)
        label.autoresizingMask = [.width, .height]

        let content = panel.contentView!
        content.wantsLayer = true
        // 深灰底 + 圆角（对齐 status.rs COLORREF(0x303030) / 圆角 12）
        content.layer?.backgroundColor = NSColor(
            calibratedWhite: 0x30 / 255.0, alpha: 1).cgColor
        content.layer?.cornerRadius = 12
        content.layer?.masksToBounds = true
        content.addSubview(label)
    }

    /// 模式切换提示: ascii=true 显示 EN，false 显示 中（对齐 status.rs flash）
    func flash(ascii: Bool) {
        label.stringValue = ascii ? "EN" : "中"

        // 光标所在屏幕的工作区右下角
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first { NSMouseInRect(mouse, $0.frame, false) }
            ?? NSScreen.main
        if let frame = screen?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x: frame.maxX - 44 - 48, y: frame.minY + 48))
        }
        panel.orderFrontRegardless()

        // 1s 后隐藏（重置前次计时，对齐 SHOW_MS=1000）
        hideWork?.cancel()
        let work = DispatchWorkItem { [panel] in panel.orderOut(nil) }
        hideWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0, execute: work)
    }
}
