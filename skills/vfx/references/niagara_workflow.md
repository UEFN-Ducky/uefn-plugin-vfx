---
description: "Deep Niagara workflow: reading capability probes, user-parameter types, component control, and what to do when the API is not exposed"
metadata:
  order: 1
  label: "Niagara workflow (deep)"
  default_enabled: false
  load_condition: "Niagara tool returned a capability miss / probe members, a user parameter will not take, or the user wants VFX beyond place-and-tune"
---

## Niagara workflow — beyond the golden path

### Reading `niagara_capabilities`

```
{"classes": {"NiagaraSystem": true, "NiagaraComponent": true, ...},
 "component_parameter_setters": ["set_variable_bool", "set_variable_float", ...]}
```

- Any `false` class → that tool family is unavailable in this UEFN build; the
  per-tool error repeats this. Fall back to `execute_python` only if the probe
  shows the pieces you need under different names.
- `component_parameter_setters` is the ground truth for `value_type` support —
  if `set_variable_position` is absent, use `vec3` instead of `position`.

### User parameters: the only tunable surface

`get_niagara_system_info` returns `user_parameters` when the build exposes the
parameter store. If it returns `user_parameters_probe` (member names) instead,
the store exists but can't be enumerated — get names from the Niagara editor UI
or the system's documentation, then set them anyway (setters accept any name).

Value types map to `NiagaraComponent` setters:

| value_type | setter | value shape |
|------------|--------|-------------|
| float | set_variable_float | 1.5 |
| int | set_variable_int | 3 |
| bool | set_variable_bool | true |
| vec2 | set_variable_vec2 | [x, y] |
| vec3 | set_variable_vec3 | [x, y, z] |
| vec4 | set_variable_vec4 | [x, y, z, w] |
| color | set_variable_linear_color | [r, g, b, a] |
| position | set_variable_position | [x, y, z] |

Setters are silent on unknown names — after setting, `control_niagara_actor`
with `"reset"` and eyeball the viewport (or `take_high_res_screenshot`).

### Component control actions

- `activate` — (re)start the effect; safe on running systems.
- `deactivate` — stop spawning, lets live particles finish.
- `reset` — restart from time 0 with current parameters (use after tuning).
- `reinitialize` — full teardown + reinit; heavier, use when reset isn't enough.

### Finding the NiagaraActor after spawn

`spawn_actor(asset_path=<NiagaraSystem>)` returns the actor; its label is the
handle for the component tools. Multiple effects: `set_actor_label` each one
immediately so later `set_niagara_component_parameter` calls are unambiguous.

### When the user wants a NEW effect

1. Prefer an existing system (`list_niagara_systems`, marketplace/stock content).
2. `create_niagara_system` makes an EMPTY system — emitters must be added in the
   Niagara editor by hand. Create it, place it, then tell the user which asset
   to open and finish; don't pretend the tool authored particles.
3. Runtime gameplay triggering (explosion on elimination, etc.) = **VFX Spawner
   device** + Verse wiring — route that part through the uefn/verse skills.

### Publish / cook blockers

When UEFN reports disallowed Niagara references (Custom HLSL, Component
Renderer, `/Game/Effects/Niagara/Enum/ENiagaraCommon*`, etc.):

1. `validate_uefn_asset({"asset_path": "<blocked NS_>"})` — authoritative.
2. Optionally `get_dependencies` for supporting evidence (never the sole proof).
3. Graph surgery is **not** available from Python in UEFN. Do not retry
   `execute_python` graph edits; they are not exposed and some conversion APIs
   hard-crash the editor.
4. Fallback (automatic, with a visual-change warning):
   - Prefer an **already-valid in-plugin** Niagara system (same project), e.g.
     another `/Roguelike/.../NS_*` that `validate_uefn_asset` marks `ok: true`.
   - Do **not** duplicate `/CRD_VFX_Spawner/...` or other `/Game/...` explosions
     into the project plugin — stock packages can look VALID in place, then fail
     plugin reference validators (and still carry Custom HLSL) after copy.
   - `validate_uefn_asset` the **temp duplicate** before touching production paths.
   - Replace the blocked asset **at the same path** (`duplicate_asset` /
     `delete_asset` / `rename_asset` + `save_asset`) so Verse asset symbols keep
     resolving.
   - Re-run `validate_uefn_asset` on the final path until `ok: true`.
   - Delete temporary backups/candidates afterward (broken backups would still
     fail publish if left in Content).
5. Open for human graph edits only when the user insists on preserving the
   exact look: `open_asset_in_uefn`.

### Troubleshooting

- Effect invisible after placement → `control_niagara_actor` `activate`, check
  `auto_activate` on the component (`get_niagara_component_info`), and confirm
  the level was saved.
- Parameter "does nothing" → wrong name (check `user_parameters`), wrong
  `value_type`, or the parameter only applies at spawn — try `reset` after.
- `get_niagara_system_info` shows `emitters_error` → emitter handles are
  editor-only in this build; that's informational, not a failure.
- Publish fails with Custom HLSL / Component Renderer → use the publish-blocker
  path above; do not claim Python fixed the emitter graph.
