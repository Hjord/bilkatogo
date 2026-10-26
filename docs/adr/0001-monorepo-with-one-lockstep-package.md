# Monorepo with one lockstep-versioned package

The library, CLI, Home Assistant integration and a future MCP server live in one repo, so a change to the order model and the code that consumes it lands in one commit. The library ships as a single PyPI package `bilkatogo` with `[cli]` and `[mcp]` extras (core depends on httpx only, so Home Assistant never pulls in click), and every `vX.Y.Z` GitHub release publishes `bilkatogo==X.Y.Z` to PyPI and is the Marketplace version of the integration, whose `manifest.json` pins that same version.

## Considered Options

- **Separate library and integration repos** (the `aula` / `hass-aula` pattern): rejected because every model change becomes two PRs plus a release in between.
- **Integration source under `src/`**: not possible. The HACS / Home Assistant Marketplace reads `custom_components/<domain>/manifest.json` from the repository tree, so `custom_components/bilkatogo/` must sit at the repo root. A stub manifest plus `zip_release` would work but means keeping two manifests in sync.
- **Several PyPI packages in a uv workspace**: rejected as three release flows for no current benefit; revisit if the CLI or MCP server needs its own release cadence.

## Consequences

A Home Assistant-only change still publishes a library release with no changes. That is accepted.
