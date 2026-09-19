---
description: "Assembling Niagara systems from stock modules through MCP: emitter recipes, V2 InitializeParticle, the mandatory ParticleState, canonical particle_update order (ParticleState → forces → solver → collision), the frozen stock-module input map, nested dynamic-input trees, renderer + project-mesh rules, and the incremental plan for large systems"
metadata:
  order: 0
  label: "Stock module assembly (MCP)"
  default_enabled: false
  load_condition: "Building or extending a Niagara system: adding emitters, modules, renderers, particle meshes, or orbit/burst motion"
---

# Stock module assembly through MCP

Everything here is verified against UEFN. The input names are **frozen** — they
were probed once, at the cost of a long session and two editor crashes. Use
them; do not re-probe, and never fall back to `execute_python`.

## The call shape

`add_niagara_emitter` builds one whole emitter and then finalizes + saves:

```json
{
  "system_path": "{content_root}Solar/Niagara/NS_Solar",
  "emitter_name": "Planet_Earth",
  "loop_duration": 1000000,
  "modules": [
    {"name": "SpawnBurst", "module_path": "/Niagara/Modules/Emitter/SpawnBurst_Instantaneous",
     "category": "emitter_update",
     "parameters": [{"name": "Spawn Count", "value_type": "int", "value": 1}]},
    {"name": "InitializeParticle", "module_path": "/Niagara/Modules/Spawn/Initialization/V2/InitializeParticle",
     "category": "particle_spawn",
     "parameters": [
       {"name": "Lifetime", "value_type": "float", "value": 100000},
       {"name": "Color", "value_type": "color", "value": [0.2, 0.45, 0.9, 1]},
       {"name": "Mesh Scale", "value_type": "vec3", "value": [1.2, 1.2, 1.2]}
     ]},
    {"name": "ParticleState", "module_path": "/Niagara/Modules/Update/Lifetime/ParticleState",
     "category": "particle_update", "parameters": []},
    {"name": "Orbit", "module_path": "/Niagara/Modules/Spawn/Location/RotateAroundPoint",
     "category": "particle_update",
     "parameters": [
       {"name": "Rotation Rate", "link": "User.EarthSpeed", "value_type": "float"},
       {"name": "Radius", "value_type": "float", "value": 1500},
       {"name": "Rotation Axis", "value_type": "vec3", "value": [0, 0, 1]},
       {"name": "Rotation Center", "link": "Engine.Owner.Position", "value_type": "position"}
     ]}
  ],
  "renderers": [
    {"type": "mesh", "name": "PlanetMesh", "mesh": "{content_root}Solar/Meshes/SM_Planet_Rocky"}
  ]
}
```

**V2 InitializeParticle only.**
`/Niagara/Modules/Spawn/Initialization/InitializeParticle` has been deprecated
since UE/UEFN 5.3 — yellow "Deprecated module" banner, unreliable conversion.
The tool rewrites it to
`/Niagara/Modules/Spawn/Initialization/V2/InitializeParticle` and says so in
`warnings`; write V2 yourself so you never see that warning. Same input names.

Parameter specs come in exactly three shapes:

| Shape | JSON | Use |
|-------|------|-----|
| Literal | `{"name": "Radius", "value_type": "float", "value": 1500}` | Fixed values |
| Link | `{"name": "Rotation Rate", "link": "User.EarthSpeed", "value_type": "float"}` | Exposes a **user parameter** (tunable in Details / at runtime), or reads engine values like `Engine.Owner.Position`, `Emitter.Age` |
| Dynamic | `{"name": "Normalized Angle", "value_type": "float", "dynamic": {"module_path": "/Niagara/DynamicInputs/...", "parameters": [...]}}` | Computed inputs; nests up to depth 4 |

Linking `User.X` is what **creates** the exposed user parameter — there is no
"add user parameter" API. `get_niagara_system_info` reports every `User.*` the
tools linked as `linked_user_parameters`.

Categories: `emitter_spawn`, `emitter_update`, `particle_spawn`,
`particle_update`.

