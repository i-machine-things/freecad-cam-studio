# Installing

This workbench is **not** submitted to FreeCAD's official Addon catalogue, and that's a
deliberate choice, not a placeholder for later — a UI layer this close to a specific commercial
product's workflow is not something upstream FreeCAD would plausibly accept, and competing with
FreeCAD's own stock CAM workbench via the same catalog entry isn't the goal anyway. Install
directly from this repository instead.

## Option A — Addon Manager, custom repository (recommended)

1. In FreeCAD: **Edit → Preferences → Addon manager**.
2. Click the **+** button to open the custom-repository dialog.
3. Repository URL: this repo's git URL (`.git` suffix optional). Branch: `master`.
4. Open **Tools → Addon manager** — this addon now shows up alongside the catalog ones and can
   be installed/updated from there (update = `git pull` under the hood, so a local `git` install
   is required for updates to work).

## Option B — manual clone

Clone this repo directly into your FreeCAD user `Mod` directory:

```sh
# Linux
git clone <this-repo-url> ~/.local/share/FreeCAD/Mod/CamStudio

# macOS
git clone <this-repo-url> "~/Library/Application Support/FreeCAD/Mod/CamStudio"

# Windows (PowerShell)
git clone <this-repo-url> "$env:APPDATA\FreeCAD\Mod\CamStudio"
```

Restart FreeCAD. "CAM Studio" should appear in the workbench selector dropdown.

If any of these paths don't match your install (portable installs, Snap/Flatpak, etc.), confirm
the real one from FreeCAD's own Python console: `App.getUserAppDataDir()` prints the actual
directory FreeCAD is using, with `Mod` as a subdirectory of it.

## Current status

Phase 1 is still in progress (see [ROADMAP.md](ROADMAP.md)) — installing today gets you an empty
workbench entry with no commands yet. This file exists now so the install path is validated
early, before there's a reason to actually use it.
