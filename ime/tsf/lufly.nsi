; 小鹭音形输入法 Windows 安装包（NSIS / MUI2）
; 构建: makensis lufly.nsi  →  ..\dist\LuflyIME-Setup-0.5.13.exe
; 双架构: 微信/企业微信/QQ 等主程序是 32 位，读 WOW6432Node 视图 —— x64/x86
; 两个 DLL 各自用对应位数的 regsvr32 注册（x64 经 Sysnative 直达真实 System32）。
; 升级安装: DLL 装在版本号子目录，跨版本新目录永无文件锁；同版本重跑时
; 旧 DLL 与码表改名腾位（被加载/被 mmap 时删不掉、同卷可改名）；旧文件重启后清理

Unicode true
; 高分屏（150%/4K）下向导不模糊
ManifestDPIAware true
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

; --- 常量 ---
!define PRODUCT_NAME "小鹭音形输入法"
!define PRODUCT_PUBLISHER "小鹭音形开发组"
!define VER "0.5.13"
!define PROFILE_GUID "{7C3A1E92-5D4F-4B68-9A2C-E1F0B3D4A5C6}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\LuflyIME"
!define CLSID_STR "{2E168808-0490-43E1-9481-F2662BB32954}"

Name "${PRODUCT_NAME} ${VER}"
OutFile "..\dist\LuflyIME-Setup-${VER}.exe"
InstallDir "$PROGRAMFILES64\LuflyIME"
RequestExecutionLevel admin
ShowInstDetails hide
ShowUnInstDetails hide

; --- MUI 设置 ---
!define MUI_ABORTWARNING
!define MUI_ICON "lufly.ico"
!define MUI_UNICON "lufly.ico"

!define MUI_WELCOMEPAGE_TEXT "本向导将引导您完成「小鹭音形输入法」的安装。$\r$\n$\r$\n安装需要管理员权限，过程中会重启系统文本服务（ctfmon）。$\r$\n$\r$\n点击“下一步”继续。"

; --- 向导页面：欢迎 → 许可协议（拒绝即退出） → 目录 → 安装 → 完成 ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_TEXT "安装完成。$\r$\n$\r$\n安装器不会自动把键盘加入输入法列表，请手动添加一次：$\r$\n    设置 → 时间和语言 → 语言和区域 → 中文(简体，中国) → 添加键盘 → 小鹭音形$\r$\n$\r$\n已打开的程序仍在使用旧版输入法，请重启这些程序后再使用。$\r$\n$\r$\n首次切换后请稍候 1~2 秒，码表正在后台加载。"
!insertmacro MUI_PAGE_FINISH

; --- 卸载向导 ---
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
  ; 只支持 64 位 x64 系统。
  ;  - 32 位 Windows: x64 TIP 无从注册，装到一半才在回读校验处弹错
  ;  - ARM64 Windows: ${RunningX64} 为真（x86 安装器跑在 WOW64 里），但 Sysnative
  ;    落到的是 ARM64 的 regsvr32，加载不了 x64 DLL —— 注册同样必失败，而回读
  ;    校验只会误导用户「请重启后重试」。需另出 aarch64 版本，故在此明确拒绝
  ${If} ${IsNativeARM64}
    MessageBox MB_ICONSTOP "「小鹭音形输入法」暂不支持 ARM64 架构的 Windows。$\r$\n$\r$\n请在 x64（Intel / AMD）电脑上安装。"
    Abort
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "「小鹭音形输入法」需要 64 位 Windows。$\r$\n$\r$\n当前系统为 32 位，无法安装。"
    Abort
  ${EndIf}
  ; 已有安装则沿用目录
  ReadRegStr $R0 HKLM "${UNINST_KEY}" "InstallLocation"
  ${If} $R0 != ""
    StrCpy $INSTDIR $R0
  ${EndIf}
  ; 64 位 regsvr32：本安装器是 32 位进程，裸名/System32 会被重定向到 SysWOW64，
  ; 经 Sysnative 才能到达真实 System32（Sysnative 仅 32 位进程可见）
  ${If} ${FileExists} "$WINDIR\Sysnative\regsvr32.exe"
    StrCpy $R7 "$WINDIR\Sysnative\regsvr32.exe"
  ${Else}
    StrCpy $R7 "regsvr32"
  ${EndIf}
FunctionEnd

