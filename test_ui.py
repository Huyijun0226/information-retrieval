import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class WorkspaceTests(unittest.TestCase):
    def test_navigation_preserves_results(self):
        db = types.ModuleType("db")
        db.load_settings = lambda: dict(api_key="", base_url="", model_name="", password="123456")
        for name in ["save_settings", "update_password", "add_chat_msg", "clear_chat_history", "add_recommendation_history", "add_query_history", "add_translation_history", "update_query_hit_counts", "update_favorite_status"]:
            setattr(db, name, lambda *a, **k: None)
        for name in ["get_chat_history", "get_query_history", "get_translation_history"]:
            setattr(db, name, lambda *a, **k: [])
        with patch.dict(sys.modules, {"db": db}):
            at = AppTest.from_file(str(Path(__file__).with_name("app.py"))).run()
            self.assertEqual(len(at.exception), 0)
            next(b for b in at.button if "一键生成检索式" in b.label).click().run()
            self.assertIn("generated_snapshot", at.session_state)
            next(n for n in at.number_input if n.label == "起始年份").set_value(2020).run()
            self.assertGreaterEqual(len(at.code), 4)
            for page in ["公众号检索", "专业检索入口", "历史记录", "AI 设置", "转译工作台"]:
                at.radio(key="page_nav").set_value(page).run()
                self.assertEqual(len(at.exception), 0, page)
            self.assertGreaterEqual(len(at.code), 4)

if __name__ == "__main__":
    unittest.main()
