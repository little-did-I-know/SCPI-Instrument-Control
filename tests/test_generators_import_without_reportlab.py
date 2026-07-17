"""The report_generator.generators package must import even when reportlab is
absent -- this is the CI condition. A module-level use of a reportlab name (e.g.
subclassing canvas.Canvas) would raise NameError at import and crash unrelated
CI tests. Run in a subprocess so blocking reportlab can't pollute this process."""

import subprocess
import sys


def test_generators_package_imports_without_reportlab():
    code = (
        "import sys\n"
        "class _Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'reportlab' or name.startswith('reportlab.'):\n"
        "            raise ImportError('reportlab blocked for this test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
        "import scpi_control.report_generator.generators  # must not raise\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"generators import crashed without reportlab:\n{result.stderr}"