Section "Install"
  ; 1. 反注册所有已知旧路径（64 位视图）+ 清残留键（两视图）+ 重启文本服务
  ExecWait '"$R7" /u /s "$INSTDIR\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\bin\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.1\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.2\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.3\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.4\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.5\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.6\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.7\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.8\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.2.9\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.3.0\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.3.1\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.4.0\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.4.1\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.4.2\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.0\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.1\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.2\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.3\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.4\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.5\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.6\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.6\lufly_tsf32.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.7\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.7\lufly_tsf32.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.8\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.8\lufly_tsf32.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.9\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.9\lufly_tsf32.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.10\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.10\lufly_tsf32.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.11\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.11\lufly_tsf32.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\0.5.12\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\0.5.12\lufly_tsf32.dll"'
  ; 旧 DLL 可能已删除导致 regsvr32 /u 无效 —— 直接清掉自己的残留键
  ; (含手写时代的脏数据)。64 位与 32 位应用读不同注册表视图，两边都清
  SetRegView 64
  DeleteRegKey HKLM "SOFTWARE\Microsoft\CTF\TIP\${CLSID_STR}"
  DeleteRegKey HKLM "SOFTWARE\Classes\CLSID\${CLSID_STR}"
  SetRegView 32
  DeleteRegKey HKLM "SOFTWARE\Microsoft\CTF\TIP\${CLSID_STR}"
  DeleteRegKey HKLM "SOFTWARE\Classes\CLSID\${CLSID_STR}"
  SetRegView lastused
  ; nsExec 用隐藏控制台跑命令（ExecWait 跑控制台程序会闪黑窗）
  nsExec::Exec 'taskkill /f /im ctfmon.exe'
  Pop $0
  Sleep 800

  ; 2. 写入新版本子目录（跨版本升级 = 新路径永无文件锁；**同版本重跑**才是难点：
  ;    旧 DLL 被 msedge 等应用加载、码表被引擎 mmap，两者都删不掉 —— 但同卷可改名，
  ;    于是先挪成带时戳的 .old 腾位；.old 安排重启后清理。
  ;    实测：被 mmap 的文件改名可行、就地覆盖写返回 ERROR_USER_MAPPED_FILE，
  ;    而 NSIS 的 File 写失败是**静默跳过不报错**，结果会留下「新 DLL + 旧码表」
  ;    的混合安装 —— 所以码表必须和 DLL 一样先腾位）
  SetOutPath "$INSTDIR\${VER}"
  System::Call 'kernel32::GetTickCount()i.R0'
  Delete /REBOOTOK "$INSTDIR\${VER}\lufly_tsf.*.old"
  Delete /REBOOTOK "$INSTDIR\${VER}\lufly_tsf32.*.old"
  Delete /REBOOTOK "$INSTDIR\${VER}\xiaolu_*.bin.*.old"
  Rename "$INSTDIR\${VER}\lufly_tsf.dll" "$INSTDIR\${VER}\lufly_tsf.$R0.old"
  ${If} ${FileExists} "$INSTDIR\${VER}\lufly_tsf.$R0.old"
    Delete /REBOOTOK "$INSTDIR\${VER}\lufly_tsf.$R0.old"
  ${EndIf}
  Rename "$INSTDIR\${VER}\lufly_tsf32.dll" "$INSTDIR\${VER}\lufly_tsf32.$R0.old"
  ${If} ${FileExists} "$INSTDIR\${VER}\lufly_tsf32.$R0.old"
    Delete /REBOOTOK "$INSTDIR\${VER}\lufly_tsf32.$R0.old"
  ${EndIf}
  Rename "$INSTDIR\${VER}\xiaolu_he_he.bin" "$INSTDIR\${VER}\xiaolu_he_he.$R0.old"
  ${If} ${FileExists} "$INSTDIR\${VER}\xiaolu_he_he.$R0.old"
    Delete /REBOOTOK "$INSTDIR\${VER}\xiaolu_he_he.$R0.old"
  ${EndIf}
  Rename "$INSTDIR\${VER}\xiaolu_fuzhu.bin" "$INSTDIR\${VER}\xiaolu_fuzhu.$R0.old"
  ${If} ${FileExists} "$INSTDIR\${VER}\xiaolu_fuzhu.$R0.old"
    Delete /REBOOTOK "$INSTDIR\${VER}\xiaolu_fuzhu.$R0.old"
  ${EndIf}
  File /oname=lufly_tsf.dll "..\target\release\lufly_tsf.dll"
  File /oname=lufly_tsf32.dll "..\target\i686-pc-windows-msvc\release\lufly_tsf.dll"
  ; 码表独立文件（DLL 内不再嵌入; 引擎 mmap 文件页——跨进程共享、
  ; 内存压力下可回收; 0.5.9 及之前为 DLL 自包含）
  File "..\data\xiaolu_he_he.bin"
  File "..\data\xiaolu_fuzhu.bin"
  File "lufly.ico"
  File "lufly-zh.ico"
  File "lufly-en.ico"

  ; 3. 注册新版：两架构各自用对应位数的 regsvr32（写各自的注册表视图）
  ExecWait '"$R7" /s "$INSTDIR\${VER}\lufly_tsf.dll"' $0
  DetailPrint "regsvr32 x64 退出码: $0"
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /s "$INSTDIR\${VER}\lufly_tsf32.dll"' $2
  DetailPrint "regsvr32 x86 退出码: $2"

  ; 3.1 回读校验：regsvr32 /s 静默失败时给用户明确提示
  SetRegView 64
  ReadRegStr $1 HKLM "SOFTWARE\Microsoft\CTF\TIP\${CLSID_STR}\LanguageProfile\0x00000804\${PROFILE_GUID}" "Description"
  SetRegView 32
  ReadRegStr $3 HKLM "SOFTWARE\Microsoft\CTF\TIP\${CLSID_STR}\LanguageProfile\0x00000804\${PROFILE_GUID}" "Description"
  SetRegView lastused
  ${If} $1 == ""
    MessageBox MB_ICONEXCLAMATION "64 位应用注册未完成（regsvr32 退出码 $0）。$\r$\n请重启电脑后再次运行本安装程序；若仍失败，请到 https://github.com/ledao/lufly-im 反馈。"
  ${EndIf}
  ${If} $3 == ""
    MessageBox MB_ICONEXCLAMATION "32 位应用注册未完成（微信/企业微信等将无法使用）。$\r$\n请重启电脑后再次运行本安装程序；若仍失败，请到 https://github.com/ledao/lufly-im 反馈。"
  ${EndIf}

  ; 4. 重启文本服务 UI，输入法立即可见
  Exec '"$SYSDIR\ctfmon.exe"'

  ; 旧文件被占用删不掉时安排重启后清
  Delete /REBOOTOK "$INSTDIR\lufly_tsf.dll"
  Delete /REBOOTOK "$INSTDIR\bin\lufly_tsf.dll"
  ; 早期版本把卸载器写在根目录/bin 下的残留
  Delete /REBOOTOK "$INSTDIR\uninstall.exe"
  Delete /REBOOTOK "$INSTDIR\bin\uninstall.exe"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.1"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.2"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.3"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.4"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.5"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.6"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.7"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.8"
  RMDir /r /REBOOTOK "$INSTDIR\0.2.9"
  RMDir /r /REBOOTOK "$INSTDIR\0.3.0"
  RMDir /r /REBOOTOK "$INSTDIR\0.3.1"
  RMDir /r /REBOOTOK "$INSTDIR\0.4.0"
  RMDir /r /REBOOTOK "$INSTDIR\0.4.1"
  RMDir /r /REBOOTOK "$INSTDIR\0.4.2"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.0"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.1"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.2"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.3"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.4"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.5"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.6"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.7"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.8"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.9"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.10"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.11"
  RMDir /r /REBOOTOK "$INSTDIR\0.5.12"
  RMDir /REBOOTOK "$INSTDIR\bin"

  ; 5. 卸载器与控制面板卸载项
  ;    旧版安装器曾把卸载项写进 32 位视图（WOW6432Node）—— 两视图都清旧，
  ;    再显式写 64 位视图；只写不清会让列表出现两条、旧那条指向已删目录
  SetRegView 32
  DeleteRegKey HKLM "${UNINST_KEY}"
  SetRegView 64
  DeleteRegKey HKLM "${UNINST_KEY}"
  WriteUninstaller "$INSTDIR\${VER}\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VER}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${VER}\lufly.ico"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" "$INSTDIR\${VER}\uninstall.exe"
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
  SetRegView lastused