Two modules are added for you, both suppressible:

| Auto module | Category | Opt out | Why |
|-------------|----------|---------|-----|
| `/Niagara/Modules/Emitter/EmitterState` | `emitter_update` | `emitter_state: false` | `loop_duration` sets its `Loop Duration` — use a huge value (1000000) for a permanently running system |
| `/Niagara/Modules/Update/Lifetime/ParticleState` | `particle_update`, first | `particle_state: false` | Without it particles **never die** — see below |

### ParticleState: the #1 silent failure

`Lifetime` on InitializeParticle is a stored attribute and nothing enforces it.
Without `/Niagara/Modules/Update/Lifetime/ParticleState` in Particle Update,
particles age forever, pile up on the floor (a `Collision` module pins them
there so the buildup is obvious), and `Lifetime` looks like it does nothing.

Any emitter with a finite `Lifetime` MUST have `ParticleState` — write it
explicitly as the first `particle_update` module with empty `parameters`. For a
permanently running body (an orbiting planet) keep it and give `Lifetime` a huge
value; `particle_state: false` is only for an emitter that must never age.

### Canonical module order

Within `particle_update` the stack order is the list order, and it decides the
result:

1. `ParticleState` **first** — age and kill.
2. All forces (`GravityForce`, `CurlNoiseForce`, drag, …).
3. `/Niagara/Modules/Solvers/SolveForcesAndVelocity` — integrates only the
   forces that precede it.
4. `/Niagara/Modules/Collision/Collision` — after the solver (CPU sim).

Falling / pouring emitter, one call, in order:

```
emitter_update:  SpawnRate                      # SpawnRate (float) = density
particle_spawn:  V2/InitializeParticle          # Lifetime, Color, Sprite Size
                 SphereLocation                 # Sphere Radius = spout size
particle_update: Update/Lifetime/ParticleState  # MANDATORY — kills at Lifetime
                 Update/Forces/GravityForce
                 Update/Forces/CurlNoiseForce   # Noise Strength/Frequency = spread
                 Solvers/SolveForcesAndVelocity # after ALL forces
                 Collision/Collision            # after the solver
renderers:       sprite, material = {content_root}<Effect>/Materials/M_...
```

### Size: initialize, then scale (or don't scale)

`ScaleSpriteSize` / `ScaleMeshSize` multiply an attribute something earlier must
have initialized. With nothing upstream, UEFN throws **"module has unmet
dependencies"** as a hard error (the assembly tool refuses the call before it
gets that far).

- Constant size → **no scale module at all**; set `Sprite Size` / `Mesh Scale`
  on V2 InitializeParticle and stop.
- Size animating over life → set it on V2 InitializeParticle **and then** add
  the scaler.

### Multi-call emitters

`add_niagara_module` / `add_niagara_renderer` / `set_niagara_module_parameter`
only work while the emitter's conversion session is open — UEFN's
`NiagaraSystemConversionContext` has **no find-emitter**, so a finalized emitter
cannot be reopened. Either:

- put everything in one `add_niagara_emitter` call (preferred), or
- chain calls with `"finalize": false` and close with `finalize_niagara_system`.

"Emitter … is not open in this conversion session" is never retryable. To change
an emitter that was already finalized: `delete_asset` the whole `NS_` system,
`create_niagara_system` at the same path, and rebuild it in one
`add_niagara_emitter` call with the corrected module list — then recover the
placed actor (see `niagara_workflow.md`, deleting the asset orphans it).

## Frozen stock module inputs

Only these names are known-good. A rejected name is a hard error.

