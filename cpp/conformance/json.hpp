// The adapter's own JSON codec (design.md 2.6, D20; frozen-m1.md section 5.2): standard JSON plus the lone-surrogate
// rule of spec/conformance.md 3 (a "\ud800" escape decodes to its WTF-8 bytes and encodes back as "\ud800"), which
// nlohmann/json and Boost.JSON refuse. Strings hold UTF-8 (WTF-8) bytes; output is ASCII only. Test code, never part
// of the library. Its WTF-8 rule is the protocol's, fixed; the library's decode policy (detail/text_in.hpp) is
// provisional and may change apart from it, so the codec decodes for itself.
#ifndef VILLANELLE_CONFORMANCE_JSON_HPP
#define VILLANELLE_CONFORMANCE_JSON_HPP

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

inline void write_string(std::string& out, std::string_view s) {
    out += '"';
    char escape[8];
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
            std::snprintf(escape, sizeof escape, "\\u%04x", static_cast<unsigned>(cp));
            out += escape;
        } else {
            const char32_t v = cp - 0x10000;
            std::snprintf(escape, sizeof escape, "\\u%04x", static_cast<unsigned>(0xD800 + (v >> 10U)));
            out += escape;
            std::snprintf(escape, sizeof escape, "\\u%04x", static_cast<unsigned>(0xDC00 + (v & 0x3FFU)));
            out += escape;
        }
    }
    out += '"';
}

inline void write(std::string& out, const value& v) {
    struct visitor {
        std::string& out;
        void operator()(std::nullptr_t) const { out += "null"; }
        void operator()(bool b) const { out += b ? "true" : "false"; }
        void operator()(std::int64_t n) const { out += std::to_string(n); }
        void operator()(double d) const {
            char spelled[32];
            std::snprintf(spelled, sizeof spelled, "%.17g", d);
            out += spelled;
        }
        void operator()(const std::string& s) const { write_string(out, s); }
        void operator()(const std::shared_ptr<array>& items) const {
            out += '[';
            for (std::size_t i = 0; i < items->size(); ++i) {
                if (i != 0) {
                    out += ", ";
                }
                write(out, (*items)[i]);
            }
            out += ']';
        }
        void operator()(const std::shared_ptr<object>& members) const {
            out += '{';
            for (std::size_t i = 0; i < members->size(); ++i) {
                if (i != 0) {
                    out += ", ";
                }
                write_string(out, (*members)[i].first);
                out += ": ";
                write(out, (*members)[i].second);
            }
            out += '}';
        }
    };
    std::visit(visitor{out}, v.data);
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

#endif  // VILLANELLE_CONFORMANCE_JSON_HPP