SectionEnd

Section "Uninstall"
  ; 反注册当前及历史版本（两架构），再整体清两视图残留键
  ${If} ${FileExists} "$WINDIR\Sysnative\regsvr32.exe"
    StrCpy $R7 "$WINDIR\Sysnative\regsvr32.exe"
  ${Else}
    StrCpy $R7 "regsvr32"
  ${EndIf}
  ExecWait '"$R7" /u /s "$INSTDIR\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\bin\lufly_tsf.dll"'
  ExecWait '"$R7" /u /s "$INSTDIR\${VER}\lufly_tsf.dll"'
  ExecWait '"$WINDIR\SysWOW64\regsvr32.exe" /u /s "$INSTDIR\${VER}\lufly_tsf32.dll"'
  SetRegView 64
  DeleteRegKey HKLM "SOFTWARE\Microsoft\CTF\TIP\${CLSID_STR}"
  DeleteRegKey HKLM "SOFTWARE\Classes\CLSID\${CLSID_STR}"
  SetRegView 32
  DeleteRegKey HKLM "SOFTWARE\Microsoft\CTF\TIP\${CLSID_STR}"
  DeleteRegKey HKLM "SOFTWARE\Classes\CLSID\${CLSID_STR}"
  SetRegView lastused
  nsExec::Exec 'taskkill /f /im ctfmon.exe'
  Pop $0
  Sleep 500
  ; 卸载器默认在 %TEMP% 运行副本，可自删目录；占用时重启后清
  RMDir /r /REBOOTOK "$INSTDIR"
  ; 卸载项两视图都删（旧版写在 32 位视图，只删当前视图会留幽灵条目）
  SetRegView 64
  DeleteRegKey HKLM "${UNINST_KEY}"
  SetRegView 32
  DeleteRegKey HKLM "${UNINST_KEY}"
  SetRegView lastused
  Exec '"$SYSDIR\ctfmon.exe"'
SectionEnd
