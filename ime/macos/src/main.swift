// 小鹭音形 —— macOS IMK 输入法入口。
//
// 进程模型: 输入法是独立 app（系统懒启动、闲置回收），单焦点一份状态，
// 不需要 fcitx5 端的「单 scratch 引擎重放」机制。
// 双入口: 从已安装位置（~/Library/Input Methods）启动 = 正常输入法；
// 从其他位置（如 dmg）双击 = 自安装器（搜狗 Mac 版同款惯例，见 Installer.swift）。
// 另有命令行: --install 静默安装（install.sh 用）、--uninstall 静默卸载（任何位置）。
import Cocoa
import InputMethodKit

if CommandLine.arguments.contains("--uninstall") {
    Installer.runUninstallCli() // 停用输入源 + 删本体后 exit，不进输入法流程
}

if !Installer.isInstalledLocation {
    Installer.run() // 自安装/卸载流程，结束即 exit
}

LuflyLog.shared.info("==== Lufly 启动 pid=\(ProcessInfo.processInfo.processIdentifier) ====")

let info = Bundle.main.infoDictionary ?? [:]
let connName = (info["InputMethodConnectionName"] as? String) ?? "Lufly_Connection"
let bundleID = Bundle.main.bundleIdentifier ?? "im.lufly.inputmethod.Lufly"

// IMKServer 建立分布式对象连接；系统通过 Info.plist 的
// InputMethodServerControllerClass 实例化每个会话的 controller。
let server = IMKServer(name: connName, bundleIdentifier: bundleID)
if server == nil {
    LuflyLog.shared.error("IMKServer 创建失败 conn=\(connName)")
} else {
    LuflyLog.shared.info("IMKServer 已建立 conn=\(connName) bundle=\(bundleID)")
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
app.run()
