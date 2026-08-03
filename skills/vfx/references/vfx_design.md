---
description: "VFX design principles for UEFN — what is and is not authorable, assembling effects from stock modules and layering systems, timing envelopes, color as gameplay language, scale against the player, readability, and performance budgets"
metadata:
  label: "VFX design"
  default_enabled: false
  load_condition: "User wants to design/create a new visual effect, make an effect look better/cinematic, choose effect colors, or asks why an effect looks weak or hurts performance"
---

# VFX design — compose, don't fake

## What you can and cannot author (be honest)

- **Can**: assemble emitters from **stock** modules and renderers through MCP
  (`add_niagara_emitter` — see `stock_module_assembly.md`), find and duplicate
  existing systems, drive **user parameters**, place/activate/reset, and
  **layer** several systems into one composed effect.
- **Cannot**: author custom module-script graphs (`NiagaraGraph` node wiring is
  not exposed) or run Python builders — a monolithic one crashed the editor.
  Never pretend a parameter tweak rewrote an emitter.
- `create_niagara_system` alone makes an EMPTY system that renders nothing;
  emitters come from the assembly tools or the Niagara editor.

## Two workflows

**Tune what exists** (fastest when something close already ships):

```
list_niagara_systems({"search": "fire"})                 # find candidates
get_niagara_system_info({"system_path": "..."})          # read user parameters
duplicate_asset({...})                                   # your own copy to tune
spawn_actor({"asset_path": "...", "location": [...]})    # place it
set_niagara_component_parameter({...})                   # tune (exact names only)
control_niagara_actor({"actor_path": "...", "action": "reset"})   # see it fresh
validate_uefn_asset                                      # the proof; screenshot if it lands
```

**Assemble a new one** when nothing fits: project meshes + materials, then one
emitter per call, verifying in the viewport as you go. Link the knobs you want
tunable to `User.*` while assembling — that is the only way they become user
parameters later.

## Layering — one effect is several layers

A convincing effect is a stack. When you assemble the effect yourself, each
layer is an **emitter** inside one system (one `add_niagara_emitter` call each,
so it drops into the level as a single asset). When you compose from existing
systems, each layer is its own placed actor.

| Layer | Job | Lifetime |
|-------|-----|----------|
| Core flash | The "hit" — bright, small, instant | 0.1–0.3 s |
| Body | The subject: flame, beam, burst | effect duration |
| Glow/light | Soft halo that sells brightness | slightly longer than body |
| Debris/sparks | Fast physical bits flying out | 0.3–1 s |
| Smoke/dissipation | The lingering exit | 1–3 s, fades last |

Placed layers go within ~50 uu of a shared origin; `attach_actor` them to one
parent prop so the whole effect moves as a unit. Skip layers a small effect
doesn't need — a pickup sparkle is one emitter, an explosion is four.

## Timing envelope

Effects read as **anticipation → impact → dissipation**:

- Anticipation (optional): a brief gather/charge — makes the impact feel
  earned (0.2–0.5 s).
- Impact: the brightest, largest frame within the first 0.1–0.2 s.
- Dissipation: longest phase, strictly decaying — nothing should get
  brighter during the tail.

Loopable ambient effects (torches, fog, auras) must have NO readable impact
moment — constant energy, or players keep glancing at them.

## Color is gameplay language

- **One hue per meaning**, project-wide: e.g. red = enemy damage, blue =
  player abilities, green = healing, gold = loot. Never reuse a meaning-hue
  for decoration.
- Brightest/whitest at the core, hue saturating outward, darkest at the
  smoke — the "hot center" gradient reads as energy.
- Tune via color user parameters (`value_type: "color"`, `[r,g,b,a]`) when
  the system exposes them.
- Contrast with the environment: a blue effect in a blue-lit ice zone
  disappears; judge from player distance, not the editor close-up.

## Scale against the player (190 uu)

- Personal effects (pickup, heal, buff): 50–150 uu — visible without hiding
  the character.
- Combat impacts: 100–300 uu; area denial/zone effects: match the actual
  gameplay radius EXACTLY (a 512 uu hazard with a 300 uu telegraph is a lie
  players will hate).
- Landmark/setpiece effects (beacon, portal, storm): 500+ uu, visible across
  the zone — these double as landmarks (see leveldesign).
- Verify with `get_actor_bounds` on the placed NiagaraActor — it is measurable
  even when a capture will not flush.

## Readability and performance

- One dominant effect per moment: if everything glows, nothing reads.
  Background/ambient layers dim and slow; gameplay-critical effects bright
  and sharp.
- Perf killers in order: **overdraw** (many large transparent quads stacked —
  the #1 cost), particle counts, always-on effects never culled. Prefer a few
  large well-placed sprites + one light over hundreds of tiny particles.
- Cap simultaneous layered effects; reuse placed actors (activate/deactivate
  via `control_niagara_actor`) instead of stacking duplicates.
- After placing: check `get_editor_stats` if the scene already runs heavy. A
  screenshot from gameplay distance is a bonus, not the verification — on dense
  levels the capture never flushes, so ask the user to confirm the look instead
  of retrying it (see `niagara_workflow.md`).

## Runtime triggering

These tools author and place; triggering in-game is the **VFX Spawner
device** (or activating the placed system) wired via Verse — see the uefn and
verse skills for device wiring.
