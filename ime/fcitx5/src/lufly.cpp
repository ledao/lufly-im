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
//   a-z       进编码缓冲（死码/全码自动顶字上屏由引擎决定）
//   空格      上屏首选
//   1-6       选当前页候选（每页 6 个）
//   PageUp/Down  翻页
//   回车      编码字母原样上屏
//   退格      删一码；Esc 清空缓冲
//   其余按键  不消费、不破坏缓冲（标点透传；空键组合键一律透传）

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

#include "lufly_capi.h"

FCITX_DEFINE_LOG_CATEGORY(lufly, "lufly");

#define FCITX_LUFLY_DEBUG() FCITX_LOGC(lufly, Debug)
#define FCITX_LUFLY_ERROR() FCITX_LOGC(lufly, Error)
#define FCITX_LUFLY_INFO() FCITX_LOGC(lufly, Info)

namespace fcitx {

namespace {

// 候选页大小: 数字 1-6 对应本页 6 个候选。
constexpr int kPageSize = 6;

// true: 候选窗钉在首个字母处不随输入右移（预编辑光标固定在起点）；
// false: 候选窗跟随最新字母（预编辑光标在末尾）。
constexpr bool kPinCandidateWindow = true;

// 每个 InputContext 的编码缓冲。
class LuflyState : public InputContextProperty {
public:
    std::string buffer;
};

class LuflyStateFactory : public InputContextPropertyFactory {
public:
    InputContextProperty *create(InputContext &) override {
        return new LuflyState;
    }
};

// 候选词: 点击/回车选中后提交并清缓冲。
class LuflyCandidateWord : public CandidateWord {
public:
    LuflyCandidateWord(Text text, class LuflyIm *im)
        : CandidateWord(std::move(text)), im_(im) {}

    void select(InputContext *ic) const override;

private:
    LuflyIm *im_;
};

class LuflyIm final : public InputMethodEngine {
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

private:
    friend class LuflyCandidateWord;

    LuflyState *state(InputContext *ic) {
        return static_cast<LuflyState *>(ic->property(&factory_));
    }

    bool ensureDict();
    // 码表热更新: 文件变化时重载（升级码表免重启 fcitx5），有 1s 节流。
    void checkDictReload(bool force = false);
    // 把 IC 缓冲重放到工作引擎（引擎即恢复到该 IC 的当前状态）。
    void replay(const std::string &buffer);
    // 按当前引擎状态刷新预编辑 + 候选窗（空缓冲时清空面板）。
    void updateUI(InputContext *ic, LuflyState *state);

