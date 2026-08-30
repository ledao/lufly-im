// 小鹭音形引擎 C ABI 声明（与 ime/capi/src/lib.rs 导出对应）。
// 返回的字符串指针为内部缓存借用，在下一次对该句柄的任意调用前有效。
#ifndef LUFLY_CAPI_H_
#define LUFLY_CAPI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct LuflyEngine LuflyEngine;

/// 加载二进制码表，失败返回 NULL。
LuflyEngine *lufly_new(const uint8_t *dict, size_t len);
void lufly_free(LuflyEngine *handle);

/// 喂入一个按键（Unicode 码位），返回需上屏的文本（可能为 NULL）。
/// 内部会自动刷新预编辑/候选缓存。
const char *lufly_key(LuflyEngine *handle, uint32_t ch);

/// 清空编码缓冲。
void lufly_reset(LuflyEngine *handle);

/// 刷新预编辑/候选缓存。
void lufly_refresh(LuflyEngine *handle);

/// 当前编码缓冲（预编辑串）。
const char *lufly_input(LuflyEngine *handle);

/// 候选数量。
int lufly_candidate_count(LuflyEngine *handle);

/// 第 idx 个候选文本（0 起，越界返回 NULL）。
const char *lufly_candidate_text(LuflyEngine *handle, int idx);

/// 第 idx 个候选是否编码完全命中。
int lufly_candidate_exact(LuflyEngine *handle, int idx);

/// 打开用户词典文件（存在则加载；之后每累计 64 次学习自动原子落盘）。
void lufly_user_open(LuflyEngine *handle, const char *path);

/// 强制落盘用户词典（无变更则不写）。返回 1 表示写了文件。
int lufly_user_flush(LuflyEngine *handle);

/// 热重载用户词典: 合并磁盘最新内容（外部进程追加的自定义词），
/// 随即全量原子落盘。返回 1 表示磁盘有变化。
int lufly_user_reload(LuflyEngine *handle);

/// 推导一个词的默认全码（ojc 加词: 单字=4码全码；多字=双拼+首末形码各1）。
/// 失败返回 NULL。返回指针在下次调用前有效。
const char *lufly_derive_word(LuflyEngine *handle, const char *word);

/// 添加自定义词（ojc 加词）: 词条立即生效并强制落盘。成功返回 1。
int lufly_user_add_word(LuflyEngine *handle, const char *code, const char *text);

/// 记录一次真实上屏 (code, text)，用于词频自学习（同码撞车时常用词排前）。
void lufly_learn(LuflyEngine *handle, const char *code, const char *text);

#ifdef __cplusplus
}
#endif

#endif // LUFLY_CAPI_H_
