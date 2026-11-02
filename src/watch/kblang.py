# SPDX-License-Identifier: Apache-2.0
"""kblang.py: the keyboard layouts of the reply keyboard (src/watch/kbd.c), one per system language, and the C header that carries the chosen ones.

    python3 -I src/watch/kblang.py                 # list the languages and what a header for all of them costs

The watch keeps its system language as a number in a byte (0x200fafe0): an index into the 69 language packs of the firmware (LANG_CODES below, read from the table at 0x2c30d1ec; docs/details.md).
Every layout here is a Latin-script one: a letter layout (QWERTY, QWERTZ or AZERTY), the letters that the base layout lacks (put on their own layer) and the multi-tap groups of the T9 pad,
which are derived: each extra letter goes into the group of the plain letter it is a variant of (ą with a, ł with l, ...). Scripts that need another font and another layout (Cyrillic, Greek, Arabic,
Hebrew, Indic, CJK, Thai, Vietnamese) are not covered. The header holds only the languages you ask for (`build_firmware.py --kb-lang pl,pt`); with more than one, the layout follows the system language,
and a tap on the count at the top of the keyboard switches it."""
import sys, unicodedata

LANG_CODES = ["zh_rCN", "en", "zh_rTW", "zh_rHK", "sq_rAL", "en_rPH", "en_rCA", "en_rUS", "ar", "az_rAZ", "ga", "et_rEE", "eu_rES", "be_rBY", "bg", "is_rIS", "pl", "bs", "fa", "da", "de", "ru", "fr", "fr_rCA",
              "tl", "fi", "ka_rGE", "kk_rKZ", "ko", "nl", "ky_rKG", "gl_rES", "ca", "cs", "hr", "lv", "lt", "ro", "mr_rIN", "ms_rMY", "mk_rMK", "mn_rMN", "bn_rBD", "bn_rIN", "nb", "pt_rBR", "pt_rPT", "ja", "sv",
              "sr", "sk", "sl", "tg", "th", "tr", "tk", "ur_rPK", "uk", "uz_rUZ", "es_rUS", "es_rES", "iw", "el", "hu", "hy_rAM", "it", "hi", "in", "vi"]
