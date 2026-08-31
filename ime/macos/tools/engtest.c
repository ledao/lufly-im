// 引擎实证: 复现 "whom" 打字流，打印每步 input/候选数/候选文本
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "lufly_capi.h"

static void dump(LuflyEngine *e, const char *tag) {
    const char *in = lufly_input(e);
    int n = lufly_candidate_count(e);
    printf("[%s] input=%-8s cand=%d :", tag, in ? in : "(null)", n);
    for (int i = 0; i < n && i < 6; i++) {
        const char *t = lufly_candidate_text(e, i);
        const char *c = lufly_candidate_code(e, i);
        printf("  %d=%s(%s)", i, t ? t : "nil", c ? c : "nil");
    }
    printf("\n");
}

int main() {
    FILE *f = fopen("build/Lufly.app/Contents/Resources/dict.bin", "rb");
    if (!f) { perror("dict"); return 1; }
    fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *buf = malloc(len);
    fread(buf, 1, len, f); fclose(f);
    LuflyEngine *e = lufly_new(buf, len);
    if (!e) { printf("engine new failed\n"); return 1; }
    // 真实 IME 同款: 加载用户词典
    lufly_user_open(e, "/Users/ledao/Library/Application Support/lufly/user_dict.txt");

    const char *seq = "whom";
    for (const char *p = seq; *p; p++) {
        // 模拟前端每键前的 replay + 可能发生在键间的热重载
        const char *r = lufly_key(e, (unsigned char)*p);
        char tag[8] = {0}; strncat(tag, p, 1);
        printf("key '%c' -> %s\n", *p, r ? r : "(none)");
        dump(e, tag);
    }
    // 退回重测: 空格后重打，模拟连续输入
    lufly_key(e, ' ');
    printf("after space input=%s\n", lufly_input(e));
    lufly_reset(e);
    for (const char *p = "who"; *p; p++) {
        lufly_key(e, (unsigned char)*p);
        dump(e, "re");
    }
    // 关键复现: 编码中热重载（前端每秒误触发一次）
    lufly_reset(e);
    lufly_key(e, 'w'); lufly_key(e, 'h');
    printf("\n-- 编码中热重载 --\n");
    int ch = lufly_user_reload(e);
    printf("reload=%d input=%s cand=%d\n", ch, lufly_input(e), lufly_candidate_count(e));
    lufly_key(e, 'o');
    dump(e, "after_reload_o");
    return 0;
}
