"""Canonical v2 witness reads and exact direct/Safe transaction verification."""

from __future__ import annotations
import json
from importlib.resources import files
from pathlib import Path
from eth_abi import decode, encode
from eth_utils import keccak
from web3 import Web3
from .deployment import Deployment, sha256
from .verification import require


def artifact_v2():
    resource = files("cluetide").joinpath("resources/ClueTideReleaseWitnessV2.json")
    if resource.is_file():
        return json.loads(resource.read_text(encoding="utf-8"))
    return json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "contracts/artifacts/ClueTideReleaseWitnessV2.json"
        ).read_text(encoding="utf-8")
    )


def binary(value):
    return bytes.fromhex(value.removeprefix("0x"))


def hex_value(value):
    return "0x" + bytes(value).hex()


class WitnessChain:
    def __init__(self, deployment: Deployment, web3=None):
        self.deployment = deployment
        self.w3 = web3 or Web3(
            Web3.HTTPProvider(deployment.rpc_url, request_kwargs={"timeout": 15})
        )
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(deployment.contract_address),
            abi=artifact_v2()["abi"],
        )

    def identity(self, block="latest"):
        require(
            self.w3.eth.chain_id == self.deployment.chain_id,
            "RPC returned a different chain",
        )
        code = bytes(
            self.w3.eth.get_code(self.contract.address, block_identifier=block)
        )
        require(
            sha256(code) == self.deployment.runtime_sha256
            and hex_value(code) == artifact_v2()["deployedBytecode"],
            "Witness runtime differs from trusted deployment",
        )

    def task(self, task_id, block="latest"):
        return self.contract.functions.getTask(binary(task_id)).call(
            block_identifier=block
        )

    def version(self, task_id, version_id, block="latest"):
        return self.contract.functions.getVersion(binary(task_id), version_id).call(
            block_identifier=block
        )

    def attempt(self, task_id, attempt_id, block="latest"):
        return self.contract.functions.getAttempt(binary(task_id), attempt_id).call(
            block_identifier=block
        )

    def function(self, action, task, version=None, envelope=None):
        t = binary(task["task_id"])
        if action == "create_task":
            return self.contract.functions.createTask(
                t,
                binary(task["salt"]),
                *[
                    Web3.to_checksum_address(task[k])
                    for k in ("proposer", "reviewer", "executor", "receipt_signer")
                ],
                binary(task["target_id"]),
            )
        if action == "propose_version":
            return self.contract.functions.proposeVersion(
                t,
                version["parent_version_id"],
                binary(version["manifest_hash"]),
                binary(version["artifact_hash"]),
                version["expires_at"],
            )
        if action == "approve":
            return self.contract.functions.approve(
                t,
                version["version_id"],
                binary(version["manifest_hash"]),
                binary(version["artifact_hash"]),
                version["expires_at"],
            )
        if action in ("revoke", "request_correction"):
            return getattr(
                self.contract.functions,
                "revoke" if action == "revoke" else "requestCorrection",
            )(t, version["version_id"])
        if action == "consume":
            return self.contract.functions.consume(
                t,
                version["version_id"],
                binary(version["manifest_hash"]),
                binary(version["artifact_hash"]),
            )
        if action == "record_receipt":
            receipt = envelope["receipt"]
            return self.contract.functions.recordReceipt(
                t,
                int(receipt["attempt_id"]),
                binary(envelope["receipt_hash"]),
                1 if receipt["status"] == "succeeded" else 2,
                binary(envelope["signature"]),
            )
        raise ValueError("Unsupported witness action")

    def verify_action(
        self, action, task, version, tx_hash, *, envelope=None, safe_nonce=None
    ):
        self.identity()
        tx = self.w3.eth.get_transaction(tx_hash)
        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        require(receipt["status"] == 1, "Transaction reverted")
        number = receipt["blockNumber"]
        anchor = bytes(receipt["blockHash"])
        require(
            bytes(tx["blockHash"]) == anchor and tx["blockNumber"] == number,
            "Transaction block differs",
        )
        require(
            bytes(self.w3.eth.get_block(number)["hash"]) == anchor,
            "Transaction was reorganized",
        )
        require(
            self.w3.eth.block_number - number + 1 >= self.deployment.confirmations,
            "Transaction is awaiting confirmations",
        )
        self.identity(number)
        expected = binary(
            self.function(action, task, version, envelope)._encode_transaction_data()
        )
        role = {
            "create_task": "owner",
            "propose_version": "proposer",
            "approve": "reviewer",
            "request_correction": "reviewer",
            "revoke": "reviewer",
            "consume": "executor",
        }.get(action)
        require(int(tx["value"]) == 0, "Witness transactions cannot transfer value")
        if safe_nonce is None:
            require(
                tx["to"].lower() == self.deployment.contract_address
                and bytes(tx["input"]) == expected,
                "Transaction target or calldata differs",
            )
            if role:
                require(
                    tx["from"].lower() == task[role],
                    "Transaction sender differs from role",
                )
        else:
            require(
                action in ("approve", "request_correction", "revoke"),
                "Safe adapter supports reviewer operations",
            )
            require(
                type(safe_nonce) is int
                and safe_nonce >= 0
                and tx["to"].lower() == task["reviewer"],
                "Invalid Safe execution",
            )
            types = [
                "address",
                "uint256",
                "bytes",
                "uint8",
                "uint256",
                "uint256",
                "uint256",
                "address",
                "address",
                "bytes",
            ]
            require(
                bytes(tx["input"])[:4]
                == keccak(text="execTransaction(" + ",".join(types) + ")")[:4],
                "Unsupported Safe entrypoint",
            )
            args = decode(types, bytes(tx["input"])[4:])
            require(
                bytes(tx["input"])[4:] == encode(types, args),
                "Safe calldata is not canonical",
            )
            require(
                args[0].lower() == self.deployment.contract_address
                and args[1] == 0
                and args[2] == expected
                and args[3] == 0,
                "Safe inner action differs",
            )
            require(
                args[6] == 0 and int(args[7], 16) == 0 and int(args[8], 16) == 0,
                "Safe refund policy differs",
            )
            hash_types = [
                "address",
                "uint256",
                "bytes",
                "uint8",
                "uint256",
                "uint256",
                "uint256",
                "address",
                "address",
                "uint256",
            ]
            call = keccak(text="getTransactionHash(" + ",".join(hash_types) + ")")[
                :4
            ] + encode(hash_types, [*args[:9], safe_nonce])
            safe_hash = bytes(
                self.w3.eth.call(
                    {
                        "to": Web3.to_checksum_address(task["reviewer"]),
                        "data": hex_value(call),
                    },
                    block_identifier=number,
                )
            )
            topic = keccak(text="ExecutionSuccess(bytes32,uint256)")
            matches = [
                log
                for log in receipt["logs"]
                if log["address"].lower() == task["reviewer"]
                and len(log["topics"]) == 2
                and bytes(log["topics"][0]) == topic
                and bytes(log["topics"][1]) == safe_hash
            ]
            require(len(matches) == 1, "Safe execution did not succeed")
        chain_task = self.task(task["task_id"], number)
        require(
            [a.lower() for a in chain_task[:5]]
            == [
                task[k]
                for k in ("owner", "proposer", "reviewer", "executor", "receipt_signer")
            ]
            and hex_value(chain_task[5]) == task["target_id"],
            "On-chain roles or target differ",
        )
        if version:
            state = self.version(task["task_id"], version["version_id"], number)
            require(
                state[0] == version["version_id"]
                and hex_value(state[2]) == version["manifest_hash"]
                and hex_value(state[3]) == version["artifact_hash"]
                and state[4] == version["expires_at"],
                "On-chain version differs",
            )
            decision = {
                "approve": 1,
                "revoke": 2,
                "request_correction": 3,
                "consume": 4,
            }.get(action)
            if decision is not None:
                require(state[5] == decision, "On-chain decision differs")
            event_name = {
                "approve": "DecisionRecorded",
                "revoke": "DecisionRecorded",
                "request_correction": "DecisionRecorded",
                "propose_version": "VersionProposed",
                "consume": "ApprovalConsumed",
            }.get(action)
            if event_name:
                from web3.logs import DISCARD

                events = getattr(self.contract.events, event_name)().process_receipt(
                    receipt, errors=DISCARD
                )
                require(
                    any(
                        hex_value(e["args"]["taskId"]) == task["task_id"]
                        and e["args"]["versionId"] == version["version_id"]
                        for e in events
                    ),
                    "Witness action event missing",
                )
        require(
            bytes(self.w3.eth.get_block(number)["hash"]) == anchor,
            "Canonical block changed during verification",
        )
        return {
            "status": "verified",
            "transaction_hash": hex_value(receipt["transactionHash"]),
            "block_number": number,
            "block_hash": hex_value(anchor),
            "confirmations": self.w3.eth.block_number - number + 1,
            "gas_used": receipt["gasUsed"],
        }

    def verify_grant(self, task, version, attempt_id, tx_hash, *, allow_recorded=False):
        proof = self.verify_action("consume", task, version, tx_hash)
        attempt = self.attempt(task["task_id"], int(attempt_id))
        state = self.version(task["task_id"], version["version_id"])
        require(
            attempt[0] == int(attempt_id)
            and attempt[1] == version["version_id"]
            and state[7] == int(attempt_id)
            and state[5] == 4,
            "Consumed grant differs",
        )
        require(
            allow_recorded or attempt[4] == 0, "Execution already has a final receipt"
        )
        return {
            **proof,
            **self.deployment.context(),
            "task_id": task["task_id"],
            "version_id": version["version_id"],
            "attempt_id": str(attempt_id),
            "manifest_hash": version["manifest_hash"],
            "artifact_hash": version["artifact_hash"],
            "executor": task["executor"],
            "receipt_signer": task["receipt_signer"],
            "target_id": task["target_id"],
            "authorization_tx": tx_hash,
        }