| Module path | Inputs |
|-------------|--------|
| `/Niagara/Modules/Emitter/EmitterState` | `Loop Duration` (float) |
| `/Niagara/Modules/Emitter/SpawnBurst_Instantaneous` | `Spawn Count` (int), `Spawn Time` (float) |
| `/Niagara/Modules/Emitter/SpawnRate` | `SpawnRate` (float) |
| `/Niagara/Modules/Spawn/Initialization/V2/InitializeParticle` | `Lifetime`, `Color`, `Position`, `Mass`, `Sprite Size` (vec2), `Mesh Scale` (vec3), `Sprite Rotation` — the non-V2 path is deprecated |
| `/Niagara/Modules/Update/Lifetime/ParticleState` | none — add with empty `parameters` |
| `/Niagara/Modules/Spawn/Location/SphereLocation` | `Sphere Radius`, `Surface Only Band Thickness`, `Sphere Origin` (position), `Offset` (vec3), `Non Uniform Scale` |
| `/Niagara/Modules/Spawn/Location/TorusLocation` | `Handle Radius`, `Large Radius`, `Torus Origin`, `Offset`, `Non Uniform Scale` |
| `/Niagara/Modules/Spawn/Location/RotateAroundPoint` | `Rotation Rate`, `Rotation Center` (position), `Rotation Axis` (vec3), `Radius` |
| `/Niagara/Modules/Spawn/Location/V2/RotateAroundPoint` | same, plus `Position` (vec3); center is vec3 |
| `/Niagara/Modules/Update/Position/JitterPosition` | `Jitter Amount`, `Jitter Delay` |
| `/Niagara/Modules/Update/Orientation/MeshRotationRate` | `Rotation Rate` |
| `/Niagara/Modules/Update/Color/Color` | `Color`, `Scale Color` (vec3), `Scale Alpha` |
| `/Niagara/Modules/Update/Size/ScaleMeshSize` | `Scale Factor` (vec3) — ONLY if `Mesh Scale` is initialized first |
| `/Niagara/Modules/Update/Size/ScaleSpriteSize` | `Scale Factor` (vec2) — ONLY if `Sprite Size` is initialized first |
| `/Niagara/Modules/Update/Forces/GravityForce` | defaults are fine |
| `/Niagara/Modules/Update/Forces/CurlNoiseForce` | `Noise Strength`, `Noise Frequency` |
| `/Niagara/Modules/Solvers/SolveForcesAndVelocity` | none — place after all forces |
| `/Niagara/Modules/Collision/Collision` | defaults (CPU sim) — place after the solver |

Dynamic inputs (`"dynamic"` values only):

| Dynamic input path | Inputs |
|--------------------|--------|
| `/Niagara/DynamicInputs/Multiply/Multiply_Float` | `A`, `B` |
| `/Niagara/DynamicInputs/Multiply/Multiply_VectorByFloat` | `Vector` (vec3), `Float` |
| `/Niagara/DynamicInputs/Multiply/Multiply_Vector2D_ByFloat` | `Vector2D`, `Float` |
| `/Niagara/DynamicInputs/Add/Add_Float` | `A`, `B` |
| `/Niagara/DynamicInputs/Angles/Sine` | `Normalized Angle`, `Scale`, `Period`, `Bias` |
| `/Niagara/DynamicInputs/Angles/Cosine` | `Normalized Angle`, `Scale`, `Period`, `Bias` |
| `/Niagara/DynamicInputs/TypeConversions/MakeVector` | `X`, `Y`, `Z` |
| `/Niagara/DynamicInputs/Vectors/Position/AddVectorToPosition` | `Position` (position), `Vector` (vec3) |
| `/Niagara/DynamicInputs/Execution/ReturnNormalizedExecIndex` | none — use as a dynamic source for per-particle phase |
| `/Niagara/DynamicInputs/UniformRange/UniformRangedFloat` | `Minimum`, `Maximum` |

Useful link names: `Emitter.Age`, `Engine.Owner.Position`, plus any `User.*` you
introduce.

## Motion recipes

**Orbit (default).** Stock `RotateAroundPoint` with `Radius`, `Rotation Rate`,
`Rotation Axis`, `Rotation Center` = `Engine.Owner.Position`. Inner bodies get a
higher rate. This is the path to use unless the user needs exact geometry.

