"""Real Safe integration. Enable explicitly with CLUETIDE_ANVIL_RPC on loopback."""

import copy
import os
from pathlib import Path
import pytest
from cluetide.local_demo import LocalDemo
from cluetide.review_v2 import verify_feedback
from cluetide.verification import verify

RPC = os.environ.get("CLUETIDE_ANVIL_RPC")
pytestmark = pytest.mark.skipif(not RPC, reason="Explicit isolated Anvil RPC required")


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    import sys

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    from toolchain import node_tools

    return LocalDemo(
        root, tmp_path_factory.mktemp("safe-v2"), RPC, str(node_tools()[0])
    )


def prepare(demo):
    demo.command("create", {"mode": "safe"})
    demo.command("propose", {"artifact": "<h1>Safe review fixture</h1>"})
    return demo.command("approve", {})


def test_threshold_unique_signers_and_exact_import(demo):
    prepare(demo)
    first = demo.command("safe_sign", {"owner": 5})
    assert len(first["signatures"]) == 1
    again = demo.command("safe_sign", {"owner": 5})
    assert len(again["signatures"]) == 1
    with pytest.raises(ValueError):
        demo.command("safe_execute", {})
    with pytest.raises(ValueError):
        demo.safe_call("execute", proposal=again)
    for field, value in [
        ("nonce", 999),
        ("to", "0x" + "11" * 20),
        ("data", "0x"),
        ("safe", "0x" + "11" * 20),
        ("safeTxGas", "123"),
    ]:
        bad = copy.deepcopy(again)
        bad[field] = value
        with pytest.raises(ValueError):
            demo.command("safe_import", {"proposal": bad})
    bad = copy.deepcopy(again)
    bad["signatures"] *= 2
    with pytest.raises(ValueError):
        demo.command("safe_import", {"proposal": bad})
    demo.command("safe_sign", {"owner": 6})
    result = demo.command("safe_execute", {})
    assert result["status"] == "verified"
    demo.command("revoke", {})
    demo.command("safe_sign", {"owner": 5})
    demo.command("safe_sign", {"owner": 7})
    assert demo.command("safe_execute", {})["status"] == "verified"


def test_outer_success_inner_failure_is_rejected(demo):
    prepare(demo)
    demo.command("safe_sign", {"owner": 5})
    proposal = demo.command("safe_sign", {"owner": 6})
    demo.command("safe_execute", {})
    # Re-approving a decided version fails internally. Nonzero safeTxGas allows Safe to return ExecutionFailure.
    proposal.pop("safe_tx_hash", None)
    proposal["nonce"] = demo.safe_call("inspect")["nonce"]
    proposal["safeTxGas"] = "100000"
    proposal["signatures"] = []
    proposal = demo.safe_call("sign", proposal=proposal, owner=5)
    proposal = demo.safe_call("sign", proposal=proposal, owner=6)
    result = demo.safe_call("execute", proposal=proposal)
    assert result["status"] == "success"
    task = demo.current()
    with pytest.raises(ValueError, match="did not succeed"):
        demo.chain.verify_action(
            "approve",
            task,
            task["versions"][-1],
            result["transaction_hash"],
            safe_nonce=proposal["nonce"],
        )


def test_1271_observations_and_rpc_interruptions(demo, monkeypatch):
    prepare(demo)
    demo.command("request_correction", {})
    demo.command("safe_sign", {"owner": 5})
    demo.command("safe_sign", {"owner": 6})
    demo.command("safe_execute", {})
    record = demo.command("feedback", {})
    assert record["verification"]["status"] == "verified"
    assert (
        verify_feedback(record, demo.current(), demo.deployment)["status"]
        == "requires_chain_state"
    )
    bad = copy.deepcopy(record)
    bad["signature"] = "0x" + "00" * 65
    with pytest.raises(Exception):
        verify_feedback(bad, demo.current(), demo.deployment, chain=demo.chain)
    bad = copy.deepcopy(record)
    bad["verification"]["block_hash"] = "0x" + "11" * 32
    with pytest.raises(ValueError):
        verify_feedback(bad, demo.current(), demo.deployment, chain=demo.chain)
    original = demo.chain.w3.eth.call

    def wrong_magic(tx, *args, **kwargs):
        if str(tx.get("data", "")).startswith("0x1626ba7e"):
            return bytes(32)
        return original(tx, *args, **kwargs)

    monkeypatch.setattr(demo.chain.w3.eth, "call", wrong_magic)
    with pytest.raises(ValueError, match="ERC-1271 rejected"):
        verify_feedback(record, demo.current(), demo.deployment, chain=demo.chain)
    monkeypatch.setattr(
        demo.chain.w3.eth,
        "call",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("RPC offline")),
    )
    with pytest.raises(ConnectionError):
        verify_feedback(record, demo.current(), demo.deployment, chain=demo.chain)


def test_safe_owner_change_preserves_historical_observation(demo):
    from eth_abi import encode
    from eth_utils import keccak
    from cluetide.local_demo import test_account

    prepare(demo)
    demo.command("request_correction", {})
    demo.command("safe_sign", {"owner": 5})
    demo.command("safe_sign", {"owner": 6})
    demo.command("safe_execute", {})
    record = demo.command("feedback", {})
    task = demo.current()
    snapshot = demo.w3.provider.make_request("evm_snapshot", [])["result"]
    try:
        # Exercise a real Safe owner rotation outside the supported reviewer API.
        data = keccak(text="swapOwner(address,address,address)")[:4] + encode(
            ["address", "address", "address"],
            ["0x" + "00" * 19 + "01", test_account(5).address, test_account(8).address],
        )
        proposal = {
            "to": demo.fixture["safe"]["address"],
            "data": "0x" + data.hex(),
            "nonce": demo.safe_call("inspect")["nonce"],
            "safeTxGas": "0",
            "signatures": [],
        }
        proposal = demo.safe_call("sign", proposal=proposal, owner=5)
        proposal = demo.safe_call("sign", proposal=proposal, owner=6)
        demo.safe_call("execute", proposal=proposal)
        assert test_account(5).address.lower() not in [
            x.lower() for x in demo.safe_call("inspect")["owners"]
        ]
        assert (
            verify_feedback(record, task, demo.deployment, chain=demo.chain)["status"]
            == "verified"
        )
        current = copy.deepcopy(record)
        block = demo.w3.eth.get_block("latest")
        current["verification"].update(
            block_number=block.number, block_hash=block.hash.to_0x_hex()
        )
        with pytest.raises(Exception):
            verify_feedback(current, task, demo.deployment, chain=demo.chain)
    finally:
        assert demo.w3.provider.make_request("evm_revert", [snapshot])["result"]