    Instance *instance_;
    LuflyStateFactory factory_;
    LuflyEngine *scratch_ = nullptr;
    bool triedLoad_ = false;
    KeyList selectionKeys_;
    std::string dictPath_;
    time_t dictMtime_ = 0;
    off_t dictSize_ = 0;
    std::chrono::steady_clock::time_point lastCheck_;
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
        lufly_free(scratch_);
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
    FCITX_LUFLY_INFO() << "lufly: 码表加载成功 " << path;
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
    lufly_free(scratch_);
    scratch_ = nullptr;
    triedLoad_ = false;
    if (ensureDict()) {
        FCITX_LUFLY_INFO() << "lufly: 码表已热更新 " << dictPath_;
    }
}

void LuflyIm::replay(const std::string &buffer) {
    lufly_reset(scratch_);
    for (unsigned char c : buffer) {
        lufly_key(scratch_, c);
    }
}

void LuflyIm::updateUI(InputContext *ic, LuflyState *state) {
    auto &panel = ic->inputPanel();
    if (state->buffer.empty()) {
        panel.reset();
        ic->updatePreedit();
        ic->updateUserInterface(UserInterfaceComponent::InputPanel);
        return;
    }

    // 编码字母跟随光标内联显示（客户端支持预编辑时）；
    // 否则退回候选窗顶部一行，保证字母始终可见。
    Text preedit;
    preedit.append(lufly_input(scratch_), TextFormatFlag::Underline);
    // 候选窗按预编辑光标位置定位: 光标在起点=钉在首字母处，在末尾=跟随右移
    preedit.setCursor(kPinCandidateWindow ? 0
                                          : static_cast<int>(preedit.textLength()));
    if (ic->capabilityFlags().test(CapabilityFlag::Preedit)) {
        panel.setClientPreedit(preedit);
    } else {
        panel.setPreedit(preedit);
    }

    auto list = std::make_unique<CommonCandidateList>();
    list->setSelectionKey(selectionKeys_);
    list->setPageSize(kPageSize);
    list->setLayoutHint(CandidateLayoutHint::Horizontal);
    const int count = lufly_candidate_count(scratch_);
    for (int i = 0; i < count; i++) {
        Text text(lufly_candidate_text(scratch_, i));
        list->insert(i, std::make_unique<LuflyCandidateWord>(std::move(text),
                                                             this));
    }
    panel.setCandidateList(std::move(list));

    ic->updatePreedit();
    ic->updateUserInterface(UserInterfaceComponent::InputPanel);
}

void LuflyIm::commitCandidate(InputContext *ic, const std::string &text) {
    auto *state = this->state(ic);
    ic->commitString(text);
    state->buffer.clear();
    updateUI(ic, state);
}

void LuflyCandidateWord::select(InputContext *ic) const {
    im_->commitCandidate(ic, text().toString());
}

void LuflyIm::keyEvent(const InputMethodEntry &, KeyEvent &event) {
    auto *ic = event.inputContext();
    const auto &key = event.key();
    if (event.isRelease() || key.isModifier()) {
        return;
    }
    // 带组合修饰键的按键一律透传（Ctrl+C / Alt+Tab 等）。
    if (key.states().test(KeyState::Ctrl) || key.states().test(KeyState::Alt) ||
        key.states().test(KeyState::Super) ||
        key.states().test(KeyState::Hyper) ||
        key.states().test(KeyState::Meta)) {
        return;
    }
    if (!ensureDict()) {
        return;
    }
    checkDictReload();
    auto *state = this->state(ic);
    replay(state->buffer);

    const KeySym sym = key.sym();

    // 翻页（有候选时）。
    if (!state->buffer.empty()) {
        auto candList = ic->inputPanel().candidateList();
        if (auto *pageable = candList ? candList->toPageable() : nullptr) {
            if (key.check(FcitxKey_Page_Down) && pageable->hasNext()) {
                pageable->next();
                ic->updateUserInterface(UserInterfaceComponent::InputPanel);
                event.accept();
                return;
            }
            if (key.check(FcitxKey_Page_Up) && pageable->hasPrev()) {
                pageable->prev();
                ic->updateUserInterface(UserInterfaceComponent::InputPanel);
                event.accept();
                return;
            }
        }
    }

    // 数字选词（当前页内，越界则透传）。
    if (sym >= FcitxKey_1 && sym < FcitxKey_1 + kPageSize &&
        !state->buffer.empty()) {
        auto candList = ic->inputPanel().candidateList();
        auto *common = dynamic_cast<CommonCandidateList *>(candList.get());
        if (common) {
            const int idx =
                static_cast<int>(sym - FcitxKey_1) +
                common->currentPage() * common->pageSize();
            if (const char *text = lufly_candidate_text(scratch_, idx)) {
                ic->commitString(text);
                state->buffer.clear();
                updateUI(ic, state);
                event.accept();
            }
            return;
        }
    }

    if (key.check(FcitxKey_space)) {
        if (state->buffer.empty()) {
            return; // 空缓冲透传
        }
        if (const char *text = lufly_key(scratch_, ' ')) {
            ic->commitString(text);
        }
        state->buffer.clear();
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (key.check(FcitxKey_Return)) {
        if (state->buffer.empty()) {
            return;
        }
        ic->commitString(state->buffer); // 编码字母原样上屏
        state->buffer.clear();
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (key.check(FcitxKey_BackSpace)) {
        if (state->buffer.empty()) {
            return;
        }
        lufly_key(scratch_, '\b');
        state->buffer = lufly_input(scratch_);
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (key.check(FcitxKey_Escape)) {
        if (state->buffer.empty()) {
            return;
        }
        state->buffer.clear();
        updateUI(ic, state);
        event.accept();
        return;
    }

    if (sym >= FcitxKey_a && sym <= FcitxKey_z) {
        const uint32_t ch = static_cast<uint32_t>('a' + (sym - FcitxKey_a));
        if (const char *text = lufly_key(scratch_, ch)) {
            ic->commitString(text);
        }
        state->buffer = lufly_input(scratch_);
        updateUI(ic, state);
        event.accept();
        return;
    }

    // 其余可打印键（标点等）: 顶出首选后放行 —— "标点顶屏"。
    // 不带修饰键的 ASCII 键才算（方向键/F 键/组合键不顶字）。
    if (key.isSimple() && !state->buffer.empty()) {
        if (const char *text = lufly_key(scratch_, ' ')) {
            ic->commitString(text);
        }
        state->buffer.clear();
        updateUI(ic, state);
        // 不消费，让标点自然插入
    }
}

void LuflyIm::activate(const InputMethodEntry &, InputContextEvent &) {
    checkDictReload(true);
}

void LuflyIm::reset(const InputMethodEntry &, InputContextEvent &event) {
    auto *ic = event.inputContext();
    auto *state = this->state(ic);
    state->buffer.clear();
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
