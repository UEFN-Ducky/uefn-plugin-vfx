---
description: "Deep Niagara workflow: the golden path for a new effect, capability probes, finding user parameters when the store is protected, component control, conversion sessions, rebuilding a finalized emitter and recovering the orphaned actor, verifying without screenshots, and publish-blocker repair"
metadata:
  order: 1
  label: "Niagara workflow (deep)"
  default_enabled: false
  load_condition: "Authoring a new Niagara effect end to end, or a Niagara tool returned a capability miss, a user parameter will not take, an emitter session error, an orphaned actor after a rebuild, a screenshot that never lands, or a publish/cook blocker on an NS_ asset"
---

## Niagara workflow — beyond the golden path

### The golden path for a NEW effect

```
1  niagara_capabilities({})                  # once per session, need fx_converter: true
2  reuse the project material/mesh if the system already had one (get_dependencies);
   new assets stay under the project mount ({content_root}<Effect>/...) — NEVER /Game/VFX
3  create_niagara_system(asset_name, folder="{content_root}<Effect>/Niagara")
4  add_niagara_emitter(...)                  # ONE call, full module list, finalizes + saves
5  validate_uefn_asset(system_path)          # require VALID, 0 errors
6  spawn_actor -> set_actor_label -> set_actor_folder -> control_niagara_actor reset
7  save_current_level()
```

One tool call per step, and read every result: `parameters_applied` per module is
your proof the inputs landed, and `warnings` tells you what the tool corrected
(deprecated → V2 InitializeParticle, auto-added ParticleState).

### Reading `niagara_capabilities`

```
{"classes": {"NiagaraSystem": true, "FXConverterUtilitiesLibrary": true, ...},
 "fx_converter": true, "assembly": "mcp_tools",
 "component_parameter_setters": ["set_variable_bool", "set_variable_float", ...],
 "limits": {"max_dynamic_depth": 4, ...}, "open_sessions": []}
```

- `fx_converter: true` → emitter/module/renderer assembly is available through
  the MCP tools. `false` → this build cannot assemble; say so and route the user
  to the Niagara editor. Do **not** go looking for another API.
- `component_parameter_setters` is ground truth for `value_type` support — if
  `set_variable_position` is absent, use `vec3`.
- `open_sessions` lists systems with staged, **unfinalized** changes. Close them
  with `finalize_niagara_system` before you walk away — an unsaved system is
  exactly what was lost in the crash that motivated these tools.
- Call it **once**. Re-probing is the failure mode this skill exists to stop.

### User parameters: how to actually know the names

The asset's exposed-parameter store is protected in UEFN, so enumeration is not
guaranteed. In order of reliability:

1. **You linked it** — any `{"link": "User.X"}` in an assembly call creates the
   parameter, and `get_niagara_system_info` returns it under
   `linked_user_parameters`.
2. **Placed component probe** — `list_niagara_user_parameters({"actor_path":
   "<label>", "names": ["User.Speed", "User.Color"], "value_type": "float"})`.
   The engine getters return a found flag, so this is a real existence check.
3. `user_parameters` from `get_niagara_system_info` when the build happens to
   expose the store.

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
with `"reset"`, then verify as far as the level allows (see below).

### Verifying the result (screenshots are not guaranteed)

On a dense level (~8,600 actors was enough) `take_high_res_screenshot` and
console `HighResShot` never flush a PNG to `Saved/`: only the AppData preview
updates and `await_path` never resolves. Do not loop retrying captures.

Verify in this order, and say plainly what you could not see:

1. `validate_uefn_asset` on the system — authoritative, require VALID / 0 errors.
2. `parameters_applied` on every module in the `add_niagara_emitter` result, plus
   any `warnings`.
3. `get_niagara_component_info` on the placed actor (auto-activate, parameters).
4. A screenshot **if** it lands — and ask the user to confirm the look otherwise.

### Moving the viewport camera

`set_viewport_camera(rotation=[pitch, yaw, roll])` — pitch first. Passing yaw
first tilts the whole view, because the huge yaw value lands in roll. Always
`get_viewport_camera` first, move, then restore the user's camera exactly.

### Conversion sessions

Assembly runs inside a conversion session on the system asset. Each
`add_niagara_*` call finalizes and saves by default, which also **closes** the
session — a finalized emitter cannot be reopened, because UEFN's
`NiagaraSystemConversionContext` exposes no find-emitter.

- Whole emitter in one `add_niagara_emitter` call → nothing to manage.
- Need several calls for one emitter → pass `"finalize": false` on each and
  finish with `finalize_niagara_system`.
- "Emitter … is not open in this conversion session" is not retryable.

### Rebuilding a finalized emitter (and rescuing the placed actor)

