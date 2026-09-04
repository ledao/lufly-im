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
        alert.addButton(withTitle: "卸载")
        alert.addButton(withTitle: "退出")
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            _ = install()
        case .alertSecondButtonReturn:
            confirmUninstall() // 确认 → 卸载 → 结果弹窗，内部 exit
        default:
            exit(0)
        }

        let done = NSAlert()
        done.messageText = "安装完成"
        done.informativeText = "最后一步 —— 添加输入法（仅需一次）：\n\n"
            + "① 系统设置 → 键盘 → 输入法 → 编辑…\n"
            + "② 若列表里已有「小鹭音形」，先选中点 − 删除\n"
            + "③ 点 ＋ → 简体中文 → 选「小鹭音形」→ 添加\n"
            + "④ 菜单栏切换到「小鹭音形」即可打字（Shift 单击切中英）\n\n"
            + "若列表里暂时没有它：注销并重新登录后再添加。\n\n"
            + "日后想卸载：菜单栏点输入法图标 → 「卸载小鹭音形」。"
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
        removeSystemCopy(forInstall: true)
        return true
    }

    /// 非交互卸载（`Lufly --uninstall`，装没装的位置运行都行）: 结果打 stdout。
    static func runUninstallCli() -> Never {
        let ok = uninstall()
        print(ok
            ? "卸载成功: 已从输入法列表移除并删除程序本体\n"
                + "造词词典保留在 ~/Library/Application Support/lufly（不需要可手动删）"
            : "卸载失败（详见上方输出）")
        exit(ok ? 0 : 1)
    }

    /// 交互卸载（dmg 卸载按钮 / 输入法菜单里的「卸载」共用）: 确认 → 卸载 →
    /// 结果弹窗。结束即 exit。
    static func confirmUninstall() -> Never {
        let fm = FileManager.default
        let legacyExists = fm.fileExists(atPath: "/Library/Input Methods/Lufly.app")
        guard fm.fileExists(atPath: targetPath) || legacyExists else {
            let alert = NSAlert()
            alert.messageText = "未检测到已安装的小鹭音形"
            alert.informativeText = "若之前已手动删除，直接退出即可。"
            alert.runModal()
            exit(0)
        }
        let alert = NSAlert()
        alert.messageText = "卸载「小鹭音形」？"
        alert.informativeText = "将从系统输入法列表移除并删除程序本体，无需注销。\n\n"
            + "造词词典会保留在 ~/Library/Application Support/lufly，"
            + "不需要可卸载后手动删除该文件夹。"
        alert.addButton(withTitle: "卸载")
        alert.addButton(withTitle: "取消")
        guard alert.runModal() == .alertFirstButtonReturn else { exit(0) }
        let ok = uninstall()
        let done = NSAlert()
        done.messageText = ok ? "已卸载" : "卸载未完成"
        done.informativeText = ok
            ? "「小鹭音形」已从输入法列表移除。\n\n"
                + "造词词典保留在 ~/Library/Application Support/lufly，"
                + "彻底清除可手动删除该文件夹。"
            : "部分步骤失败（详见上方输出），可重试，或手动删除\n"
                + "~/Library/Input Methods/Lufly.app"
        done.runModal()
        exit(0)
    }

    /// 停用输入源（TIS 层面，等价于用户在系统设置里选中按 −）→ 停进程 → 删本体。
    /// 本体可能在 ~/Library（安装器装的）或 /Library（拖拽时代装的，归 root，
    /// 走管理员授权）。返回是否成功。
    @discardableResult
    private static func uninstall() -> Bool {
        let fm = FileManager.default
        disableInputSources()
        // 停掉已安装位置运行的进程（按路径精确匹配；别把跑卸载的自己杀了）
        let selfPid = ProcessInfo.processInfo.processIdentifier
        for running in NSWorkspace.shared.runningApplications
        where running.bundleURL?.path.hasSuffix("Input Methods/Lufly.app") == true
            && running.processIdentifier != selfPid {
            running.terminate()
        }
        do {
            if fm.fileExists(atPath: targetPath) {
                try fm.removeItem(atPath: targetPath)
            }
            print("已删除: \(targetPath)")
        } catch {
            print("删除失败: \(error)")
            if NSApp.isActive {
                let alert = NSAlert()
                alert.messageText = "卸载失败"
                alert.informativeText = "\(error.localizedDescription)"
                alert.runModal()
            }
            return false
        }
        removeSystemCopy(forInstall: false)
        return true
    }

    /// 把本输入法从「已启用输入源」移除。必须先于删文件执行——先删文件再停用
    /// 会在设置列表留幽灵条目（TIS 缓存，同安装侧换 Bundle ID 斩缓存的教训）；
    /// 当前正用它打字时 deselect 会让系统切回上一个输入源。
    private static func disableInputSources() {
        // 安装器与输入法本体同 Bundle ID；若哪天做成内嵌式独立 ID 安装器包，
        // 这里兜底读内嵌副本的 ID
        var ids = [Bundle.main.bundleIdentifier].compactMap { $0 }
        let embeddedPlist = Bundle.main.bundleURL
            .appendingPathComponent("Contents/Resources/Lufly.app/Contents/Info.plist")
        if let dict = NSDictionary(contentsOfFile: embeddedPlist.path),
           let id = dict["CFBundleIdentifier"] as? String, !ids.contains(id) {
            ids.append(id)
        }
        for id in ids {
            let filter = [kTISPropertyBundleID as String: id] as CFDictionary
            guard let list = TISCreateInputSourceList(filter, true)?
                .takeRetainedValue() as? [TISInputSource] else { continue }
            for src in list {
                TISDeselectInputSource(src)
                TISDisableInputSource(src)
            }
        }
    }

    /// 删除 /Library/Input Methods/Lufly.app（系统目录）。安装语境 = 清理拖拽
    /// 时代残留（同 Bundle ID 两份并存会让 TIS 注册混乱，实测: 删除重装后拖拽
    /// 版不被重新注册 → 输入法消失）；卸载语境 = 那可能就是本体。归 root，
    /// 直接删除失败时请求管理员授权（搜狗/百度安装器同款密码弹窗）；
    /// --install/--uninstall 脚本模式只打警告不弹窗。
    private static func removeSystemCopy(forInstall: Bool) {
        let path = "/Library/Input Methods/Lufly.app"
        let fm = FileManager.default
        guard fm.fileExists(atPath: path) else { return }
        // 目录恰好可写则静默删除
        if (try? fm.removeItem(atPath: path)) != nil, !fm.fileExists(atPath: path) {
            print("已清理系统目录副本: \(path)")
            return
        }
        let scripted = CommandLine.arguments.contains("--install")
            || CommandLine.arguments.contains("--uninstall")
        guard !scripted else {
            print("警告: 系统目录存在 Lufly \(path)（需管理员删除）")
            return
        }
        var err: NSDictionary?
        NSAppleScript(source:
            "do shell script \"rm -rf '/Library/Input Methods/Lufly.app'\" "
                + "with administrator privileges")?
            .executeAndReturnError(&err)
        if err == nil, !fm.fileExists(atPath: path) {
            print("已清理系统目录副本（管理员授权）: \(path)")
            return
        }
        // 用户取消授权或删除失败: 不阻塞主流程，但要讲清楚后果
        let alert = NSAlert()
        alert.messageText = forInstall ? "检测到旧版本残留" : "程序本体未能删除"
        alert.informativeText = forInstall
            ? "系统输入法目录里存在旧版 Lufly（之前拖拽安装留下的），"
                + "可能与新版冲突导致输入法无法使用。\n\n"
                + "请在终端执行以下命令手动删除后重试:\n"
                + "sudo rm -rf \"/Library/Input Methods/Lufly.app\""
            : "本体在系统输入法目录里，删除需要管理员权限（未授权或失败）。\n"
                + "输入法已从系统列表移除，不再可用；想删净文件请在终端执行:\n"
                + "sudo rm -rf \"/Library/Input Methods/Lufly.app\""
        alert.runModal()
    }
}
