#!/bin/bash
# 小鹭音形 macOS 部署：构建（带成功守卫）+ 原子替换 + 进程重启。
#
# 事故教训（2026-09-02）：原部署用 `rm -rf 旧app && cp -R 新app`，两步之间
# 有数秒空窗；系统恰好在该空窗校验输入法 bundle，把 Lufly 从「已启用输入法
# 列表」剔除（菜单栏选中态还在）→ 进程永远不被拉起 → 打字无响应且无任何
# 报错。改为「先拷到临时名、两次 mv 原子接力」，空窗缩到一个 rename 调用。
set -e
cd "$(dirname "$0")"

./build.sh > /tmp/lufly_build.log 2>&1 || {
    echo "构建失败，未部署"; tail -30 /tmp/lufly_build.log; exit 1
}
echo "构建 OK"

APP_SRC="$PWD/build/Lufly.app"
osascript - "$APP_SRC" <<'EOF'
on run argv
    set appSrc to item 1 of argv
    do shell script "set -e
DST='/Library/Input Methods/Lufly.app'
TMP='/Library/Input Methods/.Lufly.incoming'
TRASH='/Library/Input Methods/.Lufly.trash'
rm -rf \"$TMP\" \"$TRASH\"
cp -R " & quoted form of appSrc & " \"$TMP\"
[ -d \"$DST\" ] && mv \"$DST\" \"$TRASH\"
mv \"$TMP\" \"$DST\"
rm -rf \"$TRASH\"
chown -R root:wheel \"$DST\"" with administrator privileges
end run
EOF
echo "部署完成（原子替换）"
killall Lufly 2>/dev/null || true
