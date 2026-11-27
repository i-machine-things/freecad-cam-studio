# CAM Studio on FreeCAD 26.3

**Direction (Allan, 2026-11-27):** FreeCAD 26.3's new CAM UI/UX is good on its own: tabbed op
dialogs, tool-controller feeds with presets and a Feeds & Speeds wizard, collision-checked
linking. CAM Studio becomes a **small add-on of targeted tweaks** to 26.3's own dialogs, not a
replacement dialog, and **no new toolpath features** for now. Each tweak is filed as an issue
(label `26.3 tweak`) as Allan finds them while using 26.3. The 1.1-based work (PR #4 2D Offset
Roughing, PR #21 2D Adaptive Roughing) is parked as reference.

Tweaks either add to FreeCAD's own widgets when they open (no FreeCAD code changed) or watch
for objects (e.g. new tool controllers); files stay plain FreeCAD CAM files. Some tweaks may be
better offered to FreeCAD itself as pull requests; decided per tweak.

The rest of this document is the field-by-field audit done first, when the plan was a full
reskin. It's still the reference for what 26.3 has and lacks against Fusion.

This document maps each Fusion field (from the parity maps in `ROADMAP.md`, built from Allan's
Fusion screenshots) to what FreeCAD 26.3 has. Source: 26.3rc3 (`src/Mod/CAM`) and a property
dump of real 26.3 objects (rc2 binary; rc2 to rc3 changed no CAM settings, only bug fixes).

## Principles

1. **Stock objects only.** Operations are FreeCAD's own (`Path.Op.PocketShape`,
   `Path.Op.Adaptive`, ...) with FreeCAD's own proxies: no `ops/` subclasses, no extra
   properties. A file made with CAM Studio is a plain FreeCAD CAM file; in vanilla FreeCAD it
   opens in the stock dialogs.
2. **Only the dialog is ours.** Bars in Fusion's tab order: Tool, (Multi-axis), Geometry,
   Heights, Passes, Linking. Each shows FreeCAD settings under Fusion's names; FreeCAD settings
   Fusion lacks go under "Other Options" on the bar they belong to.
3. **Two levels.**
   - Level 1: CAM Studio's toolbar commands create stock ops and open them in our dialog.
   - Level 2 (switchable): with CAM Studio installed, editing *any* Pocket/Adaptive op opens our
     dialog, by switching the op's view provider to our page on document load (as CAM Studio
     already does for the Job). FreeCAD's own create buttons still show the stock dialog for
     the very first edit; changing that would need a patch to FreeCAD, which we don't do.
4. **Minimum version 26.3.** `package.xml` `freecadmin` 26.3 once this lands.

## 26.3's own dialog (seen in 26.3, 2026-11-27)

26.3 already moved toward Fusion's layout: an op dialog is a row of **icon tabs** (labels shown
when there's room, icon-only otherwise), not FreeCAD's old stacked bars. Pocket and Adaptive
both open with: **Base Geometry, Extensions, Heights, Tool Controller, Operation**.

- **Heights** tab: Work Plane at the top; a height diagram with Clearance, **Retract**
  (`SafeHeight`: FreeCAD itself now calls it Retract), Start, Step down, Finish step down,
  Final; Reset to defaults; the **Linking** group (collision avoidance strategy + clearance).
- **Tool Controller** tab: tool controller and coolant; a warning when the controller is shared
  ("used by N other operations"); every feed (horizontal, vertical, lead-in, lead-out, ramp,
  no-engagement), rapids, spindle speed and direction; the Feeds & Speeds button.
- **Operation** tab, Pocket: cut mode, pattern, angle, step over, radial stock to leave, retract
  threshold, ignore holes, rest machining, start point.
- **Operation** tab, Adaptive: cut region, operation type, step over in percent **and** distance,
  accuracy slider (Tolerance), lift distance, "retract threshold" (`KeepToolDownRatio`), radial
  stock to leave, force inside-out, use outline, rest machining, **Helix Parameters** (max
  pitch, max ramp angle, cone angle, max / min diameter), Stop.

So the reskin delta is small: Fusion's tab order (Tool first), FreeCAD's Operation tab split
into **Passes** and **Linking**, the stepdowns moved from Heights to Passes and the Linking
group from Heights to Linking, Fusion's names and collapsible sections, and the Leads / Ramp
dressup sections on Linking. The Feed Height question mostly answers itself: 26.3 labels
`SafeHeight` "Retract" (still to confirm against rc3 G-code).

## What carries over from the 1.1 work

