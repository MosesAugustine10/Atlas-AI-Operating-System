"""Launch the Atlas desktop application.

This example shows the simplest way to start Atlas programmatically:

    python examples/launch_atlas.py

When PySide6 is available, the full Qt window opens. When PySide6 is
absent, the script prints the wiring status and exits.

To wire real subsystems, pass them to :class:`AtlasApp`:

    from atlas.app import AtlasApp
    from atlas.providers.manager import ProviderManager
    from atlas.memory.engine import MemoryEngine
    from atlas.knowledge.engine import KnowledgeEngine

    app = AtlasApp(
        providers=ProviderManager(),
        memory=MemoryEngine(),
        knowledge=KnowledgeEngine(),
    )
    app.run()
"""

from __future__ import annotations

import sys


def main() -> int:
    """Launch Atlas."""
    from atlas.app import AtlasApp, has_qt

    if not has_qt():
        print("PySide6 is not available. Running in headless mode.")
        app = AtlasApp()
        print(f"Controllers: {', '.join(app.controller_names())}")
        print("Install PySide6 with `pip install PySide6` to launch the GUI.")
        return 0

    app = AtlasApp()
    print("Starting Atlas desktop application…")
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
