"""Independent, bounded evidence verification. Network access is always explicit."""

from __future__ import annotations
import io
import zipfile
from datetime import datetime
from pathlib import Path
from eth_account import Account
from eth_account.messages import encode_typed_data
from .bundles import canonical_json_bytes
from .deployment import Deployment, address, commitment, sha256
from .release_exchange import read_zip, strict_json, MAX_PACKAGE_BYTES

HALF_ORDER = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0


def require(condition, message):
    if not condition:
        raise ValueError(message)


def typed_receipt(receipt, receipt_hash):
    require(
        receipt["status"] in ("succeeded", "failed"),
        "A final receipt requires success or failure",
    )
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Receipt": [
                {"name": "taskId", "type": "bytes32"},
                {"name": "versionId", "type": "uint256"},
                {"name": "attemptId", "type": "uint256"},
                {"name": "receiptHash", "type": "bytes32"},
                {"name": "result", "type": "uint8"},
            ],
        },
        "primaryType": "Receipt",
        "domain": {
            "name": "ClueTideReleaseWitness",
            "version": "2",
            "chainId": receipt["chain_id"],
            "verifyingContract": receipt["contract_address"],
        },
        "message": {
            "taskId": receipt["task_id"],
            "versionId": receipt["version_id"],
            "attemptId": int(receipt["attempt_id"]),
            "receiptHash": receipt_hash,
            "result": 1 if receipt["status"] == "succeeded" else 2,
        },
    }


def recover_eoa(typed, signature):
    require(
        isinstance(signature, str) and signature.startswith("0x"), "Invalid signature"
    )
    raw = bytes.fromhex(signature[2:])
    require(
        len(raw) == 65
        and raw[64] in (27, 28)
        and 0 < int.from_bytes(raw[32:64], "big") <= HALF_ORDER,
        "Invalid canonical ECDSA signature",
    )
    return Account.recover_message(
        encode_typed_data(full_message=typed), signature=raw
    ).lower()


def verify_task(task, deployment: Deployment):
    require(task["schema"] == "cluetide.release-task.v2", "Unsupported task schema")
    require(
        task["deployment"] == deployment.context(),
        "Task deployment differs from the trusted profile",
    )
    require(
        task["task_id"] == deployment.task_id(task["owner"], task["salt"]),
        "Task identity does not match creator and salt",
    )
    require(
        task["target_id"] == deployment.target_id(task["task_id"]),
        "Task publication target differs",
    )
    require(task["target"] == deployment.target, "Task target policy differs")
    for key in ("owner", "proposer", "reviewer", "executor", "receipt_signer"):
        require(address(task[key]) == task[key], "Noncanonical task address")
    require(
        task["proposer"] != task["reviewer"], "Review and proposal roles must differ"
    )
    require(
        task["receipt_signer"] == deployment.receipt_signer, "Untrusted receipt signer"
    )
    require(
        isinstance(task["title"], str) and 0 < len(task["title"]) <= 160,
        "Invalid task title",
    )
    require(
        isinstance(task["versions"], list) and 0 <= len(task["versions"]) <= 50,
        "Invalid history length",
    )
    require(
        task["version_count"] == len(task["versions"]), "Incomplete version history"
    )
    for i, version in enumerate(task["versions"], 1):
        artifact = version["artifact_text"].encode("utf-8")
        raw = version["manifest_text"].encode("utf-8")
        manifest = strict_json(raw)
        require(
            len(artifact) <= deployment.artifact_limit and artifact,
            "Invalid artifact size",
        )
        require(
            version["version_id"] == i and version["parent_version_id"] == i - 1,
            "Version history is discontinuous",
        )
        require(
            sha256(raw) == version["manifest_hash"]
            and sha256(artifact) == version["artifact_hash"],
            "Version bytes differ",
        )
        expected = {
            "schema": "cluetide.release-manifest.v2",
            "deployment": deployment.context(),
            "task_id": task["task_id"],
            "version_id": i,
            "parent_version_id": i - 1,
            "target_id": task["target_id"],
            "operation": "publish_static",
            "policy_version": deployment.policy,
            "target": deployment.target,
            "expires_at": version["expires_at"],
            "artifact": {
                "filename": "artifact.html",
                "sha256": version["artifact_hash"],
                "bytes": len(artifact),
            },
        }
        require(
            all(manifest.get(k) == v for k, v in expected.items()),
            "Manifest differs from its task or version",
        )
        require(
            type(version["expires_at"]) is int and 0 < version["expires_at"] < 2**53,
            "Invalid deadline",
        )
        require(
            isinstance(manifest["summary"], str)
            and 0 < len(manifest["summary"]) <= 1000,
            "Invalid summary",
        )
        require(
            isinstance(manifest["test_evidence"], list)
            and 1 <= len(manifest["test_evidence"]) <= 12,
            "Invalid test evidence",
        )
        require(
            all(
                isinstance(x, str) and 0 < len(x) <= 1000
                for x in manifest["test_evidence"]
            ),
            "Invalid test evidence text",
        )
        require(
            isinstance(manifest["source_reference"], str)
            and 0 < len(manifest["source_reference"]) <= 300,
            "Invalid source reference",
        )
        if "manifest" in version:
            require(version["manifest"] == manifest, "Conflicting manifest copies")
    return task