- The dialog framework: bar ordering, Heights + Depths folded into one Heights bar, the
  "[distance] = [%] of tool Ø" stepover row, the Tool bar layout (`pages/common.py` on PR #4).
- Job Edit's labelled Material row (26.3 also has a Material Picker: check for overlap),
  the toolbars, Simulate / Inspect / Post / Check actions.
- The test harness (`.cam-tests`, outside the repo) and both parity maps.

Parked (1.1-only, no 26.3 equivalent): per-op feeds, Chip Thinning, Plunge Outside Stock,
Preferred Lead-In Positions (multi-point), leads on every entry and exit, Retract Height as a
separate property, Use Even Stepdowns, Finishing Stepdowns count, Axial Stock to Leave (pocket),
Sideways Compensation direction fix for outside-in.

## Tool bar (shared by all ops)

In 26.3, feeds and speeds live on the **tool controller**, which several operations can share.
New in 26.3: the controller has Lead-In, Lead-Out, Ramp and No-Engagement feeds, and a
**Suggest Feeds & Speeds** dialog (from material, machine and operation type, or a named
**tool preset**). Presets are edited in the ToolBit editor's Presets tab.

| Fusion field | 26.3 | Notes |
|---|---|---|
| Tool, Select... | `ToolController` link + library browser | as today |
| Edit... | Tool controller editor | 26.3's editor, incl. its Feeds & Speeds button |
| Preset | Tool presets via Suggest Feeds & Speeds | **Have** (new in 26.3) |
| Spindle Speed | `TC.SpindleSpeed` | shared by every op on that controller |
| Surface Speed, Feed per Tooth, Plunge Feed per Revolution | derived | display only, as today |
| Ramp Spindle Speed | none | Missing |
| Cutting Feedrate | `TC.HorizFeed` | |
| Lead-In / Lead-Out Feedrate | `TC.LeadInFeed` / `TC.LeadOutFeed` | new in 26.3 |
| Transition Feedrate | none | Missing |
| Ramp Feedrate | `TC.RampFeed` | new in 26.3 (Adaptive helix uses it since rc3) |
| Plunge Feedrate | `TC.VertFeed` | |
| Coolant | op `CoolantMode` | per op |
| (Fusion Linking) No-Engagement Feedrate | `TC.NoEngagementFeed` | new in 26.3 |

## 2D Offset Roughing = stock Pocket Shape (`ClearingPattern` Offset)

Our command creates a stock Pocket Shape with `ClearingPattern = Offset` and doesn't show the
pattern ("offset means offset"). Nothing stops a user changing it in the property editor;
pinning it would need a subclass, which this direction rules out.

**Geometry:** Base Geometry page + Extensions page as today. `CloseOpenPaths` (new) closes open
areas with straight lines: put it under Geometry. Rest Machining: `UseRestMachining` (cleared
by earlier ops), not Fusion's tool-diameter version: Partial. Stock Contours: Missing.

**Heights:** Clearance = `ClearanceHeight`, Top = `StartDepth`, Bottom = `FinalDepth`.
**To verify on rc3:** what `SafeHeight` does now. In 1.1 the tool rapids to it and feeds from
there (Fusion's Feed Height); 26.3's link strategy "Retract Height" says it "uses safe height
for rapid moves between areas", which is Fusion's Retract Height. The label depends on the
generated G-code.

**Passes:**
| Fusion field | 26.3 | Notes |
|---|---|---|
| Tolerance | Job `GeometryTolerance` | per Job, not per op: Partial |
| Sideways Compensation | `CutMode` | Climb / Conventional |
| Clearing Order (CAM Studio) | `StartAt` | Center / Edge |
| Maximum Stepover | `StepOver` (%) | distance = % row; `ForceMaxStepOver` (new) under Other Options |
| Multiple Depths: Maximum Roughing Stepdown | `StepDown` | |
| Finishing Stepdown | `FinishDepth` | |
| Use Even Stepdowns, Wall Taper, Order by Depth/Step | none | Missing |
| Finishing Passes: count | `FinishingPasses` | **new in 26.3** |
| Finishing Passes: stepover, one stepdown, helix ramp | `FinishingOffset`, `FinishingOneStepDown`, `FinishingRampHelix` | new; shown when passes > 0 |
| Finish Feedrate, Leads on all Finishing Passes, Repeat, Overlap | none | Missing |
| Radial Stock to Leave | `ExtraOffset` | |
| Axial Stock to Leave | none | Missing |
| Minimum Cutting Radius, Both Ways, Morphed Spiral, Smoothing, Feed Optimization | none | Missing |
| (FreeCAD) Use Outline, Region order | `UseOutline`, `SortingMode` (new) | Other Options |

**Linking:** 26.3's new **Linking** feature: `CollisionAvoidanceStrategy` (Clearance Height /
Retract Height / Line of Sight / Tool Diameter / Tool Shape), `CollisionClearance`, plus the
pocket's `RetractThreshold` (stay down instead of retracting for short links).
| Fusion field | 26.3 | Notes |
|---|---|---|
| Retraction Policy, Keep Tool Down, Maximum Stay-Down Distance | Collision strategy + clearance + `RetractThreshold` | different model, comparable result: Partial |
| High Feedrate Mode, Allow Rapid Retract, Lift Height | none | Missing (Lead In/Out dressup has Rapid Plunge) |
| Lead-In / Lead-Out (radius, sweep, linear distance, perpendicular) | **Lead In/Out dressup**: Style (Arc / Line / Perpendicular / Tangent / Helix ...), Radius, Angle, Extend, Offset, Invert | a separate object wrapping the op, see decision 2 |
| Vertical Lead radius | none | Missing |
| Ramp Type, angle | **Ramp Entry dressup** (Method 1-3, Helix; Angle; Start Depth) or Lead In/Out Helix style | dressup, see decision 2 |
| Preferred Lead-In Positions | `UseStartPoint` + `StartPoint` | one point: Partial |
| Plunge Outside Stock, Predrill, Exit Positions | none | Missing |

## 2D Adaptive Roughing = stock Adaptive (`OperationType` Clearing)

26.3's Adaptive now has the helix settings Fusion has.

**Geometry:** Base Geometry + Extensions. Stock Contours: `Side` Outside (clear to the stock
edge): Partial. Rest Machining: `UseRestMachining` (**new**): Partial.

**Passes:**
| Fusion field | 26.3 | Notes |
|---|---|---|
| Tolerance | `Tolerance` | unitless accuracy factor, not a length |
| Optimal Load | `StepOverPercent` (now a float) | distance = % row |
| Both Ways, Minimum Cutting Radius, Slot Clearing, Direction | none | solver-limited |
| Multiple Depths | `StepDown`, `FinishDepth` | |
| Order by Depth / Area | `OrderCutsByRegion` | only with Model Aware |
| Radial / Axial Stock to Leave | `StockToLeave` / `ZStockToLeave` | axial only with Model Aware |
| Smoothing, Feed Optimization | none | Missing |
| (FreeCAD) Force Inside Out, Use Outline, Model Aware | Other Options | |

**Linking:**
| Fusion field | 26.3 | Notes |
|---|---|---|
| Maximum Stay-Down Distance | `KeepToolDownRatio` | a ratio, not a distance: Partial |
| Lift Height | `LiftDistance` | |
| No-Engagement Feedrate | `TC.NoEngagementFeed` | check Adaptive applies it |
| Ramp Type | helix only | |
| Ramping Angle | `HelixMaxRampAngle` | **new** |
| Ramp Taper Angle | `HelixConeAngle` | |
| Helical Ramp Diameter / Minimum Ramp Diameter | `HelixMaxDiameterPercent` / `HelixMinDiameterPercent` (% of tool) | **new**: distance = % rows |
| Maximum Ramp Stepdown | `HelixMaxPitch` | **new** |
| Leads, Positions, High Feedrate Mode, Retraction Policy | none | Missing (Adaptive has no Linking feature) |

## Multi-axis tab

`Workplane` (**new**, per op): "the named work plane this operation works in, shared with other
operations of the Job; its local +Z is the tool axis". That is Fusion's Tool Orientation in
FreeCAD form: a Multi-axis bar with Tool Orientation = Workplane becomes possible. Polar and
Wrap machining: Missing.

## Decisions (Allan, 2026-11-27)

1. **Feeds: edit the tool controller.** The Tool bar shows and edits the tool controller's feeds
   and says how many operations share it; 26.3's **Suggest Feeds & Speeds** stands in for
   Fusion's Preset / Reset to Defaults. Per-op feeds may return later as a feature branch.
2. **Leads and ramps: edit from Linking.** The Linking bar has Leads and Ramp sections that add
   or edit the op's Lead In/Out and Ramp Entry dressups (FreeCAD's own features; the dressup
   object appears in the tree wrapping the op).
3. **Level 2 skin: a preference, on by default.** Turning it off gives FreeCAD's stock dialogs
   back for ops not created from CAM Studio's buttons.
4. Still open: **Feed Height / Retract Height labels** wait for the SafeHeight check on rc3.

## Order of work (after the decisions)

1. Branch setup: `freecadmin` 26.3, shared dialog framework ported from PR #4 (`pages/common.py`
   without the per-op feed code), test harness on 26.3.
2. 2D Offset Roughing dialog over stock Pocket Shape.
3. 2D Adaptive Roughing dialog over stock Adaptive.
4. Level 2 skin.
5. Then other ops (Face, Contour, Drilling), same pattern.
