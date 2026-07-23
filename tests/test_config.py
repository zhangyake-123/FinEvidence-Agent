import os
import tempfile
import unittest
from pathlib import Path

from finevidence.config import load_env_file


class ConfigEnvFileTest(unittest.TestCase):
    def test_load_env_file_reads_values_quotes_and_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "FINEVIDENCE_TEST_DOTENV_VALUE=alpha",
                        'FINEVIDENCE_TEST_DOTENV_QUOTED="beta value"',
                        "export FINEVIDENCE_TEST_DOTENV_URL=https://example.com/v1 # inline comment",
                    ]
                ),
                encoding="utf-8",
            )

            for key in (
                "FINEVIDENCE_TEST_DOTENV_VALUE",
                "FINEVIDENCE_TEST_DOTENV_QUOTED",
                "FINEVIDENCE_TEST_DOTENV_URL",
            ):
                os.environ.pop(key, None)

            try:
                loaded = load_env_file(env_path)

                self.assertEqual(loaded["FINEVIDENCE_TEST_DOTENV_VALUE"], "alpha")
                self.assertEqual(os.environ["FINEVIDENCE_TEST_DOTENV_QUOTED"], "beta value")
                self.assertEqual(os.environ["FINEVIDENCE_TEST_DOTENV_URL"], "https://example.com/v1")
            finally:
                for key in (
                    "FINEVIDENCE_TEST_DOTENV_VALUE",
                    "FINEVIDENCE_TEST_DOTENV_QUOTED",
                    "FINEVIDENCE_TEST_DOTENV_URL",
                ):
                    os.environ.pop(key, None)

    def test_load_env_file_does_not_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("FINEVIDENCE_TEST_DOTENV_KEEP=file-value", encoding="utf-8")

            os.environ["FINEVIDENCE_TEST_DOTENV_KEEP"] = "shell-value"
            try:
                loaded = load_env_file(env_path)
                self.assertNotIn("FINEVIDENCE_TEST_DOTENV_KEEP", loaded)
                self.assertEqual(os.environ["FINEVIDENCE_TEST_DOTENV_KEEP"], "shell-value")
            finally:
                os.environ.pop("FINEVIDENCE_TEST_DOTENV_KEEP", None)


if __name__ == "__main__":
    unittest.main()
