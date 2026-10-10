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

## Next release: ship compiled

This plugin still ships its Python source on the Store. Its next release has to ship compiled and signed, the way Ducky Account and Roguelike do:

1. Give `scripts/release.py` and `scripts/build_zip.py` the compiled build from `uefn-plugin-account` (`build_compiled_zip`, upload by ticket, `--plain` only as an escape hatch).
2. Bump `version` and set `min_app_version` to `1.2.357` or newer (the Store keeps older apps from seeing it).
3. Build only with the UEFN Ducky build engine (UEFN-Ducky `68f4abc` or newer), which compiles and links for baseline x86-64, never with Nuitka or zig run by hand. Before publishing, check the `.pyd` runs on every CPU: `objdump -d <file>.pyd | grep -cE '%(y|z)mm'` must print `0`. Account 1.0.50 and Roguelike 1.12.44 carried the build PC's AVX-512 and stopped Ducky opening on every CPU without it.
4. Publish, then check the download with the start-up license check (signature, id and version, compiled, team access), not only the signature.
5. A compiled build can't `importlib.reload` its own modules (Python raises SystemError), so reload only when running from source. Before publishing, install the source and compiled zips into a throwaway Ducky and check they register the same panel calls, tools and workflow nodes, and that those calls still work after the plugin reloads.

Remove this section once a compiled version is live.

## License

MIT. Copyright (c) 2026 Mindful Path Company, LLC. See [LICENSE](LICENSE).
