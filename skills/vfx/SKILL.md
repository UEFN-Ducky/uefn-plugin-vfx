---
source_plugin_id: vfx
name: vfx
description: "Niagara VFX in UEFN — assemble systems from stock modules via MCP (emitters, renderers, project particle meshes), place them, drive user parameters; V2 InitializeParticle only, ParticleState or particles never die, never execute_python, never probe assets"
license: Ducky Source-Available License v1.0
metadata:
  label: "UEFN Niagara"
  version: 6
  author: UEFN-Ducky
  copyright: Copyright 2026 UEFN-Ducky
  allow_redistribute: false
---

# UEFN VFX — Niagara systems

**CRITICAL — editor mutations are SERIAL:** one heavy MCP call → wait → next
(`spawn_actor`, Niagara assemble tools, `save_current_level`). Never parallel /
same-turn multi — freezes UEFN. Details:
`skill_read_subskill("uefn", "batch_commands")`.

## Never do this

| Never | Instead |
|-------|---------|
| `/Niagara/Modules/Spawn/Initialization/InitializeParticle` (deprecated since 5.3) | `/Niagara/Modules/Spawn/Initialization/V2/InitializeParticle` — same inputs |
| An emitter with a finite `Lifetime` and no `ParticleState` | `/Niagara/Modules/Update/Lifetime/ParticleState` **first** in `particle_update` — without it particles never die |
| `ScaleSpriteSize` / `ScaleMeshSize` on an uninitialized size | set `Sprite Size` / `Mesh Scale` on V2 InitializeParticle; for constant size use **no** scale module |
| Retrying "emitter is not open in this conversion session" | rebuild: `delete_asset` the system → recreate at the same path → one `add_niagara_emitter` → recover the orphaned actor |
| `execute_python` for Niagara | the MCP tools, or the Niagara editor |
| Batching / parallel editor calls | one tool call per step, wait for each result (`batch_commands`) |
| `/Game/VFX`, `/Game/Materials`, … for new assets | `{content_root}<Effect>/...` from `get_project_info()` |
| `/Engine/BasicShapes/*` as a particle mesh | `create_niagara_mesh` |
| Component renderers | sprite / mesh / ribbon / light |
| Guessing a module input name | the frozen table in `references/stock_module_assembly.md` |

Two layers, and the difference decides everything you do:

| Layer | Available? | How |
|-------|-----------|-----|
| System / emitter / **stock module** / renderer stack | **Yes** | `add_niagara_emitter`, `add_niagara_module`, `add_niagara_renderer`, `set_niagara_module_parameter` |
| **Custom** module-script graphs (`NiagaraGraph` node wiring) | No | Hand-author in the Niagara editor; never probe for it |
| `NiagaraToolset_*` classes | No (present in `dir(unreal)`, zero callable methods) | Ignore completely |

So "make me a custom effect" is real work you can do — with **stock** modules
from `/Niagara/Modules/...` and `/Niagara/DynamicInputs/...`, wired through MCP.

## The tools (flat MCP tools)

| Kind | Tools |
|------|-------|
| **PROBE** | `niagara_capabilities` (once per session) |
| **READ** | `list_niagara_systems`, `get_niagara_system_info`, `list_niagara_user_parameters`, `get_niagara_component_info`, `validate_uefn_asset`, `get_dependencies` |
| **CREATE** | `create_niagara_system`, `create_niagara_mesh` |
| **ASSEMBLE** | `add_niagara_emitter`, `add_niagara_module`, `add_niagara_renderer`, `set_niagara_module_parameter`, `finalize_niagara_system` |
| **CHANGE** | `set_niagara_component_parameter`, `control_niagara_actor` |
| **REPAIR** | `duplicate_asset`, `delete_asset`, `rename_asset`, `save_asset`, `open_asset_in_uefn` |

Materials go through the **materials** MCP tools (`create_material`,
`add_material_expression`, `create_material_instance`, …) — the VFX tools never
wrap material editing.

## Golden path (author a new effect)

