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
2. Bump `version` and set `min_app_version` to `1.2.356` or newer.
3. Publish, then check the download with the start-up license check (signature, id and version, compiled, team access), not only the signature.
4. The Store must hold the version back from apps older than `min_app_version`. Until it does, older apps install a build they can't run.

Remove this section once a compiled version is live.

## License

MIT. Copyright (c) 2026 Mindful Path Company, LLC. See [LICENSE](LICENSE).
