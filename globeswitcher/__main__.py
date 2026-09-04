# SPDX-License-Identifier: Apache-2.0
"""Entry point: run the switcher, or render a demo frame."""

import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        from .demo import render
        target = sys.argv[2] if len(sys.argv) > 2 else "globeswitcher-demo.png"
        print(render(target))
        return

    from .daemon import main as run
    run()


if __name__ == "__main__":
    main()