```
niagara_capabilities({})                         # once — require fx_converter: true
create_folder {content_root}<Effect>/{Niagara,Materials,MaterialInstances,Meshes}
# materials MCP -> master materials + MIs
create_niagara_mesh({"asset_name": "SM_Planet_Rocky", "shape": "sphere",
                     "folder": "{content_root}<Effect>/Meshes",
                     "material": "{content_root}<Effect>/MaterialInstances/MI_Planet_Rocky"})
create_niagara_system({"asset_name": "NS_Solar", "folder": "{content_root}<Effect>/Niagara"})
add_niagara_emitter({...})                       # ONE emitter — finalizes + saves
validate_uefn_asset                              # require VALID, 0 errors
spawn_actor({"asset_path": ".../NS_Solar"}) -> set_actor_label -> set_actor_folder
                                                 -> control_niagara_actor reset
save_current_level
```

Then repeat `add_niagara_emitter` **once per emitter**, checking the result each
time — `parameters_applied` proves the inputs landed, and `warnings` reports what
the tool corrected for you (V2 rewrite, auto-added `ParticleState`). Read
`references/stock_module_assembly.md` before the first `add_niagara_emitter`
call — it holds the frozen module input names and the module order that matters
(ParticleState → forces → `SolveForcesAndVelocity` → `Collision`).

## Hard rules

- **One emitter per call.** A monolithic builder that finalized ~22 emitters
  with deep dynamic-input chains **took UEFN down** and lost the unsaved system.
  Every `add_niagara_*` call finalizes and saves; keep it that way.
- **Never `execute_python` for Niagara.** No FXConverter scripts, no
  `build_*.py` / `solar_lib.py` pastes, no input-name discovery loops. If a tool
  can't express it, the answer is the Niagara editor, not Python.
- **Real Content only.** No `__probe` / `Temp` folders, no `NS_MeshTest` /
  `NS_*Probe` assets, no unsaved editor-only systems. The tools reject those
  paths. Delete any test actor you spawn (`delete_actors`) — the level ships too.
- **Mesh particles need a project mesh.** `create_niagara_mesh` first.
  `/Engine/BasicShapes/*` is banned and cannot even be duplicated in UEFN
  (`duplicate_asset` returns `None`). Bake the look onto the mesh's material
  slot; skip Niagara `override_materials`.
- **Never guess module input names.** A rejected input is a hard error, not a
  retry signal. Use the frozen table in `references/stock_module_assembly.md`,
  or stop and tell the user which module needs hand-editing.
- **Orbits default to stock `RotateAroundPoint`.** Exact cos/sin position math
  through nested dynamic inputs is capped at depth 4 and is the path that
  crashed the editor twice — only use it when the user needs exact ring layout.
- **Parameter setters are fire-and-forget** — the engine silently ignores an
  unknown `param_name` on a placed component. Confirm names with
  `get_niagara_system_info` (assembly-linked `User.*` params) or
  `list_niagara_user_parameters` on the placed actor.
- **`value_type` must match** the Niagara type:
  `float|int|bool|vec2|vec3|vec4|color|position`. `color` takes `[r,g,b,a]`.
- **New assets stay under the project mount** — `{content_root}<Effect>/...`
  from `get_project_info()`. Never invent `/Game/VFX` (cook
  `Disallowed reference`). Reading `/Game/Creative` is fine.
- **`validate_uefn_asset` is the proof, not a screenshot.** On a dense level
  `take_high_res_screenshot` often never flushes a PNG — do not loop retrying.
  Verify with validate + `parameters_applied`, and tell the user you could not
  eyeball it. Moving the camera to look: `set_viewport_camera` rotation is
  `[pitch, yaw, roll]`; `get_viewport_camera` first and restore it after.
- **Publish/cook blockers:** run `validate_uefn_asset`. Component renderers and
  Custom HLSL are blockers — the renderer tool refuses `component` outright. Do
  not treat a `/Script/NiagaraEditor` dependency alone as proof of Custom HLSL,
  and do not copy `/CRD_VFX_Spawner/...` systems into a project plugin.
- Designing a NEW effect (layering, timing, color, scale, perf): read the
  **VFX design** reference before placing anything.

## After ANY VFX change

`save_current_level()` — placed actors and tuned parameters live in the level.
Asset-side changes are already saved by the assembly tools.

## References

- `references/stock_module_assembly.md` — MCP assembly recipes, frozen stock
  module inputs, dynamic-input trees, renderer + mesh rules. **Read before
  assembling.**
- `references/niagara_workflow.md` — capability probes, user parameters,
  component control, publish-blocker repair.
- `references/vfx_design.md` — composing effects that read well and run fast.
