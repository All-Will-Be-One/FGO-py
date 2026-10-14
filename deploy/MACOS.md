# Headless macOS / agent use

Install Homebrew `adb`, `uv`, and `cbc`, then `bash deploy/macos.sh install`.
This uses Python 3.12 and requirements-headless.txt; no Qt UI is required.
Set the `device` field in the local `FGO-py/fgoConfig.json` to the USB serial.
Keep `farming: false` (default) until explicitly wanted.

```sh
bash deploy/macos.sh check         # JSON OCR / foreground game / screenshot report
bash deploy/macos.sh cli <<'EOF'
connect -l
exit
EOF
```

To interact, open the game on the phone, then send `connect` followed by desired
commands to the CLI. `help` and `help COMMAND` document its commands. Connection
automatically selects JP/CN/NA/TW by the foreground game package. The resumed
activity is used before the legacy activity-list fallback to avoid selecting a
background app on HyperOS.

The launcher selects ADBCAP to avoid installing the optional Yosemite screenshot
APK. Touch still uses Airtest's supported touch service. The diagnostic initializes
that service but never sends a touch or starts a game task. Its existence alone
does not verify actual game input or battles.

FGO expects a 16:9 game layout. Native wide-screen output can be captured and cropped
but may not match recognition templates. Use upstream CLI `169 invoke` before game
login if needed, then reconnect; `169 revoke` restores the native resolution.
These operations change the phone display, and are not performed by the check.
Both OAS and FGO share the same device: run only one task executor at a time.

`pulp` is pinned below 4 to retain the bundled `PULP_CBC_CMD` fallback.
The solver prefers `cbc` on PATH (`brew install cbc`), which provides native
Apple Silicon support instead of PuLP's Intel-only bundled macOS binary.
Game login and battle behavior are separate from host installation checks.
