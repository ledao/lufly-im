// 生成 macOS App 图标 1024px PNG（build.sh 再经 sips/iconutil 转 icns）。
// 源 48px 黑鸟剪影直接 sips 放大成黑团（用户实测）；这里合成系统风格的
// 圆角徽章（深海蓝，与菜单栏 lufly.pdf 同色）+ 白鸟。
// 用法: mkappicon <bird.png> <out.png>
import Foundation
import CoreGraphics
import ImageIO

guard CommandLine.arguments.count == 3 else {
    fputs("usage: mkappicon <bird.png> <out.png>\n", stderr)
    exit(2)
}
let inURL = URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL
let outURL = URL(fileURLWithPath: CommandLine.arguments[2]) as CFURL

guard let src = CGImageSourceCreateWithURL(inURL, nil),
      let bird = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    fputs("无法读取 \(CommandLine.arguments[1])\n", stderr)
    exit(1)
}

let px = 512  // 鸟形提取工作分辨率

// 与 mkiconpdf 同款: 上采样后从亮度提取鸟形（暗=鸟 → 白），源 alpha 只用于
// 圆角块边界判定（块外透明像素一律清掉，防提出方块边框）
let work = CGContext(data: nil, width: px, height: px, bitsPerComponent: 8,
                     bytesPerRow: px * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                     bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
work.interpolationQuality = .high
work.draw(bird, in: CGRect(x: 0, y: 0, width: px, height: px))
let p = work.data!.assumingMemoryBound(to: UInt8.self)
for i in 0..<(px * px) {
    if p[i * 4 + 3] != 255 {
        p[i * 4] = 0; p[i * 4 + 1] = 0; p[i * 4 + 2] = 0; p[i * 4 + 3] = 0
        continue
    }
    let lum = (299 * Int(p[i * 4]) + 587 * Int(p[i * 4 + 1]) + 114 * Int(p[i * 4 + 2])) / 1000
    let a: Int
    if lum >= 160 { a = 0 } else if lum <= 96 { a = 255 } else { a = (160 - lum) * 255 / 64 }
    p[i * 4] = UInt8(a); p[i * 4 + 1] = UInt8(a); p[i * 4 + 2] = UInt8(a); p[i * 4 + 3] = UInt8(a)
}
guard let whiteBird = work.makeImage() else { exit(1) }

// 1024 画布: 徽章按 Apple 网格留边（824/1024），圆角 ~22.4%，白鸟居中 64%
let S: CGFloat = 1024
let canvas = CGContext(data: nil, width: Int(S), height: Int(S), bitsPerComponent: 8,
                       bytesPerRow: Int(S) * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                       bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
canvas.interpolationQuality = .high
let m = S * 100 / 1024, badgeSide = S - m * 2
let badge = CGRect(x: m, y: m, width: badgeSide, height: badgeSide)
canvas.addPath(CGPath(roundedRect: badge,
                      cornerWidth: badgeSide * 0.224, cornerHeight: badgeSide * 0.224,
                      transform: nil))
canvas.setFillColor(CGColor(srgbRed: 0x1B / 255.0, green: 0x49 / 255.0, blue: 0x65 / 255.0, alpha: 1))
canvas.fillPath()
canvas.draw(whiteBird, in: badge.insetBy(dx: badgeSide * 0.18, dy: badgeSide * 0.18))

let out = canvas.makeImage()!
let dest = CGImageDestinationCreateWithURL(outURL, "public.png" as CFString, 1, nil)!
CGImageDestinationAddImage(dest, out, nil as CFDictionary?)
guard CGImageDestinationFinalize(dest) else {
    fputs("写出失败 \(CommandLine.arguments[2])\n", stderr)
    exit(1)
}
print("appicon: \(CommandLine.arguments[2])")
