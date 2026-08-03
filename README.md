# UEFN Niagara

Niagara systems — discover, assemble emitters/modules/renderers, create particle
meshes, place, drive parameters. Bundles the vfx skill.

Desktop plugin for [UEFN-Ducky](https://github.com/UEFN-Ducky/UEFN-Ducky) (`vfx`).
Install or update from **Settings → Store** in the app — do not install from a zip by hand.

## Build

```bash
py scripts/build_zip.py
```

Writes `deploy/vfx-<version>.ducky-plugin.zip` from `plugin.json` (scripts/ and
deploy/ are not packed). Ship it with `./release/publish_plugin.sh vfx`, then
update from **Settings → Store**.
