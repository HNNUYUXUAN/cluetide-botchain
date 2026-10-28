# Deployment and migration

## Release components

v0.2.0 ships the independent verifier, Witness v2 source/ABI/creation and runtime bytecode, portable acceptance samples, a local Anvil/Safe environment and static historical-case presentation. The existing BOT Mainnet v1 contract remains `0xca71b77708674f5f2407c0ad4e599eaf5eb07281`; its source and artifact remain separate.

Build both artifacts with `npm ci && npm run compile:check`. Compiler settings are solc-js 0.8.30, Paris, optimizer 200. The script compares regenerated ABI and both bytecodes, and verifies packaged Python resources. `configs/historical-bot677.json` generates historical frontend/Python configuration. A v2 deployment profile is generated after local deployment and served to the browser from the same server configuration.

For static presentation, run `npm ci && npm run build` in `frontend`, then deploy `frontend/dist`. The production build excludes the local test adapter. Its historical case download and offline verifier stay compatible with v1. `frontend/dist-local` is the local-chain demonstration build and is served only by the loopback demo server.

## Real-network rollout checklist

This is a separate operator-controlled step; local development and release verification do not need real-wallet access.

1. Select the network, RPC providers, finality policy and a separately managed EOA receipt signer. Protect production signing material outside the source checkout and demo configuration.
2. Review and deploy the independent Witness v2 artifact with a real owner wallet. Do not overwrite v1 source, ABI or deployment records.
3. Compare deployed runtime bytes against the release artifact. Record deployment transaction, block hash, chain ID, contract address, runtime SHA-256, signer and confirmation policy in an authenticated deployment profile.
4. Provision the production publisher and target policy. The v2 release demonstrates durable file storage; complete and verify production database activation before switching write traffic. The established PostgreSQL v1 path remains covered by integration CI.
5. Configure and verify an appropriate Safe 1.4.1 deployment, owners, threshold and fallback handler. Exercise the supported reviewer operations and independently verify ERC-1271 observations.
6. Generate frontend configuration from the approved profile, validate a complete acceptance case, document trust-profile distribution and recovery procedures, and only then activate production writes.
7. Keep legacy verification routes and evidence available. New tasks carry v2 salt and deployment context; old tasks remain v1.

See the release validation record for actual publication and static-deployment status. Missing hosting access should be resolved by deploying the provided static artifact; it does not require a new token or wallet during development.
