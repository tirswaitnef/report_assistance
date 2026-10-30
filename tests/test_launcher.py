import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_demo_launcher", ROOT / "run.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="db-launcher-test-")
        self.addCleanup(self.storage.cleanup)
        self.root = Path(self.storage.name)

    def configure(self, key="fake-test-only-secret", model="example-fixed-model"):
        output = io.StringIO()
        with patch.object(launcher, "ROOT", self.root), patch.object(launcher.getpass, "getpass", return_value=key) as getpass, patch("builtins.input", return_value=model), patch("sys.stdout", output):
            launcher.configure_gemini()
        return output.getvalue(), getpass

    def test_key_uses_hidden_prompt_and_is_saved_only_locally(self):
        output, getpass = self.configure()
        self.assertEqual(getpass.call_count, 1)
        path = self.root / ".local" / "settings.json"
        settings = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(settings["GEMINI_API_KEY"], "fake-test-only-secret")
        self.assertEqual(settings["GEMINI_MODEL"], "example-fixed-model")
        self.assertEqual(settings["AI_PROVIDER"], "gemini")
        self.assertNotIn("fake-test-only-secret", output)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_existing_unrelated_local_settings_are_preserved(self):
        directory = self.root / ".local"
        directory.mkdir()
        path = directory / "settings.json"
        path.write_text(json.dumps({"unrelated": "preserve", "GEMINI_MODEL": "previous-model"}))
        self.configure()
        settings = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(settings["unrelated"], "preserve")
        self.assertEqual(settings["GEMINI_MODEL"], "example-fixed-model")

    def test_invalid_key_or_model_does_not_create_settings(self):
        for key, model in (("", "example-model"), ("key with spaces", "example-model"), ("test-key", "https://malicious.invalid/model")):
            with self.subTest(key=bool(key), model_is_url=model.startswith("https:")):
                with self.assertRaises(ValueError):
                    self.configure(key=key, model=model)
                self.assertFalse((self.root / ".local" / "settings.json").exists())

    def test_malformed_existing_configuration_is_not_overwritten(self):
        directory = self.root / ".local"
        directory.mkdir()
        path = directory / "settings.json"
        path.write_text("[broken-json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(path.read_text(encoding="utf-8"), "[broken-json")

    def test_blank_model_uses_documented_alias(self):
        self.configure(model="")
        settings = json.loads((self.root / ".local" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["GEMINI_MODEL"], "gemini-flash-latest")


if __name__ == "__main__":
    unittest.main()
