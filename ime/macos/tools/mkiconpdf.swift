// 生成输入法菜单栏图标（透明底黑鸟 —— **矢量** PDF）。
// 源图标 fcitx5/data/lufly.png 实为「白圆角块上的黑鸟」：alpha = 圆角块本身，
// 鸟形藏在 RGB 亮暗里（PIL/raw 探针实证）。这里从亮度提取鸟形（暗=鸟），
// 描摹成矢量路径填黑输出。
//
// 为什么必须是矢量 PDF（2026-09-02 实测定论）: 菜单栏/输入源列表的图标渲染
// 管线不吃位图 alpha——PDF 位图 XObject 的 /SMask、透明底 PNG 全部被渲染成
// 实心方块（注销重登、清各进程缓存均无效；NSImage/sips 渲染正常所以本地
// 测不出）。本机三个正常显示图标的输入法 Squirrel(AI 导出)/微信/豆包
// （rsvg 类工具导出）的 menu_icon.pdf 无一例外全是纯矢量路径、零位图
// XObject。故此处不做位图嵌入，直接 crack-following 提取轮廓 → RDP 简化
// → 手写最小矢量 PDF（无外部依赖，potrace/rsvg-convert 本机均无）。
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

// 3.5 归一化到满画布: 源图里鸟只占圆角块 ~60%，等比描摹在 16pt 菜单栏里显得
// 小（Squirrel 字形几乎满画布）。按最大维度等比放大，留 4% 边距居中。
var drawn: [[(Double, Double)]] = []
if !simplified.isEmpty {
    var minX = Double.greatestFiniteMagnitude, minY = minX
    var maxX = -Double.greatestFiniteMagnitude, maxY = maxX
    for loop in simplified { for pt in loop {
        minX = min(minX, pt.0); minY = min(minY, pt.1)
        maxX = max(maxX, pt.0); maxY = max(maxY, pt.1)
    } }
    let margin = Double(N) * 0.04
    let k = (Double(N) - margin * 2) / max(maxX - minX, maxY - minY)
    let cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, c = Double(N) / 2
    drawn = simplified.map { $0.map { (c + ($0.0 - cx) * k, c + ($0.1 - cy) * k) } }
}
if drawn.isEmpty {
    fputs("掩膜为空：无法提取鸟形\n", stderr)
    exit(1)
}

// 4. 手写最小矢量 PDF：单页 16x16pt，cm 把位图坐标（y 向下）映射到 PDF
//    （y 向上），even-odd 填充让洞自动镂空。Squirrel/微信/豆包同构：纯路径、
//    零位图 XObject。
func num(_ d: Double) -> String { String(format: "%.2f", d) }
var stream = "0.125 0 0 -0.125 0 16 cm\n0 0 0 rg\n"
for loop in drawn {
    stream += "\(num(loop[0].0)) \(num(loop[0].1)) m\n"
    for pt in loop.dropFirst() { stream += "\(num(pt.0)) \(num(pt.1)) l\n" }
    stream += "h\n"
}
stream += "f*\n"
let streamData = Array(stream.utf8)

var pdf = "%PDF-1.4\n"
var offsets: [Int] = []
func emit(_ s: String) { offsets.append(pdf.utf8.count); pdf += s }
emit("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
emit("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
emit("3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 16 16] /Contents 4 0 R /Resources << >> >>\nendobj\n")
emit("4 0 obj\n<< /Length \(streamData.count) >>\nstream\n")
pdf += stream
pdf += "endstream\nendobj\n"
let xrefPos = pdf.utf8.count
pdf += "xref\n0 5\n0000000000 65535 f \n"
for off in offsets { pdf += String(format: "%010d 00000 n \n", off) }
pdf += "trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n\(xrefPos)\n%%EOF\n"

try! Data(pdf.utf8).write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
print("矢量 PDF 已生成: \(drawn.count) 条轮廓, \(drawn.reduce(0) { $0 + $1.count }) 个顶点")
