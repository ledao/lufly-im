// 生成输入法菜单栏图标 PDF。
// 为什么不用 sips: `sips -s format pdf` 会丢 alpha（无 SMask）→ 菜单栏渲染成白方块（实测）。
// 源图标 fcitx5/data/lufly.png 实为「白圆角块上的黑鸟」：alpha = 圆角块本身，
// 鸟形藏在 RGB 亮暗里（PIL/raw 探针实证）。直接放大会是"白块+小鸟"→ 菜单栏白块。
// 这里从亮度提取鸟形（暗=鸟），重绘成系统输入法同款徽章（SCIM pinyin.tiff：
// 深色圆角底 + 白色主形），深浅菜单栏都可读。
// 用法: mkiconpdf <bird.png> <out.pdf>
import Foundation
import CoreGraphics
import ImageIO

guard CommandLine.arguments.count == 3 else {
    fputs("usage: mkiconpdf <bird.png> <out.pdf>\n", stderr)
    exit(2)
}
let inURL = URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL
let outURL = URL(fileURLWithPath: CommandLine.arguments[2]) as CFURL

guard let src = CGImageSourceCreateWithURL(inURL, nil),
      let bird = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    fputs("无法读取 \(CommandLine.arguments[1])\n", stderr)
    exit(1)
}

let pts: CGFloat = 16   // PDF 页面 16pt ≈ 菜单栏实际渲染尺寸
let scale: CGFloat = 8  // 内嵌位图 8x，retina 下清晰
let px = Int(pts * scale)

// 1. 上采样到 px×px，再从亮度提取鸟形: 暗像素=鸟 → 白色，亮度渐变段做软边
let work = CGContext(data: nil, width: px, height: px, bitsPerComponent: 8,
                     bytesPerRow: px * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                     bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
work.interpolationQuality = .high
work.draw(bird, in: CGRect(x: 0, y: 0, width: px, height: px))
let p = work.data!.assumingMemoryBound(to: UInt8.self)
for i in 0..<(px * px) {
    // 只认源里全不透明的像素（= 圆角块内部）: 块外透明黑、块边缘抗锯齿半透明
    // 像素的预乘 RGB 亮度都不可信，一律清透明，避免提出方块边框
    if p[i * 4 + 3] != 255 {
        p[i * 4] = 0; p[i * 4 + 1] = 0; p[i * 4 + 2] = 0; p[i * 4 + 3] = 0
        continue
    }
    let lum = (299 * Int(p[i * 4]) + 587 * Int(p[i * 4 + 1]) + 114 * Int(p[i * 4 + 2])) / 1000
    let a: Int
    if lum >= 160 { a = 0 } else if lum <= 96 { a = 255 } else { a = (160 - lum) * 255 / 64 }
    // 预乘语义下白色: rgb = a（半透明边不偏色）
    p[i * 4] = UInt8(a); p[i * 4 + 1] = UInt8(a); p[i * 4 + 2] = UInt8(a); p[i * 4 + 3] = UInt8(a)
}
guard let whiteBird = work.makeImage() else { exit(1) }

// 2. 深色圆角徽章 + 白鸟，写入 PDF（页面 16x16pt）
// 徽章底色: 深海蓝（鹭/水意象），深浅菜单栏上都可读
var mediaBox = CGRect(x: 0, y: 0, width: pts, height: pts)
guard let ctx = CGContext(outURL, mediaBox: &mediaBox, nil as CFDictionary?) else {
    fputs("无法创建 \(CommandLine.arguments[2])\n", stderr)
    exit(1)
}
ctx.scaleBy(x: scale, y: scale)  // 之后按 16pt 逻辑坐标画
ctx.beginPDFPage(nil as CFDictionary?)

let badgeColor = CGColor(srgbRed: 0x1B / 255.0, green: 0x49 / 255.0, blue: 0x65 / 255.0, alpha: 1)
let badge = CGRect(x: 0, y: 0, width: pts, height: pts)
ctx.addPath(CGPath(roundedRect: badge,
                   cornerWidth: pts * 0.24, cornerHeight: pts * 0.24, transform: nil))
ctx.setFillColor(badgeColor)
ctx.fillPath()

let birdRect = badge.insetBy(dx: pts * 0.10, dy: pts * 0.10)
ctx.draw(whiteBird, in: birdRect)

ctx.endPDFPage()
ctx.closePDF()
