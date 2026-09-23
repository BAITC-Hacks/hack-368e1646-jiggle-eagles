"""Exercise the documented shell entry point as a real, separate server process."""
import json
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.request import urlopen

from test_money_graph import write_fixture


SOURCE = Path(__file__).resolve().parent.parent
LAUNCH = SOURCE / 'scripts' / 'money-graph.sh'


class LaunchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='money graph launch ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        write_fixture(self.root / 'input with spaces')

    def command(self, port, *args):
        return [str(LAUNCH), '--serve', '--port', str(port),
                '--out', str(self.root / 'output with spaces'),
                '--data', str(self.root / 'input with spaces'), *args]

    def stop(self, process):
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
                self.fail('Server did not stop after Ctrl+C (SIGINT)')

    def test_server_stays_available_until_stopped_and_can_restart(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        # Reusing the same port verifies that shutdown releases its listener.
        for attempt in range(2):
            with self.subTest(attempt=attempt):
                log_path = self.root / f'launch-{attempt}.log'
                with log_path.open('wb') as log:
                    process = subprocess.Popen(
                        self.command(port), cwd=self.root,
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True)
                    try:
                        deadline = time.monotonic() + 20
                        while f'Dashboard: {base}' not in log_path.read_text():
                            self.assertIsNone(process.poll(), log_path.read_text())
                            self.assertLess(time.monotonic(), deadline, log_path.read_text())
                            time.sleep(0.05)
                        # New connections model refreshes, tab closes and reopenings.
                        # No terminal input or open parent stdout pipe keeps it alive.
                        for _ in range(3):
                            with urlopen(base + '/', timeout=3) as response:
                                self.assertEqual(response.status, 200)
                                self.assertIn(b'Money Graph', response.read())
                            with urlopen(base + '/api/overview', timeout=3) as response:
                                self.assertEqual(json.load(response)['profile']['nodes'], 30)
                            self.assertIsNone(process.poll(), log_path.read_text())
                        with urlopen(base + '/exports/nodes_roles.csv', timeout=3) as response:
                            self.assertEqual(len(response.read().splitlines()), 31)
                    finally:
                        self.stop(process)
                    self.assertEqual(process.returncode, 0, log_path.read_text())

    def test_occupied_port_fails_without_announcing_readiness(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            result = subprocess.run(
                self.command(occupied.getsockname()[1]),
                cwd=self.root, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Dashboard could not start:', result.stderr)
        self.assertNotIn('Dashboard: http://', result.stdout)

    def test_missing_inputs_fail_without_announcing_readiness(self):
        result = subprocess.run(
            self.command(8765, '--data', str(self.root / 'missing inputs')),
            cwd=self.root, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Money Graph failed:', result.stderr)
        self.assertNotIn('Dashboard: http://', result.stdout)
