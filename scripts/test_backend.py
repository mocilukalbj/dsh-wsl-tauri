import unittest
import tempfile
import os
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
        with patch.object(backend, 'read_log', return_value='dsh web: http://127.0.0.1:3080/?token=test'), \
                patch.object(backend, 'authenticate', return_value=True), \
                patch.object(backend.subprocess, 'run') as start:
            self.assertFalse(backend.resolve(Path('/home/tester'), 3080)['started'])
            start.assert_not_called()

    def test_occupied_port_without_login_is_not_replaced(self):
        with patch.object(backend, 'read_log', return_value=''), \
                patch('socket.socket') as socket, \
                patch.object(backend.subprocess, 'run') as start:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(RuntimeError, 'occupied'):
                backend.resolve(Path('/home/tester'), 3080)
            start.assert_not_called()

    def test_external_log_reuses_backend_without_starting_process(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / 'launcher.out.log').write_text('http://127.0.0.1:3080/?token=test')
            with patch.object(backend, 'authenticate', return_value=True), \
                    patch.object(backend.subprocess, 'run') as start:
                result = backend.resolve(home, 3080, str(home / '*.out.log'))
                self.assertEqual(result['url'], 'http://127.0.0.1:3080/?token=test')
                self.assertFalse(result['started'])
                start.assert_not_called()

    def test_external_logs_owned_by_other_users_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / 'launcher.out.log').write_text('http://127.0.0.1:3080/?token=test')
            with patch.object(backend.os, 'getuid', return_value=os.getuid() + 1), \
                    patch.object(backend, 'authenticate') as auth, \
                    patch('socket.socket') as socket:
                socket.return_value.__enter__.return_value.connect_ex.return_value = 0
                with self.assertRaisesRegex(RuntimeError, 'occupied'):
                    backend.resolve(home, 3080, str(home / '*.out.log'))
                auth.assert_not_called()

    def test_journal_authentication_reuses_running_service(self):
        with patch.object(backend, 'read_log', return_value=''), \
                patch.object(backend, 'authenticate', return_value=True), \
                patch.object(backend.subprocess, 'run', return_value=SimpleNamespace(
                    stdout='http://127.0.0.1:3080/?token=journal')) as run:
            result = backend.resolve(Path('/home/tester'), 3080, journal_unit='custom-dsh.service')
            self.assertFalse(result['started'])
            self.assertEqual(run.call_args.args[0][:4], ['journalctl', '--user', '--unit', 'custom-dsh.service'])
            self.assertEqual(run.call_count, 1)

    def test_systemd_starts_only_after_free_port_check(self):
        with patch.object(backend, 'read_log', return_value=''), \
                patch.object(backend, 'authenticate', return_value=True), \
                patch('socket.socket') as socket, \
                patch.object(backend.subprocess, 'run', side_effect=[
                    SimpleNamespace(stdout=''), SimpleNamespace(returncode=0),
                    SimpleNamespace(stdout='http://127.0.0.1:3080/?token=started')]) as run:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            self.assertTrue(backend.resolve(Path('/home/tester'), 3080, journal_unit='dsh.service')['started'])
            self.assertEqual(run.call_args_list[1].args[0], ['systemctl', '--user', 'start', 'dsh.service'])

    def test_occupied_port_never_restarts_configured_systemd_service(self):
        with patch.object(backend, 'read_log', return_value=''), \
                patch('socket.socket') as socket, \
                patch.object(backend.subprocess, 'run', return_value=SimpleNamespace(stdout='')) as run:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(RuntimeError, 'occupied'):
                backend.resolve(Path('/home/tester'), 3080, journal_unit='dsh.service')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'journalctl')

    def test_log_read_is_bounded_and_missing_file_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'backend.log'
            self.assertEqual(backend.read_log(log), '')
            log.write_bytes(b'x' * 200000)
            self.assertEqual(len(backend.read_log(log)), 131072)


if __name__ == '__main__':
    unittest.main()
