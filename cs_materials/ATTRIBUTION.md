# Material data attribution

The material names, categories and surface speeds (HSS and carbide, m/min) in `seed.json`
come from the material cards of the **FreeCAD Feeds and Speeds** addon
(https://github.com/dubstar-04/FeedsAndSpeeds), `Materials/*.FCMat`:

> (c) 2022 Daniel Wood, licensed under Creative Commons Attribution 3.0 (CC-BY 3.0),
> https://creativecommons.org/licenses/by/3.0/

Changes made here: converted from FCMat cards to JSON; kept only name, category ("Father")
and the two surface speeds. On request (CAM Studio menu > Add Feeds & Speeds Materials) they
are written back out as FreeCAD material files in the user's library, with this credit in
each file's Author/License fields. No code from that
addon (LGPL-2.1) is included in this project.