**Exact ring / cos-sin layout (advanced, depth-capped).** Feed
`AddVectorToPosition` a `MakeVector` of `Cosine`/`Sine` scaled by radius, with
the angle from `Multiply_Float(Emitter.Age, speed)` (animated) or
`ReturnNormalizedExecIndex` (static N-around-a-ring). The tools cap nesting at
depth 4 and 24 dynamic nodes per module — that ceiling exists because deeper
trees crashed the editor. If you hit it, simplify or hand-author.

**Asteroid belt.** `TorusLocation` (`Large Radius` = belt radius, `Handle
Radius` = thickness) + `JitterPosition` + `MeshRotationRate`.

**Ambience.** `SphereLocation` with a large radius + `SpawnRate`, sprite
renderer, slow `CurlNoiseForce`.

## Renderers

| Type | What the tool does | Your job |
|------|--------------------|----------|
| `mesh` | `create_mesh_renderer_properties()` → `meshes[0].mesh` | Pass a **project** StaticMesh; bake the material on the mesh |
| `sprite` | `new_object(NiagaraSpriteRendererProperties, outer=system)` | Pass a project material/MI |
| `ribbon`, `light` | FXConverter factories | Ribbon takes a material |
| `component` | **refused** | Component renderers fail UEFN publish |

Two constructions are load-bearing: the bare
`unreal.NiagaraSpriteRendererProperties()` constructor makes an outer-less
UObject and crashes the editor on finalize, and mesh materials go on the mesh —
`override_materials` was crash-adjacent, so the tools do not touch it.

## Particle meshes (always create them)

```
create_niagara_mesh({"asset_name": "SM_Planet_Rocky", "shape": "sphere",
                     "radius": 50, "steps": 24,
                     "folder": "{content_root}Solar/Meshes",
                     "material": "{content_root}Solar/MaterialInstances/MI_Planet_Rocky"})
```

Shapes: `sphere | box | cylinder | cone | torus | capsule | disc`; `scale`
squashes the result (asteroids), `size` sizes a box, `replace: true` rebuilds.
`/Engine/BasicShapes/*` is rejected — and UEFN cannot duplicate it into a
project anyway (`duplicate_asset` returns `None`), so there is no workaround to
look for.

## Materials

Use the materials MCP tools. Proven for Niagara in UEFN:

- Reference look: `/Niagara/DefaultAssets/DefaultSpriteMaterial` (additive
  unlit, ParticleColor × SphereMask).
- No Custom HLSL (`uefn_limits.custom_hlsl_node: false`), but
  `MaterialExpressionParticleColor` **does** exist and works even though
  `list_uefn_material_expression_classes` omits Particle* nodes.
- Set `used_with_niagara_sprites` / `used_with_niagara_mesh_particles` /
  `used_with_niagara_ribbons` with `set_material_flags`.

## Large systems — incremental, always

A solar-system-class build is a sequence of small verified steps, never one
script:

1. Folders, materials + MIs, then every `SM_*` particle mesh.
2. `create_niagara_system`, then the sun core emitter → place → look at it.
3. Sun glow sprites → verify.
4. **One** planet with `RotateAroundPoint` → verify.
5. One orbit ring at a modest burst count (not 192 × 8 up front) → verify.
6. Remaining planets and rings, one call each; then belt and dust.
   **Sky stars are not Niagara** — `skill_read_subskill("materials", "starfield_recipe")`.

Check every result. If a call errors, fix that emitter — do not queue more work
on top of a broken system.

## Walls (stop here, do not probe)

| Dead end | Why |
|----------|-----|
| Custom module-script graphs | `NiagaraGraph` / node wiring not exposed |
| `NiagaraToolset_*` | Classes exist, no callable Python methods |
| Module inputs from AssetRegistry tags | Only `ModuleUsageBitmask` — no parameter names |
| Reading/writing `ExposedParameters` on the asset | Protected in UEFN; probe a placed component instead |
| Duplicating `/Engine/BasicShapes/*` | Returns `None` in UEFN |
| Custom `Particles.*` writes (`set_parameter_directly`) | Not exposed through MCP; stock modules + `User.*` links only |
