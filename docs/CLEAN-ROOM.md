# Clean-room provenance

This document states how this project is built and what it deliberately avoids. Read it before
contributing a spec or implementation change.

## What "clean room" means here

Two things never happen in this project:

1. **No decompilation, disassembly, or reading of Autodesk's Fusion binaries or source.** Nothing
   in this repo's history, issues, or spec docs should ever reference output of a decompiler,
   disassembler, or debugger run against Fusion 360.
2. **No copying of Autodesk's copyrighted expression** — icons, artwork, exact UI copy/strings,
   help-text wording, or marketing material — into this project's code, assets, or docs.

## What's allowed, and what the spec is built from

Behavior specs in `docs/spec/` are written from:
- Autodesk's own **public** help pages, blog posts, and official tutorials (cited by URL).
- Third-party tutorials, reviews, and community docs (cited by URL) describing observed behavior.
- Screenshots of Fusion's UI as published in the above public sources — described in prose, not
  reproduced pixel-for-pixel.
- FreeCAD's own existing `Path`/CAM workbench source and docs, as the implementation base.

Each spec file should cite its sources inline so a reader (or a future contributor) can verify
no binary was involved and no copyrighted text was lifted verbatim.

## Why this matters

- **Autodesk's EULA bars reverse engineering Fusion 360.** That's a contract term, independent of
  copyright — avoiding decompilation entirely is what keeps this project outside that line.
- **Patents cover some CAM toolpath algorithms** (e.g. adaptive-clearing-style strategies).
  Independent invention is not a defense to patent infringement, and clean-room process only
  defends against *copyright* claims. When a spec describes an algorithm's *effect* (what a
  toolpath looks like, what parameters a user sets), prefer implementing it against published,
  non-proprietary machining literature and FreeCAD's existing algorithms rather than trying to
  match Autodesk's specific internal method.
- **"1:1 UI" claims carry real trade-dress/copyright risk** if taken literally (pixel-identical
  layouts, copied icons/strings). This project targets a *comparable workflow* — matching the
  sequence of steps, panel organization, and terminology concepts a Fusion CAM user would
  recognize — not a literal pixel clone. Icons, strings, and exact layouts are original.

## Scope boundary for contributors

If you're writing or reviewing a spec doc: describing what you saw while using your own licensed
copy of Fusion ("I opened Fusion and tried it") is ordinary use of the program, described in your
own words -- no decompiling, disassembling, debugging, or extracting files. **The license terms
that apply to your copy govern what you may do with it; check them, and if they restrict
something, don't do it.** Never paste Autodesk's own help text verbatim, and do not attach
screenshots containing Autodesk-owned icon/logo assets to this repo.
