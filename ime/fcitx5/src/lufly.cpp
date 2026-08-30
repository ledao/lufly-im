// 小鹭音形 —— fcitx5 输入法引擎插件（Linux 前端）。
//
// 架构: 引擎逻辑在 Rust crate `lufly-engine`，经 `lufly-capi`（C ABI staticlib）
// 暴露给本插件；本插件只负责 fcitx5 按键分发、预编辑与候选窗渲染。
//
// 状态模型: 每个 InputContext 一份编码缓冲（LuflyState）。全局只持有一个
// 工作引擎 scratch_，每次按键前把该 IC 的缓冲重放进去（引擎是确定性状态机，
// 缓冲 ≤ 10 字符，重放开销可忽略），避免给每个焦点切换克隆 43MB 码表。
//
// 按键语义:
//   a-z       进编码缓冲（6/8/10…偶数全码唯一 → 顶功挂起，下一键顶出）
//   空格      上屏首选 / 确认挂起字；编码 miss 时清屏（回车上屏英文）
//   1-6       选当前页候选
//   PageUp/Down  翻页
//   回车      编码字母原样上屏
//   退格      删一码；Esc 清空缓冲
//   Shift     单击: 切换中/英文模式（编码中先原样上屏字母再转英文）
//   标点      中文全角化（对齐 rime punctuator half_shape；编码中先顶字）；
//             前面是数字/英文时保持半角（3.14 / hello.），Ctrl+0 强制半角
//   其余按键  不消费、不破坏缓冲（` ~ @ # 等半角键与组合键透传）

#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/candidatelist.h>
#include <fcitx/event.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputcontextproperty.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/inputmethodentry.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx/text.h>
#include <fcitx-utils/capabilityflags.h>
#include <fcitx-utils/key.h>
#include <fcitx-utils/keysym.h>
#include <fcitx-utils/log.h>
#include <fcitx-utils/standardpath.h>

#include <chrono>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include <sys/stat.h>
#include <unistd.h>

#include "lufly_capi.h"

FCITX_DEFINE_LOG_CATEGORY(lufly, "lufly");

#define FCITX_LUFLY_DEBUG() FCITX_LOGC(lufly, Debug)
#define FCITX_LUFLY_ERROR() FCITX_LOGC(lufly, Error)
#define FCITX_LUFLY_INFO() FCITX_LOGC(lufly, Info)

namespace fcitx {

namespace {

// 候选页大小: 对齐 rime menu/page_size，数字 1-5 对应本页 5 个候选。
constexpr int kPageSize = 5;

// 每个 InputContext 的编码缓冲。
class LuflyState : public InputContextProperty {
public:
    std::string buffer;
    // 反查模式: ` 已按下，buffer 为拼音字母（不含 ` 本身）
    bool reverse = false;
    // 英文直通模式（空编码 Shift 单击切换）: 所有按键透传
    bool ascii = false;
    // Shift 已按下且其后无其他按键（单击 commit_code：字母原样上屏）
    bool shiftArmed = false;
    // $/| 已选次选候选，抬键时补发该标点（"。" / "，"）
    const char *pendingPunct = nullptr;
    // 引号配对状态（“‘ 已开待闭）
    bool dqOpen = false;
    bool sqOpen = false;
    // 顶功挂起: 全码唯一已自动选字、但未发送，等下一键顶出/空格确认
    std::string pending;
    // 挂起对应的编码（退格撤销时恢复）
    std::string pendingCode;
    // 上一个输出/透传字符的类别（0=中文/其他 1=ASCII 数字 2=ASCII 字母），
    // 数字/英文后的标点保持半角（3.14 / hello.）
    int lastCls = 0;
    // Ctrl+0 切换: 标点强制半角（对齐 rime ascii_punct）
    bool asciiPunct = false;
    // ojc 加词模式: 1=选词阶段 2=编码编辑阶段（0=非加词）。
    // 全程复用候选窗/预编辑，无外部弹窗（移植性: 零外部依赖）。
    int addStage = 0;
    std::string addWord; // 已选定的词（stage2）
    std::string addCode; // 编码，初始为自动推导（stage2）
    // 自动造词: 连续全码(4键)上屏的单字链（UTF-8 拼接），≥2 字即成词。
    // 任何非「单字+4码」的上屏（简码/选词/标点/英文/回车原样）都断链。
    std::string autoBuf;
};

class LuflyStateFactory : public InputContextPropertyFactory {
public:
    InputContextProperty *create(InputContext &) override {
        return new LuflyState;
    }
};

// 中文标点映射，对齐 rime punctuator half_shape（import_preset: default，
// /usr/share/rime-data/punctuation.yaml）。列表项取第一个；引号按对交替。
// 返回 nullptr 表示 rime 里也是半角的键（` ~ @ # % & * - + = 与字母数字）。
const char *chinesePunct(KeySym sym, LuflyState *st) {
    switch (sym) {
    case FcitxKey_comma: return "，";
    case FcitxKey_period: return "。";
    case FcitxKey_less: return "《";
    case FcitxKey_greater: return "》";
    case FcitxKey_slash: return "、";
    case FcitxKey_question: return "？";
    case FcitxKey_semicolon: return "；";
    case FcitxKey_colon: return "：";
    case FcitxKey_apostrophe:
        st->sqOpen = !st->sqOpen;
        return st->sqOpen ? "‘" : "’";
    case FcitxKey_quotedbl:
        st->dqOpen = !st->dqOpen;
        return st->dqOpen ? "“" : "”";
    case FcitxKey_backslash: return "、";
    case FcitxKey_bar: return "·";
    case FcitxKey_exclam: return "！";
    case FcitxKey_dollar: return "￥";
    case FcitxKey_asciicircum: return "……";
    case FcitxKey_parenleft: return "（";
    case FcitxKey_parenright: return "）";
    case FcitxKey_underscore: return "——";
    case FcitxKey_bracketleft: return "「";
    case FcitxKey_bracketright: return "」";
    case FcitxKey_braceleft: return "『";
    case FcitxKey_braceright: return "』";
    default: return nullptr;
    }
}

// 字符串里的 UTF-8 码点数（判断单字/词长用）
int utf8Chars(const char *s) {
    int n = 0;
    for (const unsigned char *p = reinterpret_cast<const unsigned char *>(s);
         *p; ++p) {
        n += (*p & 0xC0) != 0x80;
    }
    return n;
}

// 候选词: 点击/回车选中后提交并清缓冲。显示文本可带编码后缀，
// 上屏固定用纯词文本（commitText），两者分离防编码漏进文档。
class LuflyCandidateWord : public CandidateWord {
public:
    LuflyCandidateWord(Text text, std::string commitText, class LuflyIm *im)
        : CandidateWord(std::move(text)), commitText_(std::move(commitText)),
          im_(im) {}

