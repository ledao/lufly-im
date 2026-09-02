// 自安装器 —— macOS 输入法的惯例分发方式（搜狗/百度 Mac 版同款）:
// 输入法装在 ~/Library/Input Methods（不是 /Applications），没法拖拽安装，
// 所以 dmg 里的 Lufly.app 双击后自己弹原生安装窗，一键落位 + 注册。
// 从已安装位置启动时（系统拉起）走正常输入法流程，不进这里。
import AppKit
import Carbon.HIToolbox

enum Installer {
    /// 运行位置是否为已安装目录（系统启动输入法只认这里）
    static var isInstalledLocation: Bool {
        Bundle.main.bundlePath.contains("/Input Methods/")
    }

    static func run() -> Never {
        NSApplication.shared.activate(ignoringOtherApps: true)
        if CommandLine.arguments.contains("--install") {
            // 非交互模式（脚本/测试用）: 静默安装，结果打 stdout
            let ok = install()
            print(ok ? "安装成功: \(targetPath)" : "安装失败（详见上方输出）")
            exit(ok ? 0 : 1)
        }
        let alert = NSAlert()
        alert.messageText = "安装「小鹭音形」输入法"
        alert.informativeText = "小鹭音形是顶功音形输入法：音码起手、形码收尾，"
            + "全码唯一自动挂起、下一键顶字上屏，快打全程无需空格。\n\n"
            + "将安装到当前用户输入法目录（~/Library/Input Methods），无需管理员权限。"
        alert.addButton(withTitle: "安装")
        alert.addButton(withTitle: "退出")
        guard alert.runModal() == .alertFirstButtonReturn else {
            exit(0)
        }
        _ = install()

        let done = NSAlert()
        done.messageText = "安装完成"
        done.informativeText = "最后一步 —— 添加输入法（仅需一次）：\n\n"
            + "① 系统设置 → 键盘 → 输入法 → 编辑…\n"
            + "② 若列表里已有「小鹭音形」，先选中点 − 删除\n"
            + "③ 点 ＋ → 简体中文 → 选「小鹭音形」→ 添加\n"
            + "④ 菜单栏切换到「小鹭音形」即可打字（Shift 单击切中英）\n\n"
            + "若列表里暂时没有它：注销并重新登录后再添加。"
        done.addButton(withTitle: "打开系统设置")
        done.addButton(withTitle: "完成")
        if done.runModal() == .alertFirstButtonReturn {
            // macOS 13+ 键盘设置深链
            if let url = URL(string: "x-apple.systempreferences:com.apple.Keyboard-Settings.extension") {
                NSWorkspace.shared.open(url)
            }
        }
        exit(0)
    }

    private static var targetPath: String {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Input Methods/Lufly.app").path
    }

    /// 落位 + 免注销注册。返回是否成功。
    @discardableResult
    private static func install() -> Bool {
        let fm = FileManager.default
        let dst = URL(fileURLWithPath: targetPath)
        // 安装器包（独立 Bundle ID）内嵌真输入法 → 拷内嵌的；
        // 输入法本体被直接运行时没有内嵌副本 → 拷自己
        let embedded = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/Lufly.app")
        let src = fm.fileExists(atPath: embedded.path) ? embedded : Bundle.main.bundleURL
        print("安装源: \(src.path)")
        print("安装到: \(dst.path)")
        do {
            // 停掉已安装位置的旧进程（按路径精确匹配，别误杀 dmg 里正在跑的自己）
            for running in NSWorkspace.shared.runningApplications
            where running.bundleURL?.path.hasSuffix("Input Methods/Lufly.app") == true {
                running.terminate()
            }
            if fm.fileExists(atPath: dst.path) {
                try fm.removeItem(at: dst)
            }
            try fm.copyItem(at: src, to: dst)
        } catch {
            print("拷贝失败: \(error)")
            if NSApp.isActive {
                let alert = NSAlert()
                alert.messageText = "安装失败"
                alert.informativeText = "\(error.localizedDescription)\n\n请确认 dmg 已挂载后重试。"
                alert.runModal()
            }
            return false
        }
        // 不做主动注册（TISRegisterInputSource）: 实测自动注册出来的输入法条目
        // 能出现在列表里但打不了字，用户仍须「− 删除 + 添加」手动来一遍，等于
        // 白注册还留了个要清理的坏条目（2026-09-02 用户实测裁定）。安装器只负责
        // 落位 + 弹指引让用户自己添加。
        cleanupLegacySystemCopy()
        return true
    }

    /// 清理拖拽式安装时代残留的系统目录版本: 同 Bundle ID 两份并存会让
    /// TIS 注册混乱（实测: 删除重装后拖拽版不被重新注册 → 输入法消失）。
    /// /Library/Input Methods 归 root，普通删除失败时请求管理员授权
    /// （搜狗/百度安装器同款密码弹窗）；非交互模式只打警告。
    private static func cleanupLegacySystemCopy() {
        let path = "/Library/Input Methods/Lufly.app"
        let fm = FileManager.default
        guard fm.fileExists(atPath: path) else { return }
        // 目录恰好可写（如同用户装过）则静默删除
        if (try? fm.removeItem(atPath: path)) != nil, !fm.fileExists(atPath: path) {
            print("已清理旧版残留: \(path)")
            return
        }
        let interactive = !CommandLine.arguments.contains("--install") && NSApp.isActive
        guard interactive else {
            print("警告: 检测到旧版残留 \(path)（需管理员删除，避免与新版本冲突）")
            return
        }
        var err: NSDictionary?
        NSAppleScript(source:
            "do shell script \"rm -rf '/Library/Input Methods/Lufly.app'\" "
                + "with administrator privileges")?
            .executeAndReturnError(&err)
        if err == nil, !fm.fileExists(atPath: path) {
            print("已清理旧版残留（管理员授权）: \(path)")
            return
        }
        // 用户取消授权或删除失败: 不阻塞安装，但要讲清楚后果
        let alert = NSAlert()
        alert.messageText = "检测到旧版本残留"
        alert.informativeText =
            "系统输入法目录里存在旧版 Lufly（之前拖拽安装留下的），"
            + "可能与新版冲突导致输入法无法使用。\n\n"
            + "请在终端执行以下命令手动删除后重新安装:\n"
            + "sudo rm -rf \"/Library/Input Methods/Lufly.app\""
        alert.runModal()
    }
}
