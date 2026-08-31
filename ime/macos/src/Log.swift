// 小鹭音形 —— 诊断日志（对齐 TSF 端 %APPDATA%\lufly\tsf.log 的习惯）。
// 写 ~/Library/Logs/lufly.log，Console.app 或 tail 都能看。
import Foundation

final class LuflyLog {
    static let shared = LuflyLog()

    private let queue = DispatchQueue(label: "im.lufly.log")
    private let fileURL: URL
    private let df: DateFormatter

    private init() {
        let logsDir = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Logs", isDirectory: true)
        try? FileManager.default.createDirectory(at: logsDir, withIntermediateDirectories: true)
        fileURL = logsDir.appendingPathComponent("lufly.log")
        df = DateFormatter()
        df.dateFormat = "MM-dd HH:mm:ss.SSS"
    }

    func info(_ msg: String) { write("INFO", msg) }
    func error(_ msg: String) { write("ERROR", msg) }

    private func write(_ level: String, _ msg: String) {
        let line = "\(df.string(from: Date())) \(level) \(msg)\n"
        queue.sync {
            if !FileManager.default.fileExists(atPath: fileURL.path) {
                FileManager.default.createFile(atPath: fileURL.path, contents: nil)
            }
            guard let fh = try? FileHandle(forWritingTo: fileURL) else { return }
            defer { try? fh.close() }
            _ = try? fh.seekToEnd()
            fh.write(Data(line.utf8))
        }
    }
}
