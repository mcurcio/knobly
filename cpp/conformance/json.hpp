// The adapter's own JSON codec (design.md 2.6, D20; frozen-m1.md section 5.2): standard JSON plus the lone-surrogate
// rule of spec/conformance.md 3 (a "\ud800" escape decodes to its WTF-8 bytes and encodes back as "\ud800"), which
// nlohmann/json and Boost.JSON refuse. Strings hold UTF-8 (WTF-8) bytes; output is ASCII only. Test code, never part
// of the library. Its WTF-8 rule is the protocol's, fixed; the library's decode policy (detail/text_in.hpp) is
// provisional and may change apart from it, so the codec decodes for itself.
#ifndef KNOBLY_CONFORMANCE_JSON_HPP
#define KNOBLY_CONFORMANCE_JSON_HPP

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace adapter::json {

struct value;
using array = std::vector<value>;
using object = std::vector<std::pair<std::string, value>>;  // insertion order kept

struct value {
    std::variant<std::nullptr_t, bool, std::int64_t, double, std::string, std::shared_ptr<array>,
                 std::shared_ptr<object>>
        data;

    value() : data(nullptr) {}
    value(std::nullptr_t) : data(nullptr) {}
    value(bool b) : data(b) {}
    value(int n) : data(std::int64_t{n}) {}
    value(std::int64_t n) : data(n) {}
    value(double d) : data(d) {}
    value(std::string s) : data(std::move(s)) {}
    value(const char* s) : data(std::string(s)) {}
    value(array a) : data(std::make_shared<array>(std::move(a))) {}
    value(object o) : data(std::make_shared<object>(std::move(o))) {}
    value(const value&) = default;
    value(value&&) noexcept = default;
    value& operator=(const value&) = default;
    value& operator=(value&&) noexcept = default;

    /// Iterative, so a deep tree (a dump 256 levels down) costs heap, not stack: the default destructor recursed
    /// once per level (kno-bzv.10). Each child this value alone owns moves to a list and is emptied there in turn.
    ~value() {
        std::vector<value> pending;
        adopt(pending);
        while (!pending.empty()) {
            value last = std::move(pending.back());
            pending.pop_back();
            last.adopt(pending);
        }
    }

    /// The member `key` of an object, or nullptr when this is no object or has no such member.
    const value* find(std::string_view key) const {
        if (const auto* members = std::get_if<std::shared_ptr<object>>(&data)) {
            for (const auto& [name, member] : **members) {
                if (name == key) {
                    return &member;
                }
            }
        }
        return nullptr;
    }

private:
    /// Moves the children of the array or object this value alone owns to `pending`, leaving it empty.
    void adopt(std::vector<value>& pending) {
        if (auto* items = std::get_if<std::shared_ptr<array>>(&data); items != nullptr && items->use_count() == 1) {
            for (value& item : **items) {
                pending.push_back(std::move(item));
            }
            (*items)->clear();
        } else if (auto* members = std::get_if<std::shared_ptr<object>>(&data);
                   members != nullptr && members->use_count() == 1) {
            for (auto& member : **members) {
                pending.push_back(std::move(member.second));
            }
            (*members)->clear();
        }
    }
};

namespace detail {

class reader {
public:
    explicit reader(std::string_view text) : text_(text) {}

    value document() {
        value v = any();
        space();
        if (at_ != text_.size()) {
            fail("text after the value");
        }
        return v;
    }

private:
    [[noreturn]] void fail(const char* what) const {
        throw std::runtime_error(std::string("bad JSON at byte ") + std::to_string(at_) + ": " + what);
    }
    void space() {
        while (at_ < text_.size() &&
               (text_[at_] == ' ' || text_[at_] == '\t' || text_[at_] == '\n' || text_[at_] == '\r')) {
            ++at_;
        }
    }
    bool eat(char c) {
        space();
        if (at_ < text_.size() && text_[at_] == c) {
            ++at_;
            return true;
        }
        return false;
    }
    void expect(char c) {
        if (!eat(c)) {
            fail("unexpected character");
        }
    }
    void word(std::string_view w) {
        if (text_.substr(at_, w.size()) != w) {
            fail("unknown literal");
        }
        at_ += w.size();
    }

    value any() {
        space();
        if (at_ >= text_.size()) {
            fail("end of text");
        }
        switch (text_[at_]) {
            case '{': {
                ++at_;
                object members;
                if (!eat('}')) {
                    do {
                        space();
                        std::string key = string();
                        expect(':');
                        members.emplace_back(std::move(key), any());
                    } while (eat(','));
                    expect('}');
                }
                return value(std::move(members));
            }
            case '[': {
                ++at_;
                array items;
                if (!eat(']')) {
                    do {
                        items.push_back(any());
                    } while (eat(','));
                    expect(']');
                }
                return value(std::move(items));
            }
            case '"':
                return value(string());
            case 't':
                word("true");
                return value(true);
            case 'f':
                word("false");
                return value(false);
            case 'n':
                word("null");
                return value(nullptr);
            default:
                return number();
        }
    }

    value number() {
        const std::size_t start = at_;
        bool integral = true;
        if (at_ < text_.size() && text_[at_] == '-') {
            ++at_;
        }
        const std::size_t digits = at_;
        while (at_ < text_.size() && text_[at_] >= '0' && text_[at_] <= '9') {
            ++at_;
        }
        if (at_ == digits) {
            fail("expected a value");
        }
        if (at_ < text_.size() && text_[at_] == '.') {
            integral = false;
            ++at_;
            while (at_ < text_.size() && text_[at_] >= '0' && text_[at_] <= '9') {
                ++at_;
            }
        }
        if (at_ < text_.size() && (text_[at_] == 'e' || text_[at_] == 'E')) {
            integral = false;
            ++at_;
            if (at_ < text_.size() && (text_[at_] == '+' || text_[at_] == '-')) {
                ++at_;
            }
            while (at_ < text_.size() && text_[at_] >= '0' && text_[at_] <= '9') {
                ++at_;
            }
        }
        const std::string spelled(text_.substr(start, at_ - start));
        if (integral) {
            return value(static_cast<std::int64_t>(std::strtoll(spelled.c_str(), nullptr, 10)));
        }
        return value(std::strtod(spelled.c_str(), nullptr));
    }

    unsigned hex4() {
        if (text_.size() - at_ < 4) {
            fail("short \\u escape");
        }
        unsigned v = 0;
        for (int k = 0; k < 4; ++k) {
            const char c = text_[at_++];
            v <<= 4U;
            if (c >= '0' && c <= '9') {
                v |= static_cast<unsigned>(c - '0');
            } else if (c >= 'a' && c <= 'f') {
                v |= static_cast<unsigned>(c - 'a' + 10);
            } else if (c >= 'A' && c <= 'F') {
                v |= static_cast<unsigned>(c - 'A' + 10);
            } else {
                fail("bad \\u escape");
            }
        }
        return v;
    }

    /// A code point as UTF-8; a surrogate gets its three-byte (WTF-8) form.
    static void append(std::string& out, char32_t cp) {
        if (cp < 0x80) {
            out += static_cast<char>(cp);
        } else if (cp < 0x800) {
            out += static_cast<char>(0xC0 | (cp >> 6));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out += static_cast<char>(0xE0 | (cp >> 12));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else {
            out += static_cast<char>(0xF0 | (cp >> 18));
            out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }

    std::string string() {
        if (at_ >= text_.size() || text_[at_] != '"') {
            fail("expected a string");
        }
        ++at_;
        std::string out;
        for (;;) {
            if (at_ >= text_.size()) {
                fail("unterminated string");
            }
            const char c = text_[at_++];
            if (c == '"') {
                return out;
            }
            if (c != '\\') {
                out += c;
                continue;
            }
            if (at_ >= text_.size()) {
                fail("unterminated escape");
            }
            switch (text_[at_++]) {
                case '"':
                    out += '"';
                    break;
                case '\\':
                    out += '\\';
                    break;
                case '/':
                    out += '/';
                    break;
                case 'b':
                    out += '\b';
                    break;
                case 'f':
                    out += '\f';
                    break;
                case 'n':
                    out += '\n';
                    break;
                case 'r':
                    out += '\r';
                    break;
                case 't':
                    out += '\t';
                    break;
                case 'u': {
                    char32_t cp = hex4();
                    // A high surrogate followed by a low one is one code point; any other surrogate stays alone.
                    if (cp >= 0xD800 && cp <= 0xDBFF && text_.substr(at_, 2) == "\\u") {
                        const std::size_t back = at_;
                        at_ += 2;
                        const char32_t low = hex4();
                        if (low >= 0xDC00 && low <= 0xDFFF) {
                            cp = 0x10000 + ((cp - 0xD800) << 10U) + (low - 0xDC00);
                        } else {
                            at_ = back;
                        }
                    }
                    append(out, cp);
                    break;
                }
                default:
                    fail("bad escape");
            }
        }
    }

    std::string_view text_;
    std::size_t at_ = 0;
};

/// The code point at `at` of UTF-8 or WTF-8 bytes and its length; U+FFFD and 1 for a byte that does not decode.
inline std::pair<char32_t, std::size_t> decode(std::string_view s, std::size_t at) {
    const auto byte = [&](std::size_t k) { return static_cast<unsigned char>(s[at + k]); };
    const unsigned char lead = byte(0);
    const std::size_t length = lead < 0x80 ? 1 : lead >= 0xF0 ? 4 : lead >= 0xE0 ? 3 : lead >= 0xC2 ? 2 : 0;
    if (length == 0 || lead > 0xF4 || s.size() - at < length) {
        return {0xFFFD, 1};
    }
    if (length == 1) {
        return {lead, 1};
    }
    char32_t cp = lead & (0x7FU >> length);
    for (std::size_t k = 1; k < length; ++k) {
        if ((byte(k) & 0xC0U) != 0x80U) {
            return {0xFFFD, 1};
        }
        cp = (cp << 6U) | (byte(k) & 0x3FU);
    }
    if ((length == 3 && cp < 0x800) || (length == 4 && (cp < 0x10000 || cp > 0x10FFFF))) {
        return {0xFFFD, 1};
    }
    return {cp, length};
}

/// "\\u" and four lowercase hex digits of a UTF-16 unit.
inline void write_unit(std::string& out, char32_t unit) {
    constexpr std::string_view digits = "0123456789abcdef";
    out += "\\u";
    for (int shift = 12; shift >= 0; shift -= 4) {
        out += digits[(unit >> static_cast<unsigned>(shift)) & 0xFU];
    }
}

inline void write_string(std::string& out, std::string_view s) {
    out += '"';
    for (std::size_t at = 0; at < s.size();) {
        const auto [cp, length] = decode(s, at);
        at += length;
        if (cp == '"' || cp == '\\') {
            out += '\\';
            out += static_cast<char>(cp);
        } else if (cp == '\n') {
            out += "\\n";
        } else if (cp == '\r') {
            out += "\\r";
        } else if (cp == '\t') {
            out += "\\t";
        } else if (cp >= 0x20 && cp < 0x7F) {
            out += static_cast<char>(cp);
        } else if (cp < 0x10000) {
            write_unit(out, cp);
        } else {
            const char32_t v = cp - 0x10000;
            write_unit(out, 0xD800 + (v >> 10U));
            write_unit(out, 0xDC00 + (v & 0x3FFU));
        }
    }
    out += '"';
}

/// A scalar's text, or false (writing nothing) for an array or object, which write walks itself.
inline bool write_scalar(std::string& out, const value& v) {
    if (std::holds_alternative<std::nullptr_t>(v.data)) {
        out += "null";
    } else if (const auto* b = std::get_if<bool>(&v.data)) {
        out += *b ? "true" : "false";
    } else if (const auto* n = std::get_if<std::int64_t>(&v.data)) {
        out += std::to_string(*n);
    } else if (const auto* d = std::get_if<double>(&v.data)) {
        char spelled[32];
        std::snprintf(spelled, sizeof spelled, "%.17g", *d);
        out += spelled;
    } else if (const auto* s = std::get_if<std::string>(&v.data)) {
        write_string(out, *s);
    } else {
        return false;
    }
    return true;
}

/// Iterative, with a list of the open arrays and objects in place of the call stack, so a deep tree costs heap, not
/// stack (kno-bzv.10).
inline void write(std::string& out, const value& root) {
    struct open {
        const array* items;     // the open array, or null
        const object* members;  // else the open object
        std::size_t next;       // the index of its next member
    };
    std::vector<open> stack;
    const auto enter = [&](const value& v) {
        if (write_scalar(out, v)) {
            return;
        }
        if (const auto* items = std::get_if<std::shared_ptr<array>>(&v.data)) {
            out += '[';
            stack.push_back({items->get(), nullptr, 0});
        } else {
            out += '{';
            stack.push_back({nullptr, std::get<std::shared_ptr<object>>(v.data).get(), 0});
        }
    };
    enter(root);
    while (!stack.empty()) {
        open& top = stack.back();
        const bool is_array = top.items != nullptr;
        const std::size_t at = top.next;
        if (at == (is_array ? top.items->size() : top.members->size())) {
            out += is_array ? ']' : '}';
            stack.pop_back();
            continue;
        }
        ++top.next;
        if (at != 0) {
            out += ", ";
        }
        if (is_array) {
            enter((*top.items)[at]);  // may grow the stack, so top is not used after it
        } else {
            write_string(out, (*top.members)[at].first);
            out += ": ";
            enter((*top.members)[at].second);
        }
    }
}

}  // namespace detail

/// One request line; throws std::runtime_error on bad JSON.
inline value parse(std::string_view line) { return detail::reader(line).document(); }

/// One response line, ASCII only.
inline std::string dump(const value& v) {
    std::string out;
    detail::write(out, v);
    return out;
}

}  // namespace adapter::json

#endif  // KNOBLY_CONFORMANCE_JSON_HPP
