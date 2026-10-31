import contextlib
import importlib.util
import io
import os
from pathlib import Path
import re
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("database_lab_helper_under_test", Path(__file__).resolve().parents[1] / "lab.py")
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class LabHelperTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="db-lab-helper-test-")
        self.addCleanup(self.storage.cleanup)
        self.root = Path(self.storage.name)
        self.env_file = self.root / ".local" / "lab.env"
        for name, value in (("ROOT", self.root), ("ENV_FILE", self.env_file)):
            patcher = patch.object(lab, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_environment(self):
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text("LAB_ROOT_PASSWORD=" + "a" * 32 + "\nLAB_DB_PASSWORD=" + "b" * 32 + "\n", encoding="utf-8")

    def test_local_unix_and_windows_pipe_engines_are_accepted(self):
        for endpoint in ("unix:///var/run/docker.sock", "npipe:////./pipe/dockerDesktopLinuxEngine"):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {}, clear=True), patch.object(lab, "docker") as docker:
                docker.side_effect = [SimpleNamespace(stdout=endpoint), SimpleNamespace(stdout="linux\n"), SimpleNamespace(stdout="v2")]
                lab.check_local_engine()
                self.assertEqual(docker.call_args_list[1].args[0], ["info", "--format", "{{.OSType}}"])

    def test_explicit_remote_host_is_rejected_before_daemon_access(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "ssh://lab@example.invalid"}, clear=True), patch.object(lab, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "local Docker"):
                lab.check_local_engine()
            docker.assert_not_called()

    def test_explicit_context_takes_precedence_over_host(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "unix:///var/run/docker.sock", "DOCKER_CONTEXT": "remote-lab"}, clear=True), patch.object(lab, "docker") as docker:
            docker.return_value = SimpleNamespace(stdout="ssh://lab@example.invalid\n")
            with self.assertRaisesRegex(RuntimeError, "local Docker"):
                lab.check_local_engine()
            self.assertEqual(docker.call_args_list[0].args[0][:2], ["context", "inspect"])
            self.assertEqual(docker.call_count, 1)

    def test_windows_containers_are_rejected(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "npipe:////./pipe/docker_engine"}, clear=True), patch.object(lab, "docker") as docker:
            docker.return_value = SimpleNamespace(stdout="windows\n")
            with self.assertRaisesRegex(RuntimeError, "Linux containers"):
                lab.check_local_engine()

    def test_environment_creation_uses_private_random_credentials_without_printing(self):
        output = io.StringIO()
        with patch.object(lab, "docker", return_value=SimpleNamespace(stdout="")), contextlib.redirect_stdout(output):
            lab.ensure_environment()
        values = dict(line.split("=", 1) for line in self.env_file.read_text(encoding="utf-8").splitlines() if "=" in line)
        self.assertEqual(set(values), {"LAB_ROOT_PASSWORD", "LAB_DB_PASSWORD"})
        self.assertNotEqual(values["LAB_ROOT_PASSWORD"], values["LAB_DB_PASSWORD"])
        for value in values.values():
            self.assertRegex(value, r"^[A-Za-z0-9_-]{20,128}$")
            self.assertNotIn(value, output.getvalue())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o600)

    def test_valid_environment_is_reused_without_rotation(self):
        self.write_environment()
        original = self.env_file.read_bytes()
        with patch.object(lab, "docker") as docker, patch.object(lab.secrets, "token_urlsafe") as random_secret:
            lab.ensure_environment()
        self.assertEqual(self.env_file.read_bytes(), original)
        docker.assert_not_called()
        random_secret.assert_not_called()

    def test_existing_lab_volumes_without_configuration_block_new_credentials(self):
        with patch.object(lab, "docker", return_value=SimpleNamespace(stdout="dbreport-lab_pg-a-data\n")):
            with self.assertRaisesRegex(RuntimeError, "volumes already exist"):
                lab.ensure_environment()
        self.assertFalse(self.env_file.exists())

    def test_malformed_environment_is_not_overwritten_or_echoed(self):
        self.env_file.parent.mkdir()
        original = "LAB_ROOT_PASSWORD=private-invalid-value!\n"
        self.env_file.write_text(original, encoding="utf-8")
        with patch.object(lab, "docker") as docker:
            with self.assertRaises(RuntimeError) as error:
                lab.ensure_environment()
        self.assertNotIn("private-invalid-value", str(error.exception))
        self.assertEqual(self.env_file.read_text(encoding="utf-8"), original)
        docker.assert_not_called()

    def test_compose_scopes_commands_to_its_project_and_environment_file(self):
        with patch.object(lab, "docker") as docker:
            lab.compose(["ps"])
        self.assertEqual(docker.call_args.args[0], ["compose", "--project-name", "dbreport-lab", "--env-file", str(self.env_file),
                                                   "-f", str(self.root / "lab" / "compose.yaml"), "ps"])

    def run_action(self, args):
        with patch.object(lab.sys, "argv", ["lab.py", *args]), patch.object(lab, "check_local_engine"), \
             patch.object(lab, "compose") as compose, patch.object(lab, "ensure_environment") as ensure, \
             contextlib.redirect_stdout(io.StringIO()):
            code = lab.main()
        return code, compose, ensure

    def test_up_waits_for_healthy_services(self):
        code, compose, ensure = self.run_action(["up"])
        self.assertEqual(code, 0)
        ensure.assert_called_once()
        self.assertEqual(compose.call_args.args[0], ["up", "-d", "--wait", "--wait-timeout", "240"])

    def test_down_retains_volumes_and_credentials(self):
        self.write_environment()
        original = self.env_file.read_bytes()
        code, compose, _ = self.run_action(["down"])
        self.assertEqual(code, 0)
        self.assertEqual(compose.call_args.args[0], ["down"])
        self.assertEqual(self.env_file.read_bytes(), original)

    def test_collect_uses_argument_array_and_available_project_interpreter(self):
        self.write_environment()
        executable = self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        executable.parent.mkdir(parents=True)
        executable.touch()
        with patch.object(lab.sys, "argv", ["lab.py", "collect", "--output", "outputs/my case", "--seed", "52"]), \
             patch.object(lab, "check_local_engine"), patch.object(lab.subprocess, "run", return_value=SimpleNamespace(returncode=7)) as run:
            code = lab.main()
        self.assertEqual(code, 7)
        self.assertEqual(run.call_args.args[0], [str(executable), str(self.root / "lab" / "collect.py"), "--output", "outputs/my case", "--seed", "52",
                                               "--project", "dbreport-lab", "--env-file", str(self.env_file)])
        self.assertEqual(run.call_args.kwargs["cwd"], self.root)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_non_up_actions_require_original_configuration(self):
        with self.assertRaisesRegex(RuntimeError, "Missing .local/lab.env"):
            self.run_action(["collect"])


if __name__ == "__main__":
    unittest.main()
