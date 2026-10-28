# Portable v2 examples

These samples were produced by actual local Anvil transactions using `scripts/demo_scenario.py`. Each contains three versions, two corrections, exact approval, consumption and a signed final receipt.

- `eoa-acceptance-v3.zip`: individual reviewer and EOA feedback.
- `safe-acceptance-v3.zip`: official Safe 1.4.1 reviewer, threshold two, ERC-1271 feedback observations.
- `deployment.json`: the separately supplied local trust profile for these samples. Review it independently before trusting evidence.
- `tampered-acceptance.zip`: a changed byte in the delivered artifact; verification must fail.
- `shared-vectors.json`: task derivation, raw byte hashes and typed receipt shared by Python and TypeScript tests.

The historic local chain is not a persistent public RPC. Offline results keep contract-account signatures marked as requiring chain state. Run the demo to create a fresh deployment and fresh samples for online verification.