def verify_receipt(task, version, envelope, deployment):
    receipt = envelope["receipt"]
    expected = {
        "schema": "cluetide.execution-receipt.v2",
        **deployment.context(),
        "task_id": task["task_id"],
        "version_id": version["version_id"],
        "manifest_hash": version["manifest_hash"],
        "artifact_hash": version["artifact_hash"],
        "target_id": task["target_id"],
        "executor": task["executor"],
        "receipt_signer": deployment.receipt_signer,
        "operation": "publish_static",
        "environment": "isolated-demo",
    }
    require(
        all(receipt.get(k) == v for k, v in expected.items()), "Receipt context differs"
    )
    require(
        str(int(receipt["attempt_id"])) == receipt["attempt_id"]
        and int(receipt["attempt_id"]) > 0,
        "Invalid attempt",
    )
    commitment(receipt["authorization_tx"])
    require(receipt["status"] in ("succeeded", "failed"), "Invalid final result")
    require(
        receipt["output_hash"]
        == (version["artifact_hash"] if receipt["status"] == "succeeded" else None),
        "Invalid output commitment",
    )
    digest = sha256(canonical_json_bytes(receipt))
    require(
        envelope["receipt_hash"] == digest
        and envelope["signer"] == deployment.receipt_signer
        and envelope["signature_scheme"] == "EIP-712",
        "Invalid receipt envelope",
    )
    require(
        recover_eoa(typed_receipt(receipt, digest), envelope["signature"])
        == deployment.receipt_signer,
        "Receipt signature differs",
    )
    return receipt


