# Changelog

## 0.2.0

- Add owner/chain/contract/salt task namespaces and final-only v2 receipts with EIP-712 domain version 2.
- Rebuild and compare Solidity ABI and both bytecodes using pinned solc-js; retain v1 artifacts.
- Add installed `cluetide-release verify`, explicit deployment trust, v2 schemas and shared Python/TypeScript vectors.
- Add one-command loopback Anvil environment, durable local publisher, public test roles and real Safe 1.4.1 reviewer.
- Add exact Safe transaction validation, signature exchange and block-anchored ERC-1271 feedback.
- Make the historical three-version acceptance case available without a wallet, with byte-preserved downloads.
- Add contract fuzz/invariants, recovery and tamper tests, installed wheel/sdist checks, browser workflows and release documentation.

Real-network v2 deployment and production write migration remain separate operational steps.
