# Upstream provenance

This repository is a working fork of **OtoStoksBot Pro v5** for the Steam game
*Screen Stocks* (App ID `4356780`).

## Where this source came from

| | |
|---|---|
| Upstream repo | https://github.com/SavageisSavage/OtoStoks |
| Version | `v5` (released 2026-11-09) |
| Source archive used | `OtoStoksBot-LINUX.tar.gz` from the `v5` GitHub Release |
| Original author | `SavageisSavage` |

**Do not use `github.com/SavageisSavage/OtoStoks/archive/refs/tags/v5.zip`.**

That tag archive contains only 10 files at the repo root (`main.py`, icons,
`model.onnx`, `otostoks_proto.py`, packaging scripts). It is missing every module
that `main.py` imports:

```
core.config        core.state        core.notifications
api.server         engine.*          ui.dashboard
```

Running it fails immediately on `ImportError`. The tag archive is not the program.

The release tarball is the only published artifact that contains the real
engine. It ships ~6,000 lines of Python across `api/ core/ engine/ ui/ schemas/`
plus the two prebuilt BepInEx bridge DLLs.

## Binary files carried from upstream

These are checked in unchanged and have **no source in any release**:

- `OtoStoksBridge.dll` — BepInEx/Harmony patch assembly. Namespace
  `ScreenStocksLocalBridge.Server.LocalBridgeServer`; hosts an in-process
  `HttpListener` with WebSocket support, exposes `/snapshot` and `/trade`.
- `ScreenStocksLocalBridge.dll` — byte-identical duplicate of the above.
- `model.onnx` — 16-feature LightGBM model, 539 KB.

Rebuilding or replacing the bridge DLL means writing new C# against the game's
assemblies; the existing one can only be used as-is.

## Licensing

Upstream has **no `LICENSE` file**, which under default copyright means all
rights are reserved. Keep this fork private unless the author grants a license.

## Re-syncing from a future upstream release

```bash
curl -sL -o upstream.tar.gz \
  https://github.com/SavageisSavage/OtoStoks/releases/download/<TAG>/OtoStoksBot-LINUX.tar.gz
mkdir -p /tmp/upstream && tar -xzf upstream.tar.gz -C /tmp/upstream
diff -ru /tmp/upstream/OtoStoksBot_Linux . -x .git -x __pycache__
```
