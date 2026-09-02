// 生成输入法图标（透明底黑鸟，单页 16x16pt PDF，经 CoreGraphics 输出标准结构）。
// 源图标 fcitx5/data/lufly.png 实为「白圆角块上的黑鸟」：alpha = 圆角块本身，
// 鸟形藏在 RGB 亮暗里（PIL/raw 探针实证）。这里从亮度提取鸟形（暗=鸟），
// crack-following 描摹轮廓 → RDP 简化 → 高分辨率位图化 → CGPDFContext 封装。
//
// 两条实证结论（2026-09-01/02，勿回退）:
// 1) 图标文件名必须是 menu_icon.pdf——**词干不能与 lufly.icns 撞名**: TIS 按扩展
//    名无关的 imageForResource: 查找，词干 "lufly" 会命中 icns → 菜单栏图标变成
//    占位方块（与矢量/位图、安装位置、签名、缓存均无关，名字是唯一根因）。
// 2) **必须经 CGPDFContext 生成标准结构 PDF，不能手写极简 PDF**: Ctrl+Space
//    切换器 HUD 由远端视图服务渲染（TextInputUIMacHelper/ViewBridge），它消化
//    不了手写的 4 对象未压缩 PDF——菜单栏（NSImage 路径）正常、切换器白方块。
//    换 CG 生成的 PDF（内嵌 Flate 位图）后两端全部正常。
//
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

let N = 128  // 描摹分辨率：128px 轮廓在 16pt 下绰绰平滑