def pack(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    payload = output.getvalue()
    read_zip(payload)
    return payload


def acceptance_bundle(task, envelope, deployment, artifact=None, feedback=()):
    verify_task(task, deployment)
    version = task["versions"][envelope["receipt"]["version_id"] - 1]
    verify_receipt(task, version, envelope, deployment)
    entries = {
        "task.json": canonical_json_bytes(task),
        "receipt.json": canonical_json_bytes(envelope),
    }
    for item in task["versions"]:
        entries[f"versions/{item['version_id']}/manifest.json"] = item[
            "manifest_text"
        ].encode("utf-8")
        entries[f"versions/{item['version_id']}/artifact.html"] = item[
            "artifact_text"
        ].encode("utf-8")
    if artifact is not None:
        entries["published/artifact.html"] = artifact
    if feedback:
        entries["feedback.json"] = canonical_json_bytes(list(feedback))
    index = {
        "schema": "cluetide.acceptance-bundle.v2",
        "deployment": deployment.context(),
        "task_id": task["task_id"],
        "version_id": version["version_id"],
        "attempt_id": envelope["receipt"]["attempt_id"],
        "observed_at": datetime.now().astimezone().isoformat(),
        "files": [
            {"path": name, "bytes": len(data), "sha256": sha256(data)}
            for name, data in sorted(entries.items())
        ],
    }
    entries["acceptance.json"] = canonical_json_bytes(index)
    return pack(entries)


def verify(payload: bytes, *, deployment: Deployment | None = None, online=False):
    require(
        isinstance(payload, bytes) and 0 < len(payload) <= MAX_PACKAGE_BYTES,
        "Invalid package size",
    )
    entries = read_zip(payload)
    metadata = (
        strict_json(entries["acceptance.json"])
        if "acceptance.json" in entries
        else None
    )
    if not metadata or metadata.get("schema") == "cluetide.acceptance-bundle.v1":
        if metadata:
            import json
            from importlib.resources import files

            historical = json.loads(
                files("cluetide")
                .joinpath("resources/historical-bot677.json")
                .read_text(encoding="utf-8")
            )
            legacy_task = strict_json(entries["task.json"])
            require(
                legacy_task["receipt_signer"] == historical["receiptSigner"],
                "Legacy receipt signer differs from the trusted historical deployment",
            )
        from .release_exchange import verify_package

        legacy = verify_package(payload)
        return {
            **legacy,
            "verifier_version": "0.2.0",
            "checks": {
                "files": "verified",
                "eoa_signature": "verified"
                if legacy.get("receipt_signature_valid")
                else "not_applicable",
                "contract_signature": "not_applicable",
                "chain_authorization": "not_checked",
                "live_artifact": "not_checked",
            },
        }
    require(
        metadata["schema"] == "cluetide.acceptance-bundle.v2",
        "Unsupported acceptance schema",
    )
    require(
        deployment is not None,
        "A trusted deployment profile is required for v2 evidence",
    )
    require(
        metadata["deployment"] == deployment.context(), "Acceptance deployment differs"
    )
    task = verify_task(strict_json(entries["task.json"]), deployment)
    require(metadata["task_id"] == task["task_id"], "Acceptance task differs")
    version_id = metadata["version_id"]
    require(
        type(version_id) is int and 1 <= version_id <= len(task["versions"]),
        "Invalid accepted version",
    )
    version = task["versions"][version_id - 1]
    envelope = strict_json(entries["receipt.json"])
    receipt = verify_receipt(task, version, envelope, deployment)
    require(
        receipt["attempt_id"] == metadata["attempt_id"], "Acceptance attempt differs"
    )
    expected = {"task.json", "receipt.json", "acceptance.json"}
    for item in task["versions"]:
        for filename, key in (
            ("manifest.json", "manifest_text"),
            ("artifact.html", "artifact_text"),
        ):
            name = f"versions/{item['version_id']}/{filename}"
            expected.add(name)
            require(
                entries.get(name) == item[key].encode("utf-8"),
                "Conflicting original copies",
            )
    if receipt["status"] == "succeeded":
        expected.add("published/artifact.html")
        require(
            entries.get("published/artifact.html")
            == version["artifact_text"].encode("utf-8"),
            "Delivered artifact differs",
        )
    contract_signature = "not_applicable"
    if "feedback.json" in entries:
        expected.add("feedback.json")
        from .review_v2 import verify_feedback

        for record in strict_json(entries["feedback.json"]):
            verify_feedback(record, task, deployment)
            if record["signature_scheme"] == "ERC-1271":
                contract_signature = "requires_chain_state"
    require(set(entries) == expected, "Unsupported or missing evidence members")
    files = metadata["files"]
    require(
        isinstance(files, list) and len(files) == len(entries) - 1,
        "Incomplete file inventory",
    )
    names = set()
    for record in files:
        name = record["path"]
        require(
            name in expected - {"acceptance.json"} and name not in names,
            "Duplicate or unexpected file inventory",
        )
        require(
            type(record["bytes"]) is int
            and record["bytes"] == len(entries[name])
            and record["sha256"] == sha256(entries[name]),
            "File digest mismatch",
        )
        names.add(name)
    datetime.fromisoformat(metadata["observed_at"].replace("Z", "+00:00"))
    result = {
        "verifier_version": "0.2.0",
        "status": "verified",
        "scope": "offline_acceptance_integrity",
        "task_id": task["task_id"],
        "version_id": version_id,
        "attempt_id": receipt["attempt_id"],
        "receipt_signature_valid": True,
        "stored_artifact_matches": receipt["status"] == "succeeded",
        "current_chain_verified": False,
        "live_artifact_verified": False,
        "checks": {
            "files": "verified",
            "eoa_signature": "verified",
            "contract_signature": contract_signature,
            "chain_authorization": "not_checked",
            "live_artifact": "not_checked",
        },
    }
    if online:
        from .chain_v2 import WitnessChain

        chain = WitnessChain(deployment)
        try:
            chain.verify_grant(
                task,
                version,
                receipt["attempt_id"],
                receipt["authorization_tx"],
                allow_recorded=True,
            )
            attempt = chain.attempt(task["task_id"], int(receipt["attempt_id"]))
            require(
                attempt[3].hex() == envelope["receipt_hash"][2:]
                and attempt[4] == (1 if receipt["status"] == "succeeded" else 2),
                "On-chain receipt differs",
            )
            result["current_chain_verified"] = True
            result["checks"]["chain_authorization"] = "verified"
            if contract_signature == "requires_chain_state":
                for record in strict_json(entries["feedback.json"]):
                    verify_feedback(record, task, deployment, chain=chain)
                result["checks"]["contract_signature"] = "verified_at_recorded_block"
        except Exception as error:
            result["status"] = "incomplete"
            result["checks"]["chain_authorization"] = "unverified"
            result["online_error"] = type(error).__name__
    return result


def main():
    import argparse, json

    parser = argparse.ArgumentParser(prog="cluetide-release")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "verify", help="Verify an acceptance ZIP; network access is opt-in"
    )
    command.add_argument("package", type=Path)
    command.add_argument("--deployment", type=Path)
    command.add_argument("--online", action="store_true")
    args = parser.parse_args()
    try:
        require(
            args.package.stat().st_size <= MAX_PACKAGE_BYTES, "Package exceeds 4 MiB"
        )
        result = verify(
            args.package.read_bytes(),
            deployment=Deployment.load(args.deployment) if args.deployment else None,
            online=args.online,
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["status"] == "verified" else 2
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "invalid", "error": str(error)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
