# Installation and configuration

## Install and run

Use Python 3.12 and Node.js 24:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cd frontend
npm ci
npm test
npm run build
cd ..
.venv/bin/python -m uvicorn cluetide.release_server:app --host 127.0.0.1 --port 8787
```

On Windows use `.venv/Scripts/python.exe` and `./scripts/run-local.ps1`. The browser entry is `/`; `bot.html` retains the service-backed workspace. Development uses port 5177 and proxies the API to 8787. See [Codespaces setup](../.devcontainer/README.md).

## Configuration and evidence

- `CLUETIDE_DATA_DIR`: private persistent runtime root, default `local-data`.
- `CLUETIDE_RELEASE_CONTRACT`: verified deployed witness contract.
- `CLUETIDE_PUBLIC_ORIGIN`: exact HTTPS service origin.
- `CLUETIDE_FRONTEND_ORIGINS`: allowed browser origins; the Vercel API permits `https://cluetide.vercel.app`; the earlier service permits `https://hnnuyuxuan.github.io`.

The browser pins the BOT chain, witness bytecode, contract, target and receipt signer. The operator retains the private signer and backups across upgrades. Source exports contain no private runtime state.

Package writes on the service-created workflow require its creator's task capability. Public `POST /api/releases/imports` independently checks confirmed chain roles and commitments for each immutable version. The Agent requires `--public` for writes to a remote service. Original artifacts retain UTF-8 BOM and CRLF; strict package checks reject duplicate JSON keys, unsafe ZIP members, inconsistent copies and excessive expansion. Artifacts are at most 32 KiB; complete packages are at most 4 MiB, and version/import requests at most 512 KiB.

`cluetide.acceptance-bundle.v1` carries original versions, raw receipt bytes, downloaded artifact bytes, transaction references and timestamped observations. Imported historical confirmations are observations, not a new chain check. Browser evidence persists in a separate IndexedDB store; export it before clearing local storage.
