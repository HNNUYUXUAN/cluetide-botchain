# Contributing

Use Python 3.12 and the locked Node/Foundry toolchain. Begin with `python scripts/demo.py` or follow the explicit checks in README. Keep protocol v1 compatibility isolated from v2. Preserve evidence originals, deployed v1 source/ABI/artifacts, and third-party license notices.

Changes to authorization or signing require negative tests: wrong role, version, digest, nonce, deployment, replay and recovery. Update shared vectors and schemas when the wire format changes. Run the compiler rebuild comparison, Python and frontend tests, Foundry tests and installed-package verification. Real Safe tests use an explicitly supplied loopback Anvil RPC. Never use a real wallet for automated tests.

A pull request should explain the resulting behavior, relevant trust assumptions and actual checks. Include screenshots for visible changes. Keep generated caches, process state, credentials and private keys out of Git. Report security issues as described in SECURITY.md.
