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

#ifdef __cplusplus
}
#endif

#endif // LUFLY_CAPI_H_
