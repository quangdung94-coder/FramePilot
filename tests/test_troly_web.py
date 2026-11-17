"""Kiểm tra tĩnh giao diện HTML của Trợ lý File Quay (app/troly_web): không cần trình duyệt.
Lỗi 15/11/2026: ô thumbnail được chọn dùng class "sel" trùng với class .sel (height:40px) của ô chọn thả xuống,
nên khi giữ Shift chọn nhiều ô, các ô được chọn co còn 40 px, mất ảnh và tên file."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "troly_web")


def read(name):
    with open(os.path.join(WEB, name), "r", encoding="utf-8") as f:
        return f.read()


class WebStatic(unittest.TestCase):
    def setUp(self):
        self.js, self.css, self.html = read("app.js"), read("style.css"), read("index.html")

    def card_state_classes(self):
        """Các class trạng thái JS gắn thêm vào ô thumbnail (sau chữ 'card')."""
        toks = set()
        for line in self.js.splitlines():
            if 'class="card' in line or 'className = "card"' in line or 'const cls = "card"' in line:
                toks.update(re.findall(r'"\s+(\w+)"', line))
        return toks

    def test_card_state_classes_do_not_collide_with_other_css_classes(self):
        toks = self.card_state_classes()
        self.assertTrue({"cur", "picked"} <= toks, toks)
        for t in toks:
            # một luật CSS đứng riêng '.tên {' (không phải '.card.tên') sẽ áp lên ô thumbnail: lỗi ô co còn 40 px
            bare = re.findall(r"(?m)^\.%s[\s,{]" % re.escape(t), self.css)
            self.assertEqual(bare, [], "class '%s' của ô thumbnail trùng một luật CSS riêng" % t)
        self.assertIn(".card.picked", self.css)
        self.assertNotIn(".card.sel", self.css)

    def test_cards_keep_height_and_block_text_selection(self):
        self.assertRegex(self.css, r"\.thumb \{[^}]*aspect-ratio: 16 / 9")
        self.assertRegex(self.css, r"\.grid-scroll \{[^}]*user-select: none")
        self.assertIn('$("grid").addEventListener("mousedown"', self.js)
        self.assertIn("preventDefault", self.js[self.js.index('$("grid").addEventListener("mousedown"'):][:300])
        self.assertIn('img.draggable = false', self.js)
        self.assertIn('draggable="false"', self.js)

    def test_selection_change_only_toggles_class(self):
        body = self.js[self.js.index("function patchGrid()"):][:700]
        self.assertIn("el.className !== cls", body)            # chỉ đổi class khi khác
        self.assertNotIn("innerHTML", body)                    # không dựng lại ô

    def test_shift_digit_pending_has_no_timeout_and_no_two_second_text(self):
        pend = self.js[self.js.index("let pending = null;"):self.js.index('document.addEventListener("keydown"')]
        self.assertNotIn("setTimeout", pend)
        self.assertNotIn("timer", pend)
        self.assertNotIn("2000", pend)
        for name, text in (("app.js", self.js), ("index.html", self.html), ("style.css", self.css)):
            self.assertNotIn("2 giây", text, name)
            self.assertNotIn("pend-bar", text, name)

    def test_pending_ends_only_on_expected_events(self):
        # kết thúc chờ: số bin con, 0, Esc, bấm chuột, mũi tên, đổi bước
        self.assertIn("function finishPending", self.js)
        self.assertIn('if (!e.target.closest("#pend")) cancelPending();', self.js)
        self.assertIn("function goPage(n) { cancelPending();", self.js)
        keydown = self.js[self.js.index('document.addEventListener("keydown"'):]
        self.assertIn('e.key === "Escape"', keydown)
        self.assertIn("if (dir) { cancelPending();", keydown)

    def test_keys_use_event_code_not_event_key_for_digits(self):
        self.assertIn("Digit|Numpad", self.js)
        self.assertIn("e.code", self.js)
        keydown = self.js[self.js.index('document.addEventListener("keydown"'):]
        self.assertNotRegex(keydown, r"e\.key\s*===?\s*[\"']\d[\"']")           # không so e.key với chữ số
        self.assertNotIn("e.key.toLowerCase", keydown)
        self.assertIn("INPUT|SELECT|TEXTAREA", keydown)                           # bỏ qua khi đang gõ trong ô nhập


if __name__ == "__main__":
    unittest.main()