    void select(InputContext *ic) const override;

private:
    std::string commitText_;
    LuflyIm *im_;
};

class LuflyIm final : public InputMethodEngineV2 {
public:
    explicit LuflyIm(Instance *instance);
    ~LuflyIm() override;

    void keyEvent(const InputMethodEntry &entry,
                  KeyEvent &event) override;
    void activate(const InputMethodEntry &entry,
                  InputContextEvent &event) override;
    void reset(const InputMethodEntry &entry,
               InputContextEvent &event) override;

    // 供 LuflyCandidateWord::select 回调。
    void commitCandidate(InputContext *ic, const std::string &text);

    // 子模式图标/标签: 随中英文模式切换，托盘 SNI 图标据此刷新
    std::string subModeIconImpl(const InputMethodEntry &,
                                InputContext &ic) override {
        auto *st = this->state(&ic);
        return st && st->ascii ? "lufly-en" : "lufly";
    }
    std::string subModeLabelImpl(const InputMethodEntry &,
                                 InputContext &ic) override {
        auto *st = this->state(&ic);
        return st && st->ascii ? "EN" : "中";
    }

private:
    friend class LuflyCandidateWord;

    LuflyState *state(InputContext *ic) {
        return static_cast<LuflyState *>(ic->property(&factory_));
    }

    bool ensureDict();
    bool ensureRev();
    // 用户词典（词频自学习+自定义词）: XDG 数据目录 lufly/user_dict.txt
    void openUserDict();
    // 用户词典热重载: ojc 弹窗加词后文件变化时合并（有 1s 节流）
    void checkUserReload();
    // 码表热更新: 文件变化时重载（升级码表免重启 fcitx5），有 1s 节流。
    void checkDictReload(bool force = false);
    // 把 IC 缓冲重放到指定引擎（normal=scratch_ / 反查=rev_）。
    void replay(LuflyEngine *eng, const std::string &buffer);
    // 按当前引擎状态刷新预编辑 + 候选窗（空缓冲时清空面板）。
    void updateUI(InputContext *ic, LuflyState *state);

    // ojc 加词·选字: 选中候选追加进词槽，留在选字阶段继续选下一个字
    void appendAddWord(LuflyState *state, const char *text);
    // ojc 加词·选字完成: 推导默认码（固定查主码表）进入编码阶段
    void finishAddWord(LuflyState *state);
    // 退出/取消加词模式
    static void cancelAddWord(LuflyState *state);
    // 自动造词: 上屏钩子。单字+全码(4键) → 拼进 autoBuf，≥2 字成词
    // （走 ojc 同一条 add_user_word: rank0/计数1/常规落盘）；
    // 其余任何上屏断链。词长上限 4 字。
    void noteAutoCommit(LuflyState *state, const std::string &code,
                        const char *text);

