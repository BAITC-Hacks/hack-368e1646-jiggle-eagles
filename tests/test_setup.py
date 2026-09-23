"""Local launch contracts, using disposable environments and no downloaded packages."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parent.parent


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='money graph setup ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'project with spaces'
        (self.root / 'scripts').mkdir(parents=True)
        for name in ['setup.sh', 'money-graph.sh', 'check_environment.py']:
            shutil.copy2(SOURCE / 'scripts' / name, self.root / 'scripts' / name)
        (self.root / '.python-version').write_text('.'.join(map(str, sys.version_info[:3])) + '\n')
        (self.root / 'requirements-money-graph.txt').write_text('# No downloads in setup regression fixtures.\n')
        (self.root / 'money_graph').mkdir()
        (self.root / 'money_graph' / '__init__.py').write_text('')
        (self.root / 'money_graph' / '__main__.py').write_text(
            'import json, os, sys\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\n')

    def command(self, *args, env=None):
        return subprocess.run(args, cwd=self.root.parent, env=env, text=True,
                              capture_output=True, timeout=60)

    def environment(self, *options):
        result = self.command(sys._base_executable, '-I', '-m', 'venv', '--without-pip',
                              *options, str(self.root / '.venv'))
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.root / '.venv' / 'bin' / 'python'

    def test_setup_creates_isolated_environment_and_reuses_it(self):
        env = dict(os.environ, MONEY_GRAPH_PYTHON=sys._base_executable)
        script = str(self.root / 'scripts' / 'setup.sh')
        first = self.command('bash', script, env=env)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        sentinel = self.root / '.venv' / 'preserve-me'
        sentinel.write_text('existing environment')
        second = self.command('bash', script, env=env)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(sentinel.read_text(), 'existing environment')
        self.assertIn('include-system-site-packages = false', (self.root / '.venv' / 'pyvenv.cfg').read_text())

    def test_missing_environment_has_setup_instruction(self):
        result = self.command('bash', str(self.root / 'scripts' / 'money-graph.sh'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('./scripts/setup.sh', result.stderr)

    def test_wrong_runtime_does_not_replace_existing_environment(self):
        self.environment()
        sentinel = self.root / '.venv' / 'preserve-me'
        sentinel.write_text('keep')
        (self.root / '.python-version').write_text('0.0.0\n')
        for script in ['setup.sh', 'money-graph.sh']:
            with self.subTest(script=script):
                result = self.command('bash', str(self.root / 'scripts' / script))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Python 0.0.0 is required', result.stderr)
                self.assertEqual(sentinel.read_text(), 'keep')

    def test_wrong_explicit_interpreter_fails_before_creation(self):
        (self.root / '.python-version').write_text('0.0.0\n')
        result = self.command('bash', str(self.root / 'scripts' / 'setup.sh'),
                              env=dict(os.environ, MONEY_GRAPH_PYTHON=sys._base_executable))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Selected interpreter must be Python 0.0.0', result.stderr)
        self.assertFalse((self.root / '.venv').exists())

    def test_missing_or_drifted_package_blocks_launch(self):
        python = self.environment()
        (self.root / 'requirements-money-graph.txt').write_text('setup-fixture==1.0\n')
        script = str(self.root / 'scripts' / 'money-graph.sh')
        missing = self.command('bash', script)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('setup-fixture is missing', missing.stderr)
        site = self.command(str(python), '-I', '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))')
        self.assertEqual(site.returncode, 0, site.stderr)
        metadata = Path(site.stdout.strip()) / 'setup_fixture-2.0.dist-info'
        metadata.mkdir()
        (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: setup-fixture\nVersion: 2.0\n')
        drifted = self.command('bash', script)
        self.assertNotEqual(drifted.returncode, 0)
        self.assertIn('must be 1.0; found 2.0', drifted.stderr)

    def test_system_packages_and_global_interpreter_are_rejected(self):
        python = self.environment('--system-site-packages')
        check = str(self.root / 'scripts' / 'check_environment.py')
        result = self.command(str(python), '-I', check)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exclude system packages', result.stderr)
        result = self.command(sys._base_executable, '-I', check)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('project-local .venv', result.stderr)

    def test_external_environment_symlink_is_rejected(self):
        self.environment()
        outside = self.root.parent / 'external-venv'
        (self.root / '.venv').rename(outside)
        (self.root / '.venv').symlink_to(outside, target_is_directory=True)
        for script in ['setup.sh', 'money-graph.sh']:
            result = self.command('bash', str(self.root / 'scripts' / script))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('project-local', result.stderr)

    def test_launch_from_another_directory_preserves_arguments_and_ignores_pythonpath(self):
        import json
        self.environment()
        injected = self.root.parent / 'injected'
        injected.mkdir()
        (injected / 'sitecustomize.py').write_text('raise SystemExit("ambient Python path was loaded")\n')
        args = ['--data', 'directory with spaces', '--port', '9876']
        result = self.command('bash', str(self.root / 'scripts' / 'money-graph.sh'), *args,
                              env=dict(os.environ, PYTHONPATH=str(injected)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(self.root.resolve()), args])

    def test_invalid_pin_and_arguments_fail_without_creating_environment(self):
        script = str(self.root / 'scripts' / 'setup.sh')
        result = self.command('bash', script, '--unknown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Usage:', result.stderr)
        (self.root / '.python-version').write_text('3.14\n')
        result = self.command('bash', script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('major.minor.patch', result.stderr)
        self.assertFalse((self.root / '.venv').exists())
