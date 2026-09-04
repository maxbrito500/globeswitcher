#!/usr/bin/env bash
#
# Copyright 2026 Max Brito
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/globeswitcher"
BIN="$HOME/.local/bin/globeswitcher"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/globeswitcher.desktop"
MENU_ENTRY="${XDG_DATA_HOME:-$HOME/.local/share}/applications/globeswitcher.desktop"
BACKUP="$DATA_DIR/keybindings-backup.json"

pkill -f "globeswitcher\.__main__" 2>/dev/null || true          # Python daemon
pkill -f "globeswitcher/app/globeswitcher" 2>/dev/null || true   # Flutter build
sleep 1

# Give Alt+Tab back to the desktop before deleting the record of what it was.
if [ -f "$BACKUP" ] && command -v gsettings >/dev/null; then
    python3 - "$BACKUP" <<'PYTHON'
import json, subprocess, sys

with open(sys.argv[1]) as handle:
    saved = json.load(handle)
for key, value in saved.items():
    subprocess.run(
        ["gsettings", "set", "org.gnome.desktop.wm.keybindings", key, value],
        check=False)
    print(f"restored {key} = {value}")
PYTHON
fi

rm -f "$BIN" "$AUTOSTART" "$MENU_ENTRY"
rm -rf "$DATA_DIR"

echo "Removed. Alt+Tab is back to your desktop's own switcher."