// 1. 上采样后从亮度提取鸟形掩膜: 暗像素=鸟，亮度渐变段做软边
let work = CGContext(data: nil, width: N, height: N, bitsPerComponent: 8,
                     bytesPerRow: N * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                     bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
work.interpolationQuality = .high
work.draw(bird, in: CGRect(x: 0, y: 0, width: N, height: N))
let p = work.data!.assumingMemoryBound(to: UInt8.self)
var inside = [Bool](repeating: false, count: N * N)
for i in 0..<(N * N) {
    // 只认源里全不透明的像素（= 圆角块内部）: 块外透明黑、块边缘抗锯齿半透明
    // 像素的预乘 RGB 亮度都不可信，一律置为块外，避免提出方块边框
    guard p[i * 4 + 3] == 255 else { continue }
    let lum = (299 * Int(p[i * 4]) + 587 * Int(p[i * 4 + 1]) + 114 * Int(p[i * 4 + 2])) / 1000
    inside[i] = lum < 128
}
func isIn(_ x: Int, _ y: Int) -> Bool {
    x >= 0 && x < N && y >= 0 && y < N && inside[y * N + x]
}

// 2. crack-following: 沿「内/外像素边界」收集有向边（内部恒在行进方向左侧，
//    因此外轮廓与洞自动反向），再链成闭环。坐标为位图系（y 向下）。
var edges: [Int: [Int]] = [:]  // 起点 vertex(x + y*(N+1)) -> [终点]
func v(_ x: Int, _ y: Int) -> Int { x + y * (N + 1) }
func addEdge(_ a: Int, _ b: Int) { edges[a, default: []].append(b) }
for y in 0..<N {
    for x in 0..<N where inside[y * N + x] {
        if !isIn(x, y - 1) { addEdge(v(x, y), v(x + 1, y)) }        // 上边界 →
        if !isIn(x, y + 1) { addEdge(v(x + 1, y + 1), v(x, y + 1)) } // 下边界 ←
        if !isIn(x - 1, y) { addEdge(v(x, y + 1), v(x, y)) }         // 左边界 ↑
        if !isIn(x + 1, y) { addEdge(v(x + 1, y), v(x + 1, y + 1)) } // 右边界 ↓
    }
}
var loops: [[(Double, Double)]] = []
var used = Set<Int>()  // 已消费的边（用 "a->b" 编码 a*(N+1)*(N+2)+b）
func edgeKey(_ a: Int, _ b: Int) -> Int { a * (N + 2) * (N + 2) + b }
for start in edges.keys.sorted() {
    for firstEnd in edges[start]! where !used.contains(edgeKey(start, firstEnd)) {
        used.insert(edgeKey(start, firstEnd))
        var loop = [(Double, Double)]()
        var cur = start, next = firstEnd
        loop.append((Double(cur % (N + 1)), Double(cur / (N + 1))))
        while next != start {
            loop.append((Double(next % (N + 1)), Double(next / (N + 1))))
            used.insert(edgeKey(cur, next))
            guard let candidates = edges[next] else { break }
            if let pick = candidates.first(where: { !used.contains(edgeKey(next, $0)) }) {
                cur = next; next = pick
            } else { break }
        }
        if loop.count >= 4 { loops.append(loop) }
    }
}

// 3. Ramer-Douglas-Peucker 简化（epsilon 1.2px），输出足够平滑且体积极小
func rdp(_ pts: [(Double, Double)], _ eps: Double) -> [(Double, Double)] {
    guard pts.count > 2 else { return pts }
    let n = pts.count
    var keep = [Bool](repeating: false, count: n)
    keep[0] = true; keep[n - 1] = true
    var stack = [(0, n - 1)]
    while let (a, b) = stack.popLast() {
        guard b > a + 1 else { continue }
        let ax = pts[a].0, ay = pts[a].1, bx = pts[b].0, by = pts[b].1
        let dx = bx - ax, dy = by - ay
        let len = (dx * dx + dy * dy).squareRoot()
        var best = -1.0, bestI = -1
        for i in (a + 1)..<b {
            let d = len == 0
                ? ((pts[i].0 - ax) * (pts[i].0 - ax) + (pts[i].1 - ay) * (pts[i].1 - ay)).squareRoot()
                : abs(dy * pts[i].0 - dx * pts[i].1 + bx * ay - by * ax) / len
            if d > best { best = d; bestI = i }
        }
        if best > eps { keep[bestI] = true; stack.append((a, bestI)); stack.append((bestI, b)) }
    }
    return (0..<n).filter { keep[$0] }.map { pts[$0] }
}
let simplified = loops.map { rdp($0, 1.2) }

// 3.5 归一化到画布: 按最大维度等比放大，留 8% 边距居中（用户实测 4% 偏大）。
var drawn: [[(Double, Double)]] = []
if !simplified.isEmpty {
    var minX = Double.greatestFiniteMagnitude, minY = minX
    var maxX = -Double.greatestFiniteMagnitude, maxY = maxX
    for loop in simplified { for pt in loop {
        minX = min(minX, pt.0); minY = min(minY, pt.1)
        maxX = max(maxX, pt.0); maxY = max(maxY, pt.1)
    } }
    let margin = Double(N) * 0.08
    let k = (Double(N) - margin * 2) / max(maxX - minX, maxY - minY)
    let cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, c = Double(N) / 2
    drawn = simplified.map { $0.map { (c + ($0.0 - cx) * k, c + ($0.1 - cy) * k) } }
}
if drawn.isEmpty {
    fputs("掩膜为空：无法提取鸟形\n", stderr)
    exit(1)
}

// 4. 高分辨率位图化 + CGPDFContext 封装: 掩膜坐标 y 向下，CG y 向上，翻转绘制。
//    位图 256px 对 16pt 图标（3x Retina 66px）绰绰有余。CGPDFContext 产出标准
//    结构（Flate 压缩流 + 正规 xref/Info），切换器远端渲染服务与菜单栏都能吃。
let px = 256
let bitmap = CGContext(data: nil, width: px, height: px, bitsPerComponent: 8,
                       bytesPerRow: px * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                       bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
let k = CGFloat(px) / CGFloat(N)
bitmap.translateBy(x: 0, y: CGFloat(px))
bitmap.scaleBy(x: k, y: -k)
bitmap.setFillColor(CGColor(red: 0, green: 0, blue: 0, alpha: 1))
for loop in drawn {
    guard let first = loop.first else { continue }
    let path = CGMutablePath()
    path.move(to: CGPoint(x: first.0, y: first.1))
    for pt in loop.dropFirst() { path.addLine(to: CGPoint(x: pt.0, y: pt.1)) }
    path.closeSubpath()
    bitmap.addPath(path)
}
bitmap.fillPath(using: .evenOdd)
guard let birdImage = bitmap.makeImage() else {
    fputs("位图化失败\n", stderr)
    exit(1)
}

var mediaBox = CGRect(x: 0, y: 0, width: 16, height: 16)
guard let pdf = CGContext(outURL, mediaBox: &mediaBox, nil) else {
    fputs("CGPDFContext 创建失败\n", stderr)
    exit(1)
}
pdf.beginPDFPage(nil)
pdf.draw(birdImage, in: mediaBox)
pdf.endPDFPage()
pdf.closePDF()
print("标准 PDF 已生成（CGPDFContext，内嵌 \(px)px 位图）: \(drawn.count) 条轮廓, \(drawn.reduce(0) { $0 + $1.count }) 个顶点")
