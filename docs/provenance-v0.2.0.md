# Source and evidence provenance

The maintained public repository is [HNNUYUXUAN/cluetide-botchain](https://github.com/HNNUYUXUAN/cluetide-botchain). The implementation baseline for this release is `61fad4a4d21c2721957ddbc7d6d4a2a4f24030cc`.

Historical deployed source was identified as revision `1655aa887fadf30bbdf8a0ce9dfbe02c2b0a1609` in the predecessor repository. Its file-level mapping is retained in `provenance/deployed-source-manifest-1655aa8.json`; `source-manifest.json` retains the original consolidation record. These are historical provenance records, not assertions that current v0.2.0 files have those hashes.

`evidence/complete-mainnet/acceptance-v3.zip`, historical source manifests and the v1 contract artifact retain their original bytes. The frontend’s flagship task and receipt are copied directly from that ZIP, and `frontend/public/evidence/acceptance-v3.zip` is a byte-identical download copy. The package records observation time `2026-10-14T05:16:22.697Z`; an offline check does not refresh that observation.

New v2 examples in `fixtures/v2` were created on local Anvil chain 31337 with public test accounts. Their addresses and block observations describe that local run. Replaying `scripts/demo_scenario.py` creates a new local case and deployment profile; transaction hashes and timestamps naturally differ.