Changing a finalized emitter means rebuilding the system, and `delete_asset`
breaks the placed actor: its `system_path` goes null, sometimes the actor is
removed outright, and its custom label/folder are lost.

```
get_all_actors({"label_filter": "<label>"})   # BEFORE deleting — read location from THIS result
delete_asset(<NS_ system>)
create_niagara_system(...)                    # same path, so Verse asset symbols keep resolving
add_niagara_emitter(...)                      # one call, corrected module list
delete_actors([<stale actor>]) ; spawn_actor({"asset_path": <NS_>, "location": <original>})
set_actor_label -> set_actor_folder -> control_niagara_actor reset
save_current_level()
```

Capture the transform **before** deleting: `get_actor_properties` fails on a
NiagaraActor ("Failed to find property") for location/rotation, so the
`get_all_actors` list result is the only reliable source. When hunting the stale
actor afterwards, search by class `NiagaraActor` as well as by label — the label
may have reverted.

### Component control actions

- `activate` — (re)start the effect; safe on running systems.
- `deactivate` — stop spawning, lets live particles finish.
- `reset` — restart from time 0 with current parameters (use after tuning).
- `reinitialize` — full teardown + reinit; heavier, use when reset isn't enough.

### Finding the NiagaraActor after spawn

`spawn_actor(asset_path=<NiagaraSystem>)` returns the actor; its label is the
handle for the component tools. Multiple effects: `set_actor_label` each one
immediately so later `set_niagara_component_parameter` calls are unambiguous.
Delete anything you spawned only to look at it — the level ships too.

### When the user wants a NEW effect

1. Check for an existing system first (`list_niagara_systems`, stock content) —
   assembling from scratch is slower than tuning something that already looks
   right.
2. Otherwise assemble it: read `stock_module_assembly.md`, create the project
   meshes/materials, then one emitter per call.
3. `create_niagara_system` alone renders nothing — it is an empty system until
   emitters are added.
4. Runtime gameplay triggering (explosion on elimination, etc.) = **VFX Spawner
   device** + Verse wiring — route that part through the uefn/verse skills.

### Publish / cook blockers

When UEFN reports disallowed Niagara references (Custom HLSL, Component
Renderer, `/Game/Effects/Niagara/Enum/ENiagaraCommon*`, etc.):

1. `validate_uefn_asset({"asset_path": "<blocked NS_>"})` — authoritative.
2. Optionally `get_dependencies` for supporting evidence (never the sole proof).
3. Graph surgery is not available. Do not retry `execute_python` graph edits —
   they are not exposed and some conversion APIs hard-crash the editor.
4. Fallback (automatic, with a visual-change warning):
   - Prefer an **already-valid in-plugin** Niagara system (same project), e.g.
     another `{content_root}/VFX/NS_*` that `validate_uefn_asset` marks `ok: true`.
   - Or **reassemble** a compliant replacement with the assembly tools (stock
     modules + project meshes are publish-safe by construction).
   - Do **not** duplicate `/CRD_VFX_Spawner/...` or other `/Game/...` explosions
     into the project plugin — stock packages can look VALID in place, then fail
     plugin reference validators after copy.
   - Replace the blocked asset **at the same path** so Verse asset symbols keep
     resolving, then re-run `validate_uefn_asset` until `ok: true`.
   - Delete temporary backups/candidates afterward — leftovers still fail publish.
5. Open for human graph edits only when the user insists on preserving the exact
   look: `open_asset_in_uefn`.

### Troubleshooting

- Particles pile up / never disappear, `Lifetime` seems ignored → the emitter is
  missing `/Niagara/Modules/Update/Lifetime/ParticleState` in Particle Update.
  Rebuild the emitter with it (the tool adds it unless `particle_state: false`).
- "Module has unmet dependencies" on `ScaleSpriteSize` / `ScaleMeshSize` →
  nothing initialized `Sprite Size` / `Mesh Scale`. Set it on V2
  InitializeParticle, or drop the scaler if the size is constant.
- Effect invisible after placement → `control_niagara_actor` `activate`, check
  `auto_activate` (`get_niagara_component_info`), confirm the emitter has a
  renderer and a spawn module, and that the level was saved.
- Mesh particles invisible → the renderer needs a **project** StaticMesh with a
  material baked on its slot (`create_niagara_mesh` does both).
- Parameter "does nothing" → wrong name, wrong `value_type`, or it only applies
  at spawn — `reset` after setting.
- Module rejected an input name → that name does not exist on that module. Use
  the frozen table; do not brute-force variants.
- `get_niagara_system_info` shows `emitters_note` → emitter handles are
  editor-only in this build; informational, not a failure.
