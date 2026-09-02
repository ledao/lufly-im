// 生成 dmg 背景图: 「双击安装」引导（用户反馈: 裸 dmg 窗口不知道要干什么）。
// 用法: mkdmgbg <输出.png>   —— 画布 660×420 透明底，与 pack.sh 的窗口尺寸对应。
import AppKit

let out = CommandLine.arguments[1]
let W: CGFloat = 660, H: CGFloat = 420
let img = NSImage(size: NSSize(width: W, height: H))
img.lockFocus()
let para = NSMutableParagraphStyle()
para.alignment = .center
// 注意: lockFocus 后坐标系原点在左下角，y 自下而上
let big = NSAttributedString(string: "双击「Lufly」开始安装", attributes: [
    .font: NSFont.systemFont(ofSize: 34, weight: .semibold),
    .foregroundColor: NSColor(calibratedWhite: 0.30, alpha: 1),
    .paragraphStyle: para,
])
big.draw(in: NSRect(x: 0, y: H - 92, width: W, height: 52))
let sub = NSAttributedString(
    string: "安装完成后：系统设置 → 键盘 → 输入法 → 添加「小鹭音形」",
    attributes: [
        .font: NSFont.systemFont(ofSize: 15),
        .foregroundColor: NSColor(calibratedWhite: 0.50, alpha: 1),
        .paragraphStyle: para,
    ])
sub.draw(in: NSRect(x: 0, y: H - 134, width: W, height: 24))
img.unlockFocus()

let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!
    .write(to: URL(fileURLWithPath: out))
print("bg: \(out)")