    Instance *instance_;
    LuflyStateFactory factory_;
    LuflyEngine *scratch_ = nullptr;
    LuflyEngine *rev_ = nullptr; // 拼音反查码表（懒加载，无热更新）
    bool triedLoad_ = false;
    bool triedRev_ = false;
    KeyList selectionKeys_;
    std::string dictPath_;
    time_t dictMtime_ = 0;
    off_t dictSize_ = 0;
    std::chrono::steady_clock::time_point lastCheck_;
    std::string userPath_;
    time_t userMtime_ = 0;
    off_t userSize_ = 0;
    std::chrono::steady_clock::time_point lastUserCheck_;
};

LuflyIm::LuflyIm(Instance *instance) : instance_(instance) {
    for (int i = 0; i < kPageSize; i++) {
        selectionKeys_.emplace_back(static_cast<KeySym>(FcitxKey_1 + i));
    }
    instance_->inputContextManager().registerProperty("lufly", &factory_);
    // 随 fcitx5 启动预加载码表（约 150ms），首键零延迟
    ensureDict();
}

LuflyIm::~LuflyIm() {
    if (scratch_) {
        lufly_user_flush(scratch_);
        lufly_free(scratch_);
    }
    if (rev_) {
        lufly_free(rev_);
    }
}

bool LuflyIm::ensureDict() {
    if (scratch_) {
        return true;
    }
    if (triedLoad_) {
        return false;
    }
    triedLoad_ = true;

    std::string path;
    if (const char *env = getenv("LUFLY_DICT")) {
        path = env;
    }
    if (path.empty()) {
        path = StandardPath::global().locate(StandardPath::Type::PkgData,
                                             "lufly/dict.bin");
    }
    if (path.empty()) {
        FCITX_LUFLY_ERROR()
            << "lufly: 未找到码表（XDG 数据目录 lufly/dict.bin 或 $LUFLY_DICT）";
        return false;
    }

    std::ifstream in(path, std::ios::binary);
    if (!in) {
        FCITX_LUFLY_ERROR() << "lufly: 码表读取失败 " << path;
        return false;
    }
    std::vector<char> bytes((std::istreambuf_iterator<char>(in)),
                            std::istreambuf_iterator<char>());
    scratch_ = lufly_new(reinterpret_cast<const uint8_t *>(bytes.data()),
                         bytes.size());
    if (!scratch_) {
        FCITX_LUFLY_ERROR() << "lufly: 码表解析失败 " << path;
        return false;
    }
    dictPath_ = path;
    struct stat st;
    if (stat(path.c_str(), &st) == 0) {
        dictMtime_ = st.st_mtime;
        dictSize_ = st.st_size;
    }
    openUserDict();
    FCITX_LUFLY_INFO() << "lufly: 码表加载成功 " << path;
    return true;
}

// 用户词典: $LUFLY_USER_DICT 或 XDG 数据目录 lufly/user_dict.txt。
// 存在则加载；之后每次学习由 capi 计数，每 64 次自动原子落盘。
void LuflyIm::openUserDict() {
    std::string path;
    if (const char *env = getenv("LUFLY_USER_DICT")) {
        path = env;
    }
    if (path.empty()) {
        if (const char *env = getenv("XDG_DATA_HOME")) {
            path = std::string(env) + "/lufly/user_dict.txt";
        } else if (const char *home = getenv("HOME")) {
            path = std::string(home) + "/.local/share/lufly/user_dict.txt";
        }
    }
    if (path.empty()) {
        return;
    }
    lufly_user_open(scratch_, path.c_str());
    userPath_ = path;
    struct stat st;
    if (stat(path.c_str(), &st) == 0) {
        userMtime_ = st.st_mtime;
        userSize_ = st.st_size;
    }
    FCITX_LUFLY_INFO() << "lufly: 用户词典 " << path;
}

// 用户词典热重载: ojc 弹窗管线追加自定义词后，文件 mtime/size 变化时
// 合并进引擎（lufly_user_reload 会顺带全量去重落盘）。1s 节流。
void LuflyIm::checkUserReload() {
    if (!scratch_ || userPath_.empty()) {
        return;
    }
    auto now = std::chrono::steady_clock::now();
    if (now - lastUserCheck_ < std::chrono::seconds(1)) {
        return;
    }
    lastUserCheck_ = now;

    struct stat st;
    if (stat(userPath_.c_str(), &st) != 0) {
        return;
    }
    if (st.st_mtime == userMtime_ && st.st_size == userSize_) {
        return;
    }
    userMtime_ = st.st_mtime;
    userSize_ = st.st_size;
    if (lufly_user_reload(scratch_)) {
        FCITX_LUFLY_INFO() << "lufly: 用户词典已热更新 " << userPath_;
    }
}

// ojc 加词·选字: 选中候选进词槽（要加的词不在码表，整词选不出，只能逐字
// 选出来拼成词），留在选字阶段；反查选中后一并退出反查。
void LuflyIm::appendAddWord(LuflyState *state, const char *text) {
    state->addWord += text;
    state->buffer.clear();
    state->reverse = false;
    state->addStage = 1;
}

// 选字完成 → 编码阶段: derive 固定查主码表（反查态的 eng 是 fuzhu）
void LuflyIm::finishAddWord(LuflyState *state) {
    const char *d =
        scratch_ ? lufly_derive_word(scratch_, state->addWord.c_str()) : nullptr;
    state->addCode = d ? d : "";
    state->buffer.clear();
    state->reverse = false;
    state->addStage = 2;
}

void LuflyIm::cancelAddWord(LuflyState *state) {
    state->addStage = 0;
    state->addWord.clear();
    state->addCode.clear();
    state->autoBuf.clear();
}

// 自动造词: 用户连续以 4 键全码打字上屏时，把这些字拼成自动词。
// 例: 连续全码打「乐」「乐」→ 造出 lelemb（双拼+首末形码）→ 乐乐，
// 之后打该码即可出词；learn 随使用自然提频。断链 = 任何非「单字+4码」
// 的上屏（简码选字/词上屏/标点/英文/回车原样都到不了这里或被显式清）。
void LuflyIm::noteAutoCommit(LuflyState *state, const std::string &code,
                             const char *text) {
    if (code.size() != 4 || utf8Chars(text) != 1) {
        state->autoBuf.clear();
        return;
    }
    state->autoBuf += text;
    const int n = utf8Chars(state->autoBuf.c_str());
    if (n < 2) {
        return;
    }
    if (n > 4) { // 词长上限 4 字，超长断链防串词
        state->autoBuf.clear();
        return;
    }
    if (scratch_) {
        if (const char *d =
                lufly_derive_word(scratch_, state->autoBuf.c_str())) {
            lufly_user_add_word(scratch_, d, state->autoBuf.c_str());
        }
    }
}

// 反查码表（拼音→单字，fuzhu.bin）: 懒加载，首次按 ` 时才读。
bool LuflyIm::ensureRev() {
    if (rev_) {
        return true;
    }
    if (triedRev_) {
        return false;
    }
    triedRev_ = true;

    std::string path;
    if (const char *env = getenv("LUFLY_FUZHU")) {
        path = env;
    }
    if (path.empty()) {
        path = StandardPath::global().locate(StandardPath::Type::PkgData,
                                             "lufly/fuzhu.bin");
    }
    if (path.empty()) {
        FCITX_LUFLY_ERROR() << "lufly: 未找到反查码表（lufly/fuzhu.bin 或 $LUFLY_FUZHU）";
        return false;
    }

    std::ifstream in(path, std::ios::binary);
    if (!in) {
        FCITX_LUFLY_ERROR() << "lufly: 反查码表读取失败 " << path;
        return false;
    }
    std::vector<char> bytes((std::istreambuf_iterator<char>(in)),
                            std::istreambuf_iterator<char>());
    rev_ = lufly_new(reinterpret_cast<const uint8_t *>(bytes.data()),
                     bytes.size());
    if (!rev_) {
        FCITX_LUFLY_ERROR() << "lufly: 反查码表解析失败 " << path;
        return false;
    }
    FCITX_LUFLY_INFO() << "lufly: 反查码表加载成功 " << path;
    return true;
}

void LuflyIm::checkDictReload(bool force) {
    if (!scratch_ || dictPath_.empty()) {
        return;
    }
    auto now = std::chrono::steady_clock::now();
    if (!force && now - lastCheck_ < std::chrono::seconds(1)) {
        return;
    }
    lastCheck_ = now;

    struct stat st;
    if (stat(dictPath_.c_str(), &st) != 0) {
        return;
    }
    if (st.st_mtime == dictMtime_ && st.st_size == dictSize_) {
        return;
    }
    lufly_user_flush(scratch_);
    lufly_free(scratch_);
    scratch_ = nullptr;
    triedLoad_ = false;
    if (ensureDict()) {
        FCITX_LUFLY_INFO() << "lufly: 码表已热更新 " << dictPath_;
    }
}

void LuflyIm::replay(LuflyEngine *eng, const std::string &buffer) {
    lufly_reset(eng);
    for (unsigned char c : buffer) {
        lufly_key(eng, c);
    }
}

void LuflyIm::updateUI(InputContext *ic, LuflyState *state) {
    auto *eng = state->reverse ? rev_ : scratch_;
    auto &panel = ic->inputPanel();
    if (state->buffer.empty()) {
        panel.reset();
        // ojc 加词·编码阶段: 显示词与编码（可编辑），回车/空格确认
        if (state->addStage == 2) {
            Text preedit;
            preedit.append("加词:" + state->addWord + " · 编码:" + state->addCode,
                           TextFormatFlag::Underline);
            preedit.setCursor(static_cast<int>(preedit.textLength()));
            if (ic->capabilityFlags().test(CapabilityFlag::Preedit)) {
                panel.setClientPreedit(preedit);
            } else {
                panel.setPreedit(preedit);
            }
            panel.setAuxUp(Text("回车/空格确认 · 退格删码(退空回选词) · Esc 取消"));
            ic->updatePreedit();
            ic->updateUserInterface(UserInterfaceComponent::InputPanel);
            return;
        }
        if (state->addStage == 1) {
            // 加词·选字阶段空缓冲: 词槽（已选的字）+ 操作提示
            Text preedit;
            preedit.append("加词:" + state->addWord, TextFormatFlag::Underline);
            preedit.setCursor(static_cast<int>(preedit.textLength()));
            if (ic->capabilityFlags().test(CapabilityFlag::Preedit)) {
                panel.setClientPreedit(preedit);
            } else {
                panel.setPreedit(preedit);
            }
            panel.setAuxUp(
                Text("输入新词 · 回车完成保存 · 退格删字 · Esc 取消"));
            ic->updatePreedit();
            ic->updateUserInterface(UserInterfaceComponent::InputPanel);
            return;
        }
        if (state->reverse) {
            // 裸 ` 已按下、还没输入拼音: 只显示模式提示
            panel.setAuxUp(Text("拼音"));
        }
        if (!state->pending.empty()) {
            // 顶功挂起: 已选字显示在光标处（预编辑），但还没发给应用
            Text preedit;
            preedit.append(state->pending, TextFormatFlag::Underline);
            preedit.setCursor(static_cast<int>(preedit.textLength()));
            if (ic->capabilityFlags().test(CapabilityFlag::Preedit)) {
                panel.setClientPreedit(preedit);
            } else {
                panel.setPreedit(preedit);
            }
        }
        ic->updatePreedit();
        // 必须显式通知 UI 面板已变化，否则上屏后候选窗不消失
        ic->updateUserInterface(UserInterfaceComponent::InputPanel);
        return;
    }

    // 编码字母跟随光标内联显示（客户端支持预编辑时）；
    // 否则退回候选窗顶部一行，保证字母始终可见。
    Text preedit;
    if (state->addStage == 1) {
        preedit.append("加词:" + state->addWord +
                           (state->addWord.empty() ? "" : "·"),
                       TextFormatFlag::Underline);
    }
    if (state->reverse) {
        preedit.append("`", TextFormatFlag::Underline);
        panel.setAuxUp(Text("拼音"));
    }
    if (!state->pending.empty()) {
        // 顶功挂起字在前，正在打的编码跟在后面
        preedit.append(state->pending, TextFormatFlag::Underline);
    }
    preedit.append(lufly_input(eng), TextFormatFlag::Underline);
    // 候选窗与文本光标都定位在预编辑末尾（跟随输入位置，标准 IME 行为）
    preedit.setCursor(static_cast<int>(preedit.textLength()));
    if (ic->capabilityFlags().test(CapabilityFlag::Preedit)) {
        panel.setClientPreedit(preedit);
    } else {
        panel.setPreedit(preedit);
    }

    auto list = std::make_unique<CommonCandidateList>();
    list->setSelectionKey(selectionKeys_);
    list->setPageSize(kPageSize);
    list->setLayoutHint(CandidateLayoutHint::Horizontal);
    const int count = lufly_candidate_count(eng);
    const std::string &typed = state->buffer;
    for (int i = 0; i < count; i++) {
        // 显示「词 剩余编码」: 已敲的前缀在预编辑里不重复，exact 命中无后缀；
        // 编码仅供学习参考，上屏用纯词文本（commitText 分离防漏进文档）
        const char *raw = lufly_candidate_text(eng, i);
        const char *code = lufly_candidate_code(eng, i);
        std::string commitText = raw ? raw : "";
        Text text(commitText);
        if (code && *code) {
            const std::string_view full(code);
            if (full.size() > typed.size() &&
                full.compare(0, typed.size(), typed) == 0) {
                text.append(" ");
                text.append(std::string(full.substr(typed.size())));
            }
        }
        list->insert(i, std::make_unique<LuflyCandidateWord>(
                            std::move(text), std::move(commitText), this));
    }
    // 空候选列表上调 setGlobalCursorIndex 会抛异常（fcitx5 直接 abort），
    // 必须有候选时才置高亮游标。
    if (count > 0) {
        list->setGlobalCursorIndex(0);
    }
    panel.setCandidateList(std::move(list));

    ic->updatePreedit();
    ic->updateUserInterface(UserInterfaceComponent::InputPanel);
}

void LuflyIm::commitCandidate(InputContext *ic, const std::string &text) {
    auto *state = this->state(ic);
    LuflyEngine *eng = state->reverse ? rev_ : scratch_;
    if (state->addStage == 1 && eng && !state->buffer.empty()) {
        // 加词·选字阶段: 鼠标点选进词槽，不提交
        appendAddWord(state, text.c_str());
        updateUI(ic, state);
        return;
    }
    if (eng && !state->buffer.empty()) {
        lufly_learn(eng, state->buffer.c_str(), text.c_str());
    }
    ic->commitString(text);
    state->lastCls = 0;
    state->buffer.clear();
    state->reverse = false;
    updateUI(ic, state);
}

void LuflyCandidateWord::select(InputContext *ic) const {
    im_->commitCandidate(ic, commitText_);
}

void LuflyIm::keyEvent(const InputMethodEntry &, KeyEvent &event) {
    auto *ic = event.inputContext();
    const auto &key = event.key();
    const KeySym sym = key.sym();
    auto *state = this->state(ic);

    // ---- 抬键（release）----
    if (event.isRelease()) {
        // $/|: 按下时已选次选候选，抬键补标点（对齐 rime Release+dollar/bar）。
        // 兼容先松 Shift 的情况（此时 keysym 变回 4 / backslash）。
        if (state->pendingPunct &&
            (sym == FcitxKey_dollar || sym == FcitxKey_bar ||
             sym == FcitxKey_4 || sym == FcitxKey_backslash)) {
            const char *punct = state->pendingPunct;
            state->pendingPunct = nullptr;
            ic->commitString(punct);
            state->autoBuf.clear(); // 标点 = 断链
            state->lastCls = 0;
            event.accept();
            return;
        }
        // Shift 单击（其后无其他键）: 切换中/英文模式；
        // 编码中先原样上屏字母再转英文（对齐常见输入法手感）
        if ((sym == FcitxKey_Shift_L || sym == FcitxKey_Shift_R) &&
            state->shiftArmed) {
            state->shiftArmed = false;
            cancelAddWord(state); // 切换模式即退出加词
            if (!state->buffer.empty()) {
                ic->commitString(state->buffer);
                state->lastCls = 2;
                state->buffer.clear();
                state->reverse = false;
                state->ascii = true; // 编码中必为中文态: 定向转英文
                FCITX_LUFLY_INFO() << "lufly: 切换到英文模式";
                updateUI(ic, state);
                ic->updateUserInterface(UserInterfaceComponent::StatusArea);
            } else {
                if (!state->pending.empty()) {
                    // 挂起字随模式切换落地
                    ic->commitString(state->pending);
                    state->pending.clear();
                    state->pendingCode.clear();
                }
                state->autoBuf.clear(); // 切英文模式 = 断链
                state->reverse = false;
                state->lastCls = 0;
                state->ascii = !state->ascii;
                FCITX_LUFLY_INFO() << "lufly: 切换到"
                                   << (state->ascii ? "英文" : "中文") << "模式";
                updateUI(ic, state);
                // 通知托盘 SNI 刷新子模式图标（天鹅/en）
                ic->updateUserInterface(UserInterfaceComponent::StatusArea);
            }
        }
        return;
    }

    // 任何其他按下键解除 Shift 单击武装、作废待补标点
    state->shiftArmed = false;
    state->pendingPunct = nullptr;

    // ---- 修饰键: Shift 记录单击（空编码时用于切换中英），其余透传 ----
    if (key.isModifier()) {
        if (sym == FcitxKey_Shift_L || sym == FcitxKey_Shift_R) {
            state->shiftArmed = true;
        }
        return;
    }

    // 带组合修饰键的按键一律透传（Ctrl+C / Alt+Tab 等）；Ctrl+0 例外，
    // 切换标点强制半角（对齐 rime ascii_punct）。
    if (key.states().test(KeyState::Ctrl)) {
        if (sym == FcitxKey_0) {
            state->asciiPunct = !state->asciiPunct;
            FCITX_LUFLY_INFO() << "lufly: 标点"
                               << (state->asciiPunct ? "强制半角" : "跟随中文");
            event.accept();
        }
        return;
    }
    if (key.states().test(KeyState::Alt) || key.states().test(KeyState::Super) ||
        key.states().test(KeyState::Hyper) ||
        key.states().test(KeyState::Meta)) {
        return;
    }
    // 英文模式: 一律透传，Shift 单击切回中文
    if (state->ascii) {
        return;
    }
    if (!ensureDict()) {
        return;
    }
    checkDictReload();
    checkUserReload();

    LuflyEngine *eng = state->reverse ? rev_ : scratch_;
    if (!eng) {
        state->reverse = false;
        eng = scratch_;
    }

    // ---- ojc 加词·编码阶段 (stage2): 编辑编码，回车/空格确认 ----
    if (state->addStage == 2) {
        if (key.check(FcitxKey_Escape)) {
            cancelAddWord(state);
            updateUI(ic, state);
            event.accept();
            return;
        }
        if (key.check(FcitxKey_BackSpace)) {
            if (state->addCode.empty()) {
                state->addStage = 1; // 码删空: 退回选词阶段
            } else {
                state->addCode.pop_back();
            }
            updateUI(ic, state);
            event.accept();
            return;
        }
        if (key.check(FcitxKey_Return) || key.check(FcitxKey_space)) {
            if (state->addCode.size() < 2) {
                updateUI(ic, state); // 编码太短: 等待继续输入
                event.accept();
                return;
            }
            if (lufly_user_add_word(scratch_, state->addCode.c_str(),
                                    state->addWord.c_str())) {
                // 保存成功: 词直接上屏（立即可用）
                const std::string word = state->addWord;
                cancelAddWord(state);
                ic->commitString(word);
                state->lastCls = 0;
            } else {
                cancelAddWord(state);
            }
            updateUI(ic, state);
            event.accept();
            return;
        }
        if (sym >= FcitxKey_a && sym <= FcitxKey_z) {
            state->addCode.push_back(static_cast<char>('a' + (sym - FcitxKey_a)));
            updateUI(ic, state);
            event.accept();
            return;
        }
        if (key.isSimple()) {
            event.accept(); // 加词编辑中吞掉其他简单键，防误触
        }
        return;
    }

    // ---- ` 进入拼音反查（对齐 rime reverse_lookup prefix）----
    if (!state->reverse && sym == FcitxKey_grave && state->buffer.empty()) {
        if (ensureRev()) {
            state->reverse = true;
            updateUI(ic, state);
            event.accept();
        }
        return; // 已在反查模式或码表缺失: ` 透传
    }

    // 反查用 rev_ 引擎，普通输入用 scratch_；重放恢复到该 IC 的状态。
    replay(eng, state->buffer);

    // 是否有候选（rime has_menu）/ 是否编码 miss，以刚重放的引擎为准。
    // miss = 缓冲非空但无任何前缀命中（用户可能在输英文）。
    const auto candList = ic->inputPanel().candidateList();
    const bool hasMenu = lufly_candidate_count(eng) > 0;
    const bool miss = !hasMenu && !state->buffer.empty();

    // ---- 翻页: PageUp/PageDown、- 前翻 = 后翻、Tab 后翻 Shift+Tab 前翻 ----
    if (!state->buffer.empty()) {
        if (auto *pageable = candList ? candList->toPageable() : nullptr) {
            const bool shiftHeld = key.states().test(KeyState::Shift);
            const bool pagePrev = key.check(FcitxKey_Page_Up) ||
                                  key.check(FcitxKey_minus) ||
                                  (key.check(FcitxKey_Tab) && shiftHeld);
            const bool pageNext = key.check(FcitxKey_Page_Down) ||
                                  key.check(FcitxKey_equal) ||
                                  (key.check(FcitxKey_Tab) && !shiftHeld);
            if (pagePrev || pageNext) {
                if ((pageNext && pageable->hasNext()) ||
                    (pagePrev && pageable->hasPrev())) {
                    if (pageNext) {
                        pageable->next();
                    } else {
                        pageable->prev();
                    }
                    ic->updateUserInterface(UserInterfaceComponent::InputPanel);
                    event.accept();
                    return;
                }
                // - = Tab 到头/单页: 消费不动作（防半角 - = 漏进文档）；
                // PageUp/PageDown 保持透传（非简单键，应用自处理）
                if (hasMenu && !key.check(FcitxKey_Page_Up) &&
                    !key.check(FcitxKey_Page_Down)) {
                    event.accept();
                    return;
                }
            }
        }
        // Tab: 有菜单翻页；miss 时透传（英文输入中，不清屏）；否则清空（rime send Escape）
        if (key.check(FcitxKey_Tab)) {
            if (miss) {
                return;
            }
            if (hasMenu) {
                if (auto *pageable = candList->toPageable();
                    pageable && pageable->hasNext()) {
                    pageable->next();
                }
                ic->updateUserInterface(UserInterfaceComponent::InputPanel);
            } else {
                state->buffer.clear();
                state->reverse = false;
                cancelAddWord(state);
                updateUI(ic, state);
            }
            event.accept();
            return;
        }
        // Caps_Lock: 清空缓冲（rime send Escape）
        if (key.check(FcitxKey_Caps_Lock)) {
            state->buffer.clear();
            state->reverse = false;
            cancelAddWord(state);
            updateUI(ic, state);
            event.accept();
            return;
        }
    }

    // ---- 选词: 数字 1-5 与 ; ' [ ] = 第2/3/4/5（对齐 rime key_binder）----
    int sel = -1;
    bool digitSel = false;
    if (sym >= FcitxKey_1 && sym < FcitxKey_1 + kPageSize) {
        sel = static_cast<int>(sym - FcitxKey_1);
        digitSel = true;
    } else if (key.check(FcitxKey_semicolon)) {
        sel = 1;
    } else if (key.check(FcitxKey_apostrophe)) {
        sel = 2;
    } else if (key.check(FcitxKey_bracketleft)) {
        sel = 3;
    } else if (key.check(FcitxKey_bracketright)) {
        sel = 4;
    }
    if (sel >= 0 && !state->buffer.empty() && hasMenu) {
        auto *common = dynamic_cast<CommonCandidateList *>(candList.get());
        if (common) {
            const int idx = sel + common->currentPage() * common->pageSize();
            if (const char *text = lufly_candidate_text(eng, idx)) {
                if (state->addStage == 1) {
                    // 加词·选字阶段: 选中的字进词槽，继续选下一个字
                    appendAddWord(state, text);
                    updateUI(ic, state);
                    event.accept();
                    return;
                }
                lufly_learn(eng, state->buffer.c_str(), text);
                noteAutoCommit(state, state->buffer, text);
                ic->commitString(text);
                state->lastCls = 0;
                state->buffer.clear();
                state->reverse = false;
                updateUI(ic, state);
                event.accept();
                return;
            }
            if (digitSel) {
                return; // 数字越界: 消费不动作（原行为）
            }
            // ;'[] 越界: 落到标点顶字
        }
    }

    // ---- $ / |: 选次选候选，抬键补 。 / ，（对齐 rime dollar/bar 绑定）----
    if ((key.check(FcitxKey_dollar) || key.check(FcitxKey_bar)) &&
        !state->buffer.empty() && hasMenu) {
        auto *common = dynamic_cast<CommonCandidateList *>(candList.get());
        if (common) {
            const int idx = 1 + common->currentPage() * common->pageSize();
            if (const char *text = lufly_candidate_text(eng, idx)) {
                if (state->addStage == 1) {
                    appendAddWord(state, text);
                    updateUI(ic, state);
                    event.accept();
                    return;
                }
                lufly_learn(eng, state->buffer.c_str(), text);
                noteAutoCommit(state, state->buffer, text);
                ic->commitString(text);
                state->lastCls = 0;
                state->buffer.clear();
                state->reverse = false;
                state->pendingPunct =
                    key.check(FcitxKey_dollar) ? "。" : "，";
                updateUI(ic, state);
                event.accept();
                return;
            }
        }
    }

    if (key.check(FcitxKey_space)) {
        if (state->buffer.empty()) {
            if (!state->pending.empty()) {
                state->reverse = false;
                if (state->addStage == 1) {
                    // 加词中: 挂起字进词槽（不能漏进文档）
                    state->addWord += state->pending;
                } else {
                    // 空格确认挂起字（空格被消费，不会漏成真空格）
                    if (scratch_) {
                        lufly_learn(scratch_, state->pendingCode.c_str(),
                                    state->pending.c_str());
                    }
                    noteAutoCommit(state, state->pendingCode,
                                   state->pending.c_str());
                    ic->commitString(state->pending);
                }
                state->pending.clear();
                state->pendingCode.clear();
                state->lastCls = 0;
                updateUI(ic, state);
                event.accept();
                return;
            }
            if (state->reverse) {
                state->reverse = false; // 反查空缓冲: 空格退出反查
                updateUI(ic, state);
                event.accept();
            }
            return; // 空缓冲透传
        }
        const std::string code = state->buffer;
        if (const char *text = lufly_key(eng, ' ')) {
            if (state->addStage == 1) {
                // 加词·选字阶段: 空格选中首选进词槽，不提交
                appendAddWord(state, text);
                updateUI(ic, state);
                event.accept();
                return;
            }
            lufly_learn(eng, code.c_str(), text);
            noteAutoCommit(state, code, text);
            ic->commitString(text);
        }
        state->buffer.clear();
        state->reverse = false;
        state->lastCls = 0;
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (key.check(FcitxKey_Return)) {
        if (state->addStage == 1) {
            // 加词·选字阶段: 编码中回车 = 反悔（字母上屏退出）；
            // 空缓冲回车 = 完成选字（挂起字一并入槽）→ 编码阶段
            if (!state->buffer.empty()) {
                cancelAddWord(state);
                ic->commitString(state->buffer);
                state->lastCls = 2;
                state->buffer.clear();
                state->reverse = false;
                updateUI(ic, state);
                event.accept();
                return;
            }
            if (!state->pending.empty()) {
                state->addWord += state->pending;
                state->pending.clear();
                state->pendingCode.clear();
            }
            if (state->addWord.empty()) {
                cancelAddWord(state); // 一个字都没选: 视为取消
            } else {
                finishAddWord(state);
            }
            state->reverse = false;
            updateUI(ic, state);
            event.accept();
            return;
        }
        if (state->buffer.empty()) {
            if (!state->pending.empty()) {
                // 挂起字先送出，Enter 本身不消费（换行照常，顺序正确）
                ic->commitString(state->pending);
                state->pending.clear();
                state->pendingCode.clear();
                state->autoBuf.clear(); // 回车换行 = 断链
                updateUI(ic, state);
            }
            return;
        }
        cancelAddWord(state); // 回车上屏字母 = 反悔退出加词
        ic->commitString(state->buffer); // 编码字母原样上屏
        state->lastCls = 2;
        state->buffer.clear();
        state->reverse = false;
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (key.check(FcitxKey_BackSpace)) {
        if (state->buffer.empty()) {
            if (!state->pending.empty()) {
                // 撤销顶功挂起: 恢复原编码供继续编辑（加形码/换候选/删码）
                state->buffer = state->pendingCode;
                state->pending.clear();
                state->pendingCode.clear();
                replay(eng, state->buffer);
                updateUI(ic, state);
                event.accept();
                return;
            }
            if (state->reverse) {
                state->reverse = false; // 退过 ` 本身: 退出反查
                updateUI(ic, state);
                event.accept();
                return;
            }
            if (state->addStage == 1) {
                if (!state->addWord.empty()) {
                    // 删词槽最后一个字（UTF-8 感知）
                    while (!state->addWord.empty() &&
                           (static_cast<unsigned char>(state->addWord.back()) &
                            0xC0) == 0x80) {
                        state->addWord.pop_back();
                    }
                    if (!state->addWord.empty()) {
                        state->addWord.pop_back();
                    }
                } else {
                    cancelAddWord(state); // 退无可退: 退出加词
                }
                updateUI(ic, state);
                event.accept();
                return;
            }
            return;
        }
        lufly_key(eng, '\b');
        state->buffer = lufly_input(eng);
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (key.check(FcitxKey_Escape)) {
        if (state->buffer.empty()) {
            if (state->addStage == 1) {
                cancelAddWord(state); // 选字中 Esc: 取消加词
                updateUI(ic, state);
                event.accept();
                return;
            }
            if (state->reverse) {
                state->reverse = false;
                updateUI(ic, state);
                event.accept();
            }
            return;
        }
        state->buffer.clear();
        state->reverse = false;
        cancelAddWord(state);
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (sym >= FcitxKey_a && sym <= FcitxKey_z) {
        const uint32_t ch = static_cast<uint32_t>('a' + (sym - FcitxKey_a));
        if (!state->pending.empty()) {
            // 顶功: 下一字词的首键把挂起字顶出（快打全程不用空格）；
            // 加词中顶进词槽而非上屏
            if (state->addStage == 1) {
                state->addWord += state->pending;
            } else {
                noteAutoCommit(state, state->pendingCode,
                               state->pending.c_str());
                ic->commitString(state->pending);
            }
            state->pending.clear();
            state->pendingCode.clear();
            state->lastCls = 0;
        }
        const std::string prev = state->buffer;
        if (const char *text = lufly_key(eng, ch)) {
            // 全码唯一: 不立即发送，挂起等顶出/空格确认（顶功）
            state->pending = text;
            state->pendingCode = prev + static_cast<char>(ch);
        }
        state->buffer = lufly_input(eng);
        // ojc: 命令引导符 o + jc(加词声母) → 进入加词·选词阶段（码表无
        // o 开头编码，与正常打字零冲突；选词/编码全程复用候选窗，无弹窗）
        if (state->buffer == "ojc") {
            state->buffer.clear();
            state->reverse = false;
            state->addStage = 1;
            replay(eng, state->buffer);
        }
        updateUI(ic, state);
        event.accept();
        return;
    }

    // ---- 标点: 中文全角化（对齐 rime punctuator half_shape）----
    // 上下文半角: 前一字符是数字/英文、miss 携带英文、或 Ctrl+0 强制时，
    // 标点不映射、原样透传（编码中仍先顶字）—— 3.14 / hello. / english,
    // 编码中先顶出首选再上屏标点并消费；空缓冲直接上屏标点。
    if (state->addStage == 1) {
        state->addStage = 0; // 标点退出加词（视为反悔），照常处理标点
    }
    const bool composing = !state->buffer.empty();
    const bool halfPunct =
        state->asciiPunct || state->lastCls != 0 || miss;
    const char *punct = halfPunct ? nullptr : chinesePunct(sym, state);
    if (punct) {
        if (!state->pending.empty()) {
            // 挂起字随标点顶出
            noteAutoCommit(state, state->pendingCode,
                           state->pending.c_str());
            ic->commitString(state->pending);
            state->pending.clear();
            state->pendingCode.clear();
        }
        if (miss) {
            ic->commitString(state->buffer); // 英文原样上屏
        } else if (composing) {
            const std::string code = state->buffer;
            if (const char *text = lufly_key(eng, ' ')) {
                lufly_learn(eng, code.c_str(), text);
                noteAutoCommit(state, code, text);
                ic->commitString(text);
            }
        }
        state->buffer.clear();
        state->reverse = false;
        ic->commitString(punct);
        state->autoBuf.clear(); // 标点 = 断链
        state->lastCls = 0;
        updateUI(ic, state);
        event.accept();
        return;
    }
    // 未映射的简单键（含按上下文放行的半角标点）:
    // miss 时透传不清屏（英文继续）；编码中顶出首选后放行原字符。
    if (composing && key.isSimple()) {
        if (state->addStage == 1) {
            event.accept(); // 加词中(含 miss): 不上屏英文/符号，退格或 Esc 处理
            return;
        }
        if (miss) {
            // 英文原样上屏，标点等符号不消费、半角自然插入
            ic->commitString(state->buffer);
            state->buffer.clear();
            state->reverse = false;
            state->lastCls = 2;
            state->autoBuf.clear(); // 英文 = 断链
            updateUI(ic, state);
            return;
        }
        const std::string code = state->buffer;
        if (const char *text = lufly_key(eng, ' ')) {
            lufly_learn(eng, code.c_str(), text);
            noteAutoCommit(state, code, text);
            ic->commitString(text);
        }
        state->buffer.clear();
        state->reverse = false;
        state->lastCls = 0;
        state->autoBuf.clear(); // 透传的原字符插在字间 = 断链
        updateUI(ic, state);
        // 不消费，让原字符自然插入
    }
    // 空缓冲透传的数字: 记录上下文（3.14 / 1,000 后续标点保持半角）
    if (!composing && sym >= FcitxKey_0 && sym <= FcitxKey_9) {
        state->lastCls = 1;
    }
}

void LuflyIm::activate(const InputMethodEntry &, InputContextEvent &) {
    checkDictReload(true);
}

void LuflyIm::reset(const InputMethodEntry &, InputContextEvent &event) {
    auto *ic = event.inputContext();
    auto *state = this->state(ic);
    if (!state->pending.empty()) {
        // 焦点切走: 挂起字落地防丢
        ic->commitString(state->pending);
        state->pending.clear();
        state->pendingCode.clear();
    }
    state->buffer.clear();
    state->reverse = false;
    state->shiftArmed = false;
    state->pendingPunct = nullptr;
    state->lastCls = 0;
    state->dqOpen = false;
    state->sqOpen = false;
    cancelAddWord(state);
    updateUI(ic, state);
}

} // namespace（匿名）
} // namespace fcitx

namespace fcitx {
class LuflyFactory : public AddonFactory {
public:
    AddonInstance *create(AddonManager *manager) override {
        return new LuflyIm(manager->instance());
    }
};
} // namespace fcitx

FCITX_ADDON_FACTORY(fcitx::LuflyFactory)
