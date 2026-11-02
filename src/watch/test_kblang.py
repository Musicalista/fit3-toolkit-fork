# SPDX-License-Identifier: Apache-2.0
"""test_kblang.py: the keyboard layouts (kblang.py) are consistent: python3 -I src/watch/test_kblang.py   (the glyph check needs Roboto, found with fc-match; skipped without it)"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "assets"))
import kblang as K
ok = 0
def good(what):
    global ok; ok += 1; print("  ok  ", what)

assert len(K.LANG_CODES) == 69 and len(set(K.LANG_CODES)) == 69
good("69 language codes, as the firmware's table")
seen = {}
for n in K.LANGS:
    for i in K.ids_of(n):
        assert i not in seen, "system language %d (%s) belongs to %s and %s" % (i, K.LANG_CODES[i], seen[i], n); seen[i] = n
    assert K.ids_of(n), "%s matches no system language" % n
good("every layout matches at least one system language and none is claimed twice (%d of 69 ids covered)" % len(seen))
for n, (cap, pref, layout, extra) in K.LANGS.items():
    assert len(cap) == 2 and cap.isupper() and len(set(extra)) == len(extra)
    assert len(K.ROWS[layout][0]) <= 10 and len(K.ROWS[layout][1]) <= 10 and len(K.ROWS[layout][2]) <= 7
    assert len(extra) <= 20, "%s: the extra letters take at most two rows" % n
    g = K.groups(extra)
    assert len(g) == 10 and all(len(x.encode()) <= 23 for x in g), (n, g)
    assert all(c in "".join(g) for c in extra), "%s: an extra letter is in no multi-tap group" % n
    for i in range(2, 10): assert g[i].endswith(str(i)) and g[i].startswith(K.T9_BASE[i])
good("rows fit the keys, at most 20 extra letters, every extra letter has a multi-tap group, groups fit a key's buffer")
for n in K.LANGS:
    h = K.header([n]); assert "KB_LANGS" in h and "KB_NPAIRS" in h
    for ch in K.LANGS[n][3]:
        u = K.upper(ch, [n])
        if u: assert len(ch.encode()) == 2 and len(u.encode()) in (1, 2), (n, ch, u)
good("capitals of the extra letters are one or two bytes, as the keyboard's table expects")
assert "İ" in K.alphabet(["tr"]) and "ı" in K.alphabet(["tr"]) and "İ" not in K.alphabet(["pl"])
good("the Turkish dotted capital is in the Turkish alphabet only")
ttf = subprocess.run(["fc-match", "-f", "%{file}", "Roboto:medium"], capture_output=True, text=True).stdout
if os.path.exists(ttf):
    import mkfont; have = mkfont.ttf_codepoints(ttf); miss = [c for c in K.alphabet(list(K.LANGS)) if ord(c) not in have]
    assert not miss, "Roboto lacks: %s" % miss; good("Roboto Medium has a glyph for every character of every layout")
else: print("  skip: no Roboto found")
print("%d checks passed" % ok)
