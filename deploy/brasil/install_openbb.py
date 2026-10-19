"""Install the OpenBB fork in editable mode, skipping providers we do not use.

Wraps ``openbb_platform/dev_install.py`` without modifying upstream files.
Usage (from the OpenBB project root):

    openbb/.venv/bin/python openbb/deploy/brasil/install_openbb.py --routers

Skipped: providers/eia (its build hook needs EIA_API_KEY and openbb-core at
build time, so it cannot build from a clean checkout).
"""

import sys
from pathlib import Path

FORK_PLATFORM = Path(__file__).resolve().parents[2] / "openbb_platform"
SKIPPED_PACKAGES = {"openbb_platform/providers/eia"}

sys.path.insert(0, str(FORK_PLATFORM))
import dev_install  # noqa: E402

_get_tracked_packages = dev_install.get_tracked_packages


def get_tracked_packages() -> list[Path]:
    """Return the fork's tracked packages minus SKIPPED_PACKAGES."""
    packages = _get_tracked_packages()
    skipped = [p for p in packages if p.as_posix() in SKIPPED_PACKAGES]
    for package in skipped:
        dev_install.log(f"  - {package.as_posix()} (skipped by install_openbb.py)")
    return [p for p in packages if p.as_posix() not in SKIPPED_PACKAGES]


dev_install.get_tracked_packages = get_tracked_packages

if __name__ == "__main__":
    dev_install.main()
