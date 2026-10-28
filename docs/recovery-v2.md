# Operation and recovery

`python scripts/demo.py` owns only the processes it starts. Process IDs and selected ports are recorded in `.local-demo/<name>/processes.json`; server and Anvil logs are in the same directory. The launcher never kills an occupied port. Use a different port pair for another checkout.

Anvil periodically persists state to `anvil.json`. The fixture records witness/Safe deployments and the publisher profile. Retain the complete directory together. A saved fixture against a different chain or missing runtime is rejected. Start with a new `--data .local-demo/new-name` directory and unused ports for an independent chain.

To stop, inspect the saved process IDs and verify their executable and command line match this checkout before terminating them using your OS process manager. For archival, stop the server and Anvil first, then copy the complete state directory. These files are ignored by Git. They contain public demonstration identities and local operational state, not production credentials.

## Publisher crash boundaries

1. The service validates a canonical consumed grant and saves the attempt.
2. It writes immutable artifact bytes and a marker into the attempt destination.
3. It durably records `switching_target`, then atomically updates the target pointer.
4. It reads the target and compares marker plus byte hash.
5. It saves the signed final receipt before the completed attempt state.

A failure before touching the target can produce a failed receipt. A failure during target switching or signing enters `reconciliation_required`. Recovery checks the existing target or saved receipt; it never blindly repeats publication. The same task, version, attempt ID and authorization transaction are required on retry. A different request cannot take over the attempt. Saved receipt and target bytes permit recovery after a crash between receipt persistence and state update.

The local UI’s **Publish / recover** action uses the existing consumed attempt. Refresh restores task, version, on-chain decisions and signature progress. Changing the test-role selector changes available controls; the witness still enforces actual transaction senders.

Cross-device recovery requires the original task/version bytes, consumed transaction hash and the durable publisher state, or access to the same publisher. Copy the whole state directory while stopped. A portable acceptance ZIP supports independent verification; it does not grant publication authority or reconstruct missing mutable target state.

If RPC validation is unavailable, retain the request and retry the read. If a transaction was sent but no verified result is recorded, inspect the chain and transaction journal before preparing another operation. The demo journal records sending/pending/verified stages for direct witness calls. Production deployments should additionally use a persistent transaction outbox and multi-RPC reconciliation.
