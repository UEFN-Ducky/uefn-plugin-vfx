---
source_plugin_id: vfx
name: vfx
description: "Niagara VFX in UEFN — find, create, and place particle systems, drive user parameters, activate/reset effects; capability-guarded editor tools"
license: All Rights Reserved
metadata:
  label: "UEFN Niagara"
  version: 3
  author: UEFN-Ducky
  copyright: Copyright 2026 UEFN-Ducky
  allow_redistribute: false
---

# UEFN VFX — Niagara systems

Niagara work in UEFN is **editor-only** Python: place systems and tune their
**user parameters**. Emitter/module graph internals are NOT exposed to Python
(that is editor C++ territory) — author the effect in the Niagara editor or use
a stock system, then drive it from these tools. Runtime triggering belongs to
the **VFX Spawner device** wired via Verse, not to these tools.

The tools are **small composable primitives** — probe, read, create, change —
chain them for the task at hand.

## The tools (flat MCP tools)

| Kind | Tools |
|------|-------|
| **PROBE** | `niagara_capabilities` |
| **READ** | `list_niagara_systems`, `get_niagara_system_info`, `get_niagara_component_info`, `validate_uefn_asset`, `get_dependencies` |
| **CREATE** | `create_niagara_system` |
| **CHANGE** | `set_niagara_component_parameter`, `control_niagara_actor` |
| **REPAIR** | `duplicate_asset`, `delete_asset`, `rename_asset`, `save_asset`, `open_asset_in_uefn` |

Always `niagara_capabilities({})` first — UEFN builds vary in what Niagara API
Python sees. If a class is missing the tools say so and list what IS present;
adapt instead of retrying blindly.

## Golden path (place + tune an existing system)

```
niagara_capabilities({})                                          # PROBE
list_niagara_systems({"search": "smoke"})                         # READ -> pick a system
get_niagara_system_info({"system_path": "/VideoTest/VFX/NS_Smoke"})  # project path, not /Game/VFX
spawn_actor({"asset_path": "/VideoTest/VFX/NS_Smoke",
             "location": [0, 0, 100]})                            # generic tool -> NiagaraActor
set_niagara_component_parameter({"actor_path": "<label>",
    "param_name": "SpawnRate", "value_type": "float", "value": 50})   # CHANGE
control_niagara_actor({"actor_path": "<label>", "action": "reset"})   # CHANGE -> see it fresh
save_current_level()
```

## Hard rules

- **Parameter setters are fire-and-forget** — the engine silently ignores an
  unknown `param_name`. Read `user_parameters` from `get_niagara_system_info`
  first; never guess names.
- **`value_type` must match** the parameter's Niagara type:
  `float|int|bool|vec2|vec3|vec4|color|position`. A `color` takes `[r,g,b,a]`,
  vectors take float lists.
- **No emitter/module editing from Python.** If asked to "make the smoke
  denser", look for a user parameter first; if the system exposes none, say so
  and suggest editing the system in the Niagara editor — do not fake it.
- **Publish/cook blockers:** run `validate_uefn_asset` first. Do **not** treat a
  `/Script/NiagaraEditor` dependency alone as proof of Custom HLSL. If validation
  fails and graph APIs are unavailable, replace with a **validated in-plugin**
  template (duplicate another Roguelike `NS_*` that already returns `ok: true`)
  at the same asset path and warn that the look may change. Do **not** copy
  `/CRD_VFX_Spawner/...` systems into the project plugin — they can validate in
  their original package and still fail `AssetValidator_AssetReferenceRestrictions`
  / `FortValidator_FortExposedAssets` after duplication.
- **New systems from `create_niagara_system` are empty** — they render nothing
  until emitters are added in the Niagara editor. Prefer existing systems.
- **New assets:** `create_niagara_system` → omit `folder` or use
  `{content_root}VFX/...` from `get_project_info()`. **Never invent `/Game/VFX`**
  (cook `Disallowed reference`). Catalog/read under `/Game/Creative` is fine.
- Designing a NEW effect (layering systems, timing, color, scale, perf):
  read the **VFX design** reference before placing anything.

## After ANY VFX change

`save_current_level()` — placed actors and tuned parameters live in the level.
