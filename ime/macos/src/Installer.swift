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
            if install(), let vol = currentDmgVolume() {
                // 从 dmg 安装: 收尾交给已落位真身（完成器）——我们自己弹不动
                // 脚下的盘、也清不掉自己的注册（挂载中 lsregister -u 失败）
                spawnFinisher(volume: vol)
                exit(0)
            }
        case .alertSecondButtonReturn:
            confirmUninstall() // 确认 → 卸载 → 结果弹窗，内部 exit
        default:
            exit(0)
        }

        showDoneDialog()
    }

    /// 安装完成指引（「− 删 + ＋ 加」）。ejectFailed: 安装盘没能自动弹出时
    /// 追加提醒先手动推出，避免添加键盘时 dmg 注册仍在场抢绑定。
    private static func showDoneDialog(ejectFailed: Bool = false) -> Never {
        let done = NSAlert()
        done.messageText = "安装完成"
        done.informativeText = (ejectFailed
            ? "安装盘未能自动弹出——请先手动推出安装盘，再执行下面步骤。\n\n"
            : "")
            + "最后一步 —— 添加输入法（仅需一次）：\n\n"
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

    /// 安装收尾完成器（已落位真身以 `--finish-install <卷路径>` 运行）:
    /// ① 重试弹载安装盘（dmg 安装实例退出后卷即无人占用，至多 15s）
    /// ② 擦掉刚消失的 /Volumes 死注册（实证: 路径消失后 lsregister -u 才有效，
    ///    挂载中反而失败——所以这步只能在弹载之后、由不在卷上的进程做）
    /// ③ 弹添加键盘指引。此刻 LaunchServices 只剩真身，用户添加即正确绑定。
    static func finishInstall(volume: String?) -> Never {
        NSApplication.shared.activate(ignoringOtherApps: true)
        var ejected = true
        if let volume {
            ejected = false
            for _ in 0..<15 {
                if runToolBool("/usr/bin/hdiutil", ["detach", volume]) {
                    print("安装盘已弹出: \(volume)")
                    ejected = true
                    break
                }
                Thread.sleep(forTimeInterval: 1)
            }
            purgeStaleRegistrations(keeping: targetPath)
        }
        showDoneDialog(ejectFailed: !ejected)
    }

    /// 当前是否从 dmg（/Volumes）运行
    private static var isRunningFromDmg: Bool { currentDmgVolume() != nil }

    /// dmg 实例的安装盘卷根路径（非 /Volumes 运行返回 nil）
    private static func currentDmgVolume() -> String? {
        let path = Bundle.main.bundlePath
        guard path.hasPrefix("/Volumes/") else { return nil }
        guard let name = path.dropFirst("/Volumes/".count).split(separator: "/").first else {
            return nil
        }
        return "/Volumes/\(name)"
    }

    /// 让已落位真身接管收尾（不等待——dmg 实例随即退出，完成器重试弹载）
    private static func spawnFinisher(volume: String) {
        let exe = URL(fileURLWithPath: targetPath).appendingPathComponent("Contents/MacOS/Lufly")
        let p = Process()
        p.executableURL = exe
        p.arguments = ["--finish-install", volume]
        p.standardOutput = Pipe()
        p.standardError = Pipe()
        do {
            try p.run()
        } catch {
            print("完成器启动失败: \(error)（请手动推出安装盘）")
        }
    }

    private static var targetPath: String {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Input Methods/Lufly.app").path
    }

    /// 落位 + 清理旧状态。返回是否成功。
    /// 顺序纪律与 uninstall() 一致（2026-10-16 事故: 安装时未停 TIS/未终止旧
    /// 进程就删 /Library 残留，正在服务的会话被斩断 + LaunchServices 僵尸注册
    /// 抢绑定 → 装完打不出字）:
    ///   ① TIS 停用（等同设置里按 −）→ ② 终止旧副本进程并等退出
    ///   → ③ 原子替换落位（rm+cp 有空窗，系统恰在空窗校验会把输入法从启用
    ///      列表剔除，deploy.sh 同教训）→ ④ 清 LaunchServices 僵尸注册并
    ///      重注册真身（dmg 挂载/直接跑 build 版都会各攒一份同 Bundle ID
    ///      注册，会话绑到死副本即打不出字）→ ⑤ 清 /Library 残留（此时已无
    ///      会话无进程，安全）。弹载与 /Volumes 死注册清理由完成器在弹载后
    ///      执行（见 finishInstall）——挂载中 lsregister -u 失败，必须先弹载。
    /// 用户随后「− 删 + ＋ 加」重加一次即绑定到唯一真身。
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

        disableInputSources()
        terminateOtherCopies()

        // 原子替换: 先拷到同目录临时名，再 rename 换入（无空窗）
        let tmp = dst.deletingLastPathComponent()
            .appendingPathComponent("Lufly.app.new-\(ProcessInfo.processInfo.processIdentifier)")
        do {
            try? fm.removeItem(at: tmp) // 上次失败残留
            try fm.copyItem(at: src, to: tmp)
            if fm.fileExists(atPath: dst.path) {
                _ = try fm.replaceItemAt(dst, withItemAt: tmp)
            } else {
                try fm.moveItem(at: tmp, to: dst)
            }
        } catch {
            try? fm.removeItem(at: tmp)
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
        purgeStaleRegistrations(keeping: targetPath)
        removeSystemCopy(forInstall: true)
        // 弹载与 /Volumes 死注册清理不在本进程做（从 dmg 运行时弹不动脚下的盘、
        // 挂载中 lsregister -u 也失败）——GUI 流程由完成器接管（见 run()）；
        // 脚本模式提示手动处理
        if isRunningFromDmg {
            print("提示: 从 dmg 运行的脚本安装请随后手动推出安装盘，"
                + "或执行: \"\(targetPath)/Contents/MacOS/Lufly\" --finish-install <卷路径>")
        }
        return true
    }

    /// 终止已安装位置（~/Library 与 /Library 都匹配后缀）运行的旧副本进程，
    /// 排除自身，最多等 2s 确认退出——不等退出就删文件，旧进程还攥着会话与文件。
    private static func terminateOtherCopies() {
        let selfPid = ProcessInfo.processInfo.processIdentifier
        for running in NSWorkspace.shared.runningApplications
        where running.bundleURL?.path.hasSuffix("Input Methods/Lufly.app") == true
            && running.processIdentifier != selfPid {
            running.terminate()
            let deadline = Date().addingTimeInterval(2)
            while !running.isTerminated && Date() < deadline {
                Thread.sleep(forTimeInterval: 0.05)
            }
        }
    }

    /// 清 LaunchServices 里同 Bundle ID 的僵尸注册（dmg 挂载、打包 staging、
    /// 直接跑 build 版、/Library 残留都会各注册一份；会话绑到任一死副本 =
    /// 打不出字无报错）。keeping 保留的路径（安装语境 = 真身，卸载语境传 nil
    /// 全清），清完对保留路径强制重注册刷新记录。
    private static func purgeStaleRegistrations(keeping keep: String?) {
        let lsreg = "/System/Library/Frameworks/CoreServices.framework"
            + "/Frameworks/LaunchServices.framework/Support/lsregister"
        guard let dump = runTool(lsreg, ["-dump"]) else {
            print("警告: 无法读取 LaunchServices 注册表，跳过僵尸清理")
            return
        }
        var paths = Set<String>()
        if let re = try? NSRegularExpression(pattern: "/[^\\n;()\"',<>]*Lufly\\.app") {
            let ns = dump as NSString
            re.enumerateMatches(in: dump, range: NSRange(location: 0, length: ns.length)) { m, _, _ in
                guard let m else { return }
                paths.insert(ns.substring(with: m.range))
            }
        }
        for p in paths.sorted() where p != keep {
            _ = runTool(lsreg, ["-u", p])
            print("已清除僵尸注册: \(p)")
        }
        if let keep, !runToolBool(lsreg, ["-f", keep]) {
            print("警告: 重注册 \(keep) 失败")
        }
    }

    /// 跑外部工具拿 stdout（失败/非零退出返回 nil）。
    /// 必须先 readDataToEndOfFile 再 waitUntilExit: lsregister -dump 有几 MB，
    /// 先等退出后读会写满 64KB 管道缓冲 → 子进程阻塞在 write → 互等死锁。
    @discardableResult
    private static func runTool(_ path: String, _ args: [String]) -> String? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let out = Pipe()
        p.standardOutput = out
        p.standardError = Pipe()
        do {
            try p.run()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            guard p.terminationStatus == 0 else { return nil }
            return String(data: data, encoding: .utf8)
        } catch { return nil }
    }

    private static func runToolBool(_ path: String, _ args: [String]) -> Bool {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let out = Pipe()
        p.standardOutput = out
        p.standardError = Pipe()
        do {
            try p.run()
            // 同上: 必须先排干输出再等退出，防大输出撑爆管道缓冲死锁
            _ = out.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            return p.terminationStatus == 0
        } catch { return false }
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
        terminateOtherCopies()
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
        // 本体已全删: LaunchServices 里的注册一并清空（含 dmg/build 等僵尸）
        purgeStaleRegistrations(keeping: nil)
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
