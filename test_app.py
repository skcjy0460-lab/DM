import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copy2

from streamlit.testing.v1 import AppTest


class StreamlitSmokeTests(unittest.TestCase):
    def test_initial_screen_renders(self):
        app = AppTest.from_file("app.py", default_timeout=10).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("당뇨 약제 조합 심사 워크벤치" in item.value for item in app.markdown))
        self.assertTrue(any("선택 조합 하이라이트 매트릭스" in item.value for item in app.subheader))
        self.assertTrue(any("약제 선택" in item.value for item in app.subheader))

    def test_product_combination_selection_renders_review(self):
        app = AppTest.from_file("app.py", default_timeout=10).run()
        app.multiselect[0].set_value(["다이아벡스정500밀리그램", "제미글로정50밀리그램"]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("MET + DPP-4i 2제 조합" in item.value for item in app.markdown))

    def test_missing_data_file_uses_builtin_catalog(self):
        with TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            copy2("app.py", temp_dir / "app.py")
            copy2("diabetes_engine.py", temp_dir / "diabetes_engine.py")
            app = AppTest.from_file(str(temp_dir / "app.py"), default_timeout=10).run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("기본 제품 목록" in item.value for item in app.warning))

    def test_root_catalog_is_accepted_when_data_folder_is_missing(self):
        with TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            copy2("app.py", temp_dir / "app.py")
            copy2("diabetes_engine.py", temp_dir / "diabetes_engine.py")
            copy2("data/drug_catalog.csv", temp_dir / "drug_catalog.csv")
            app = AppTest.from_file(str(temp_dir / "app.py"), default_timeout=10).run()
            self.assertEqual(len(app.exception), 0)
            self.assertFalse(any("최상위의" in item.value for item in app.info))

    def test_public_screen_hides_price_update_and_shows_copyright(self):
        app = AppTest.from_file("app.py", default_timeout=10).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any("약가 데이터 업데이트" in item.label for item in app.expander))
        self.assertTrue(any("주식회사 메디엄 조정윤" in item.value for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