ROWS = {"qwerty": ("qwertyuiop", "asdfghjkl", "zxcvbnm"), "qwertz": ("qwertzuiop", "asdfghjkl", "yxcvbnm"), "azerty": ("azertyuiop", "qsdfghjklm", "wxcvbn")}
# name -> (header caption, language codes by prefix, layout, the extra letters). The first entry is the fallback of a build that has several.
LANGS = {
    "en": ("EN", ["en", "tl", "ms", "in"], "qwerty", ""),
    "pl": ("PL", ["pl"], "qwerty", "ąćęłńóśźż"),
    "pt": ("PT", ["pt"], "qwerty", "áàâãçéêíóôõú"),
    "es": ("ES", ["es"], "qwerty", "áéíñóúü¿¡"),
    "fr": ("FR", ["fr"], "azerty", "àâæçéèêëîïôœùûüÿ"),
    "de": ("DE", ["de"], "qwertz", "äöüß"),
    "it": ("IT", ["it"], "qwerty", "àèéìíîòóùú"),
    "nl": ("NL", ["nl"], "qwerty", "éëïöó"),
    "cs": ("CS", ["cs"], "qwertz", "áčďéěíňóřšťúůýž"),
    "sk": ("SK", ["sk"], "qwertz", "áäčďéíĺľňóôŕšťúýž"),
    "hu": ("HU", ["hu"], "qwertz", "áéíóöőúüű"),
    "hr": ("HR", ["hr", "bs"], "qwertz", "čćđšž"),
    "sl": ("SL", ["sl"], "qwertz", "čšž"),
    "ro": ("RO", ["ro"], "qwerty", "ăâîșț"),
    "sv": ("SV", ["sv", "fi"], "qwerty", "åäö"),
    "nb": ("NB", ["nb", "da"], "qwerty", "åæø"),
    "is": ("IS", ["is"], "qwerty", "áðéíóúýþæö"),
    "tr": ("TR", ["tr", "az"], "qwerty", "çğıöşüə"),
    "lt": ("LT", ["lt"], "qwerty", "ąčęėįšųūž"),
    "lv": ("LV", ["lv"], "qwerty", "āčēģīķļņšūž"),
    "et": ("ET", ["et"], "qwerty", "äõöüšž"),
    "ca": ("CA", ["ca", "gl", "eu"], "qwerty", "àçéèíïòóúüñ"),
    "ga": ("GA", ["ga"], "qwerty", "áéíóú"),
    "sq": ("SQ", ["sq"], "qwerty", "çë"),
}
T9_BASE = ["", ".,?!'-", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"]            # index = the key's digit; 0 is the space key
SPECIAL_BASE = {"æ": "a", "ø": "o", "œ": "o", "ð": "d", "đ": "d", "þ": "t", "ı": "i", "ł": "l", "ə": "e", "ß": "s", "ĺ": "l"}
PUNCT_EXTRA = "¿¡"                                                                             # extras that are not letters: they go to the punctuation group (1)
TURKISH = ("tr",)                                                                               # i and ı have their own capitals there


def ids_of(lang):
    """the system-language numbers that select this layout"""
    pref = LANGS[lang][1]; return [i for i, c in enumerate(LANG_CODES) if c.split("_")[0] in pref]


def base_letter(ch):
    if ch in SPECIAL_BASE: return SPECIAL_BASE[ch]
    d = unicodedata.normalize("NFD", ch)[0]
    return d if d.isascii() and d.isalpha() else ""


def groups(extra):
    """the ten multi-tap groups (index 0 = space, 1 = punctuation, 2..9 = letters), each ends with its digit"""
    g = [list(s) for s in T9_BASE]
    for ch in extra:
        if ch in PUNCT_EXTRA: g[1].append(ch); continue
        b = base_letter(ch)
        for i, s in enumerate(T9_BASE):
            if i >= 2 and b in s: g[i].append(ch); break
        else: raise SystemExit("no multi-tap group for %r" % ch)
    out = []
    for i, s in enumerate(g):
        if i == 0: out.append(" 0")
        else: out.append("".join(s) + str(i))
    return out


def rows_of(lang):
    return ROWS[LANGS[lang][2]]


def upper(ch, lang_names):
    """the capital of a lower-case extra letter, or None when there is none or it is not a single letter (ß)"""
    if "tr" in lang_names and ch == "ı": return "I"
    u = ch.upper()
    return u if len(u) == 1 and u != ch else None


def alphabet(names):
    """every character the chosen layouts type, lower and upper case (for the font)"""
    s = set()
    for n in names:
        for r in rows_of(n): s |= set(r) | set(r.upper())
        for ch in LANGS[n][3]:
            s.add(ch); u = upper(ch, names)
            if u: s.add(u)
        if n in TURKISH: s |= {"İ", "ı"}
    return "".join(sorted(s, key=ord))


def cstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def header(names):
    """the C header with the layouts of `names` (kbd.c includes it as kblang.h)"""
    for n in names:
        if n not in LANGS: raise SystemExit("unknown keyboard language %r (known: %s)" % (n, ", ".join(LANGS)))
    out = ["/* generated by src/watch/kblang.py: do not edit */", "#ifndef F3_KBLANG_H", "#define F3_KBLANG_H",
           "typedef struct { const char *name; const u8 *ids; const char *rows[3]; const char *extra; const char *group[10]; u8 turkish; } KbLang;"]
    pairs = []
    for n in names:
        for ch in LANGS[n][3]:
            u = upper(ch, names)
            if u and (ch, u) not in pairs: pairs.append((ch, u))
    out.append("static const struct { char lo[3], up[3]; } KB_PAIRS[] = { %s };" % (", ".join("{%s, %s}" % (cstr(a), cstr(b)) for a, b in pairs) or "{\"\", \"\"}"))
    out.append("#define KB_NPAIRS %d" % len(pairs))
    items = []
    for n in names:
        cap, _, layout, extra = LANGS[n]; ids = ids_of(n)
        out.append("static const u8 KB_IDS_%s[] = { %s, 0xff };" % (n, ", ".join(map(str, ids))))
        items.append("{ %s, KB_IDS_%s, { %s }, %s, { %s }, %d }" % (cstr(cap), n, ", ".join(cstr(r) for r in rows_of(n)), cstr(extra), ", ".join(cstr(g) for g in groups(extra)), 1 if n in TURKISH else 0))
    out.append("static const KbLang KB_LANGS[] = {\n    %s\n};" % ",\n    ".join(items))
    out.append("#define KB_NLANGS %d" % len(names)); out.append("#endif")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    for n, (cap, pref, layout, extra) in LANGS.items():
        print("%-3s %-6s %-6s ids %-14s extra %s" % (n, cap, layout, ids_of(n), extra))
    print("all together: %d characters for the font" % len(alphabet(list(LANGS))))
