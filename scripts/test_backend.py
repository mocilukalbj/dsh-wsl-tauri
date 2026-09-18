import unittest
from unittest.mock import patch
from pathlib import Path
import backend
from types import SimpleNamespace


class BackendTests(unittest.TestCase):
    def test_version_is_read_from_resolved_dsh_package(self):
        with patch.object(backend.subprocess, 'run', return_value=SimpleNamespace(stdout='/node/bin/dsh\n')), \
                patch.object(Path, 'resolve', return_value=Path('/node/lib/node_modules/@deepseek-ai/dsh/lib/bin.js')), \
                patch.object(Path, 'read_text', return_value='{"name":"@deepseek-ai/dsh","version":"0.1.6-alpha.1"}'):
            self.assertEqual(backend.installed_version(Path('/home/tester')), '0.1.6-alpha.1')

    def test_unrelated_executable_cannot_supply_core_version(self):
        with patch.object(backend.subprocess, 'run', return_value=SimpleNamespace(stdout='/node/bin/dsh\n')), \
                patch.object(Path, 'resolve', return_value=Path('/node/other/lib/bin.js')), \
                patch.object(Path, 'read_text', return_value='{"name":"other","version":"0.1.6"}'):
            with self.assertRaisesRegex(RuntimeError, 'not @deepseek-ai/dsh'):
                backend.installed_version(Path('/home/tester'))

    def test_only_accepts_configured_loopback_login(self):
        log = "\n".join([
            "http://127.0.0.1:3080/?token=old",
            "http://evil.test:3080/?token=bad",
            "http://127.0.0.1:8080/?token=bad",
            "http://user@127.0.0.1:3080/?token=bad",
            "http://127.0.0.1:3080/api?token=bad",
            "http://127.0.0.1:3080/",
            "http://127.0.0.1:3080/?token=new",
        ])
        self.assertEqual(backend.candidate_urls(log, 3080), [
            "http://127.0.0.1:3080/?token=new", "http://127.0.0.1:3080/?token=old"])

    def test_existing_authenticated_backend_is_never_started_again(self):
        with patch.object(Path, 'exists', return_value=True), \
                patch.object(Path, 'read_text', return_value='dsh web: http://127.0.0.1:3080/?token=test'), \
                patch.object(backend, 'authenticate', return_value=True), \
                patch.object(backend.subprocess, 'run') as start:
            self.assertFalse(backend.resolve(Path('/home/tester'), 3080)['started'])
            start.assert_not_called()

    def test_occupied_port_without_login_is_not_replaced(self):
        with patch.object(Path, 'exists', return_value=False), \
                patch('socket.socket') as socket, \
                patch.object(backend.subprocess, 'run') as start:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(RuntimeError, 'occupied'):
                backend.resolve(Path('/home/tester'), 3080)
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
