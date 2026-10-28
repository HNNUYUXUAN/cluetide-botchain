# v0.2.0 validation record

Local validation date: 28 October 2026. Baseline: `61fad4a4d21c2721957ddbc7d6d4a2a4f24030cc`.

| Check | Observed result |
| --- | --- |
| Python regression and v2 verifier/schema tests | 282 passed; optional PostgreSQL and explicit-Anvil tests run separately |
| Real Safe integration on Anvil | 4 passed: threshold, duplicate signatures, proposal mutation, inner failure, ERC-1271, RPC interruption and owner rotation |
| Frontend tests | 77 passed, including shared Python/TypeScript protocol vectors |
| Browser EOA and Safe workflows | 2 passed; refresh, repeated publication, offline/online checks, download, tamper rejection and mobile layout |
| Foundry 1.8.6 | 4 passed; 128 invariant runs / 4,096 calls; 256 fuzz runs per property |
| Solidity reproduction | v1 and v2 ABI, creation bytecode and runtime bytecode match pinned solc-js output |
| Installed distributions | Wheel and sdist installed in independent temporary environments; v1/v2/Safe verification and tamper rejection pass |
| Python static error checks | Ruff E9/F63/F7/F82 passed |
| Static frontend | Production build succeeds and excludes the local test adapter |
| Historical artifacts | Original v1 source/artifact, mainnet evidence and provenance manifests unchanged |

Foundry seed: `0x434c554554494445`. Reproduce with `python scripts/toolchain.py forge test -vv`; failing sequences are retained by Foundry under ignored `cache/`. Gas measurements are in `.gas-snapshot` and reflect this pinned configuration.

The GitHub workflow additionally provides PostgreSQL integration, Linux installed-package validation, local browser checks and Solidity static analysis. Its run status and release assets are linked from the published PR/release. Production v2 deployment and write migration are separate steps documented in `docs/deployment-v2.md`.
