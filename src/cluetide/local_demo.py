"""Loopback-only Anvil adapter. Every identity derives from Anvil's public mnemonic."""

from __future__ import annotations
import json
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3
from .bundles import canonical_json_bytes
from .chain_v2 import WitnessChain, artifact_v2, hex_value
from .deployment import Deployment, sha256
from .review_v2 import typed_feedback, feedback_digest, verify_feedback
from .service_v2 import ReleaseServiceV2
from .verification import require, verify, pack
from .release_exchange import read_zip, strict_json

PUBLIC_MNEMONIC = "test test test test test test test test test test test junk"


def test_account(index):
    Account.enable_unaudited_hdwallet_features()
    return Account.from_mnemonic(
        PUBLIC_MNEMONIC, account_path=f"m/44'/60'/0'/0/{index}"
    )


class LocalDemo:
    def __init__(self, root: Path, data: Path, rpc: str, node: str):
        self.root, self.data, self.rpc, self.node = root, data, rpc, node
        parsed = urlparse(rpc)
        require(
            parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"),
            "Loopback RPC required",
        )
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
        require(
            self.w3.eth.chain_id == 31337 and "anvil" in self.w3.client_version.lower(),
            "Local Anvil chain 31337 required",
        )
        self.lock = threading.RLock()
        data.mkdir(parents=True, exist_ok=True)
        path = data / "fixture.json"
        if path.exists():
            self.fixture = strict_json(path.read_bytes())
            self.deployment = Deployment.load(data / "deployment.json")
            require(
                self.deployment.rpc_url == rpc,
                "Existing demonstration uses a different RPC",
            )
        else:
            artifact = artifact_v2()
            contract = self.w3.eth.contract(
                abi=artifact["abi"], bytecode=artifact["bytecode"]
            )
            receipt = self.w3.eth.wait_for_transaction_receipt(
                contract.constructor().transact({"from": test_account(0).address})
            )
            require(receipt["status"] == 1, "Witness deployment failed")
            self.deployment = Deployment(
                chain_id=31337,
                contract_address=receipt["contractAddress"],
                runtime_sha256=sha256(
                    bytes(self.w3.eth.get_code(receipt["contractAddress"]))
                ),
                receipt_signer=test_account(4).address,
                rpc_url=rpc,
                confirmations=1,
            )
            self.fixture = {
                "safe": self.safe_call("deploy"),
                "tasks": [],
                "journal": [],
                "proposals": {},
                "active_task": None,
            }
            (data / "deployment.json").write_bytes(
                canonical_json_bytes(self.deployment.to_dict())
            )
            self.save()
        self.chain = WitnessChain(self.deployment, self.w3)
        self.chain.identity()
        require(
            len(
                self.w3.eth.get_code(
                    Web3.to_checksum_address(self.fixture["safe"]["address"])
                )
            )
            > 0,
            "Saved Safe is absent; restore Anvil state or use a new demo directory",
        )
        self.service = ReleaseServiceV2(
            data / "publisher",
            deployment=self.deployment,
            chain=self.chain,
            signing_key=test_account(4).key,
        )

    def save(self):
        temp = self.data / "fixture.tmp"
        temp.write_bytes(canonical_json_bytes(self.fixture))
        temp.replace(self.data / "fixture.json")

    def safe_call(self, command, **kwargs):
        payload = {"command": command, "rpc": self.rpc, **kwargs}
        if hasattr(self, "fixture"):
            payload["safe"] = self.fixture["safe"]
        result = subprocess.run(
            [self.node, str(self.root / "scripts/safe-reviewer.mjs")],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=90,
            cwd=self.root,
        )
        require(result.returncode == 0, "Safe SDK: " + result.stderr[-1500:])
        return json.loads(result.stdout)

    def state(self):
        with self.lock:
            tasks = []
            for task_id in self.fixture["tasks"]:
                task = self.service.get_task(task_id)
                task["chain_versions"] = [
                    list(self.chain.version(task_id, v["version_id"]))
                    for v in task["versions"]
                ]
                # Keep binary commitments JSON-compatible.
                task["chain_versions"] = [
                    [hex_value(x) if isinstance(x, bytes) else x for x in row]
                    for row in task["chain_versions"]
                ]
                tasks.append(task)
            return {
                "schema": "cluetide.local-demo.v2",
                "version": "0.2.0",
                "chain": "Anvil local · 31337",
                "deployment": self.deployment.to_dict(),
                "safe": {**self.fixture["safe"], **self.safe_call("inspect")},
                "roles": {
                    k: test_account(i).address.lower()
                    for k, i in [
                        ("owner", 0),
                        ("proposer", 1),
                        ("reviewer", 2),
                        ("executor", 3),
                        ("receipt_signer", 4),
                    ]
                },
                "tasks": tasks,
                "active_task": self.fixture["active_task"],
                "proposals": self.fixture["proposals"],
                "journal": self.fixture["journal"],
            }

    def transact(self, action, task, version=None, envelope=None):
        role = {
            "create_task": 0,
            "propose_version": 1,
            "approve": 2,
            "request_correction": 2,
            "revoke": 2,
            "consume": 3,
            "record_receipt": 3,
        }[action]
        entry = {
            "action": action,
            "task_id": task["task_id"],
            "version_id": version["version_id"] if version else None,
            "status": "sending",
        }
        self.fixture["journal"].append(entry)
        self.save()
        tx = self.chain.function(action, task, version, envelope).transact(
            {"from": test_account(role).address}
        )
        entry.update(transaction_hash=hex_value(tx), status="pending")
        self.save()
        self.w3.eth.wait_for_transaction_receipt(tx)
        proof = self.chain.verify_action(
            action, task, version, hex_value(tx), envelope=envelope
        )
        entry.update(**proof)
        self.save()
        return entry

    def current(self):
        require(self.fixture["active_task"] is not None, "Create a local task first")
        return self.service.get_task(self.fixture["active_task"])

    def command(self, action, payload):
        with self.lock:
            if action == "create":
                require(
                    payload.get("mode") in ("eoa", "safe"),
                    "Choose an EOA or Safe reviewer",
                )
                task = self.service.create_task(
                    {
                        "title": "Exact release · " + payload["mode"].upper(),
                        "owner": test_account(0).address,
                        "proposer": test_account(1).address,
                        "executor": test_account(3).address,
                        "reviewer": self.fixture["safe"]["address"]
                        if payload["mode"] == "safe"
                        else test_account(2).address,
                    }
                )
                self.transact("create_task", task)
                self.fixture["tasks"].append(task["task_id"])
                self.fixture["active_task"] = task["task_id"]
                self.save()
                return task
            if action == "select":
                require(payload.get("task_id") in self.fixture["tasks"], "Unknown task")
                self.fixture["active_task"] = payload["task_id"]
                self.save()
                return {}
            task = self.current()
            if action == "propose":
                version = self.service.create_version(
                    task["task_id"],
                    {
                        "summary": payload.get(
                            "summary", "A reproducible local delivery"
                        ),
                        "source_reference": "cluetide-botchain v0.2.0 local demonstration",
                        "test_evidence": [
                            "Local artifact inspected; witness authorization verified"
                        ],
                        "artifact_text": payload["artifact"],
                        "expires_at": int(time.time()) + 86400,
                    },
                )
                task = self.current()
                return self.transact("propose_version", task, version)
            require(task["versions"], "Propose a version first")
            version = task["versions"][-1]
            safe = task["reviewer"] == self.fixture["safe"]["address"].lower()
            if action in ("approve", "request_correction", "revoke"):
                if not safe:
                    return self.transact(action, task, version)
                proposal = {
                    "schema": "cluetide.safe-review.v2",
                    "deployment": self.deployment.context(),
                    "safe": task["reviewer"],
                    "task_id": task["task_id"],
                    "version_id": version["version_id"],
                    "manifest_hash": version["manifest_hash"],
                    "action": action,
                    "nonce": self.safe_call("inspect")["nonce"],
                    "to": self.deployment.contract_address,
                    "data": self.chain.function(
                        action, task, version
                    )._encode_transaction_data(),
                    "safeTxGas": "0",
                    "signatures": [],
                }
                self.fixture["proposals"][task["task_id"]] = proposal
                self.save()
                return proposal
            if action in ("safe_sign", "safe_execute", "safe_import"):
                proposal = self.fixture["proposals"].get(task["task_id"])
                require(
                    safe and proposal is not None,
                    "Prepare a Safe reviewer action first",
                )
                require(
                    proposal["version_id"] == version["version_id"]
                    and proposal["nonce"] == self.safe_call("inspect")["nonce"],
                    "Proposal is stale; prepare it again",
                )
                if action == "safe_import":
                    incoming = payload["proposal"]
                    require(
                        isinstance(incoming, dict)
                        and all(
                            incoming.get(k) == v
                            for k, v in proposal.items()
                            if k not in ("signatures", "safe_tx_hash")
                        ),
                        "Imported proposal context differs",
                    )
                    require(
                        set(incoming) <= set(proposal) | {"safe_tx_hash"},
                        "Unsupported proposal fields",
                    )
                    signatures = incoming.get("signatures", [])
                    require(
                        isinstance(signatures, list) and len(signatures) <= 3,
                        "Invalid signature count",
                    )
                    owners = {a.lower() for a in self.safe_call("inspect")["owners"]}
                    require(
                        len({s["signer"].lower() for s in signatures})
                        == len(signatures)
                        and all(
                            s["signer"].lower() in owners
                            and len(bytes.fromhex(s["data"].removeprefix("0x"))) == 65
                            for s in signatures
                        ),
                        "Invalid or duplicate owner signatures",
                    )
                    proposal = {**proposal, "signatures": signatures}
                    proposal = self.safe_call("validate", proposal=proposal)
                elif action == "safe_sign":
                    proposal = self.safe_call(
                        "sign", owner=payload.get("owner", 5), proposal=proposal
                    )
                else:
                    require(
                        len(proposal["signatures"]) >= 2,
                        "Two distinct owner signatures are required",
                    )
                    result = self.safe_call("execute", proposal=proposal)
                    proof = self.chain.verify_action(
                        proposal["action"],
                        task,
                        version,
                        result["transaction_hash"],
                        safe_nonce=proposal["nonce"],
                    )
                    self.fixture["journal"].append(
                        {
                            **proof,
                            "action": proposal["action"],
                            "task_id": task["task_id"],
                            "version_id": version["version_id"],
                            "safe_nonce": proposal["nonce"],
                        }
                    )
                    del self.fixture["proposals"][task["task_id"]]
                    self.save()
                    return proof
                self.fixture["proposals"][task["task_id"]] = proposal
                self.save()
                return proposal
            if action == "feedback":
                corrections = [
                    e
                    for e in self.fixture["journal"]
                    if e["action"] == "request_correction"
                    and e["task_id"] == task["task_id"]
                    and e["version_id"] == version["version_id"]
                    and e["status"] == "verified"
                ]
                require(corrections, "An on-chain correction is required")
                correction = corrections[-1]
                content = {
                    "reason": payload.get("reason", "Add release verification details"),
                    "acceptance_conditions": [
                        "Include the verification steps in the revised artifact"
                    ],
                }
                record = {
                    "schema": "cluetide.review-feedback.v2",
                    "deployment": self.deployment.context(),
                    "task_id": task["task_id"],
                    "version_id": version["version_id"],
                    "manifest_hash": version["manifest_hash"],
                    "reviewer": task["reviewer"],
                    **content,
                    "content_hash": sha256(canonical_json_bytes(content)),
                    "correction_transaction_hash": correction["transaction_hash"],
                    "safe_nonce": correction.get("safe_nonce"),
                }
                if safe:
                    # SDK wraps this typed-data digest in SafeMessage before both owners sign.
                    message = typed_feedback(record, self.deployment)
                    signatures = []
                    for owner in (5, 6):
                        signatures += self.safe_call(
                            "message", owner=owner, message=message
                        )["signatures"]
                    record.update(
                        signature_scheme="ERC-1271",
                        signature="0x"
                        + "".join(
                            s["data"].removeprefix("0x")
                            for s in sorted(
                                signatures, key=lambda s: s["signer"].lower()
                            )
                        ),
                    )
                else:
                    signature = Account.sign_message(
                        encode_typed_data(
                            full_message=typed_feedback(record, self.deployment)
                        ),
                        test_account(2).key,
                    ).signature
                    record.update(
                        signature_scheme="EIP-712", signature=hex_value(signature)
                    )
                record["verification"] = verify_feedback(
                    record, task, self.deployment, chain=self.chain
                )
                self.service._save(
                    self.service.root
                    / "feedback"
                    / task["task_id"]
                    / f"{version['version_id']}.json",
                    record,
                    immutable=True,
                )
                return record
            if action == "consume":
                return self.transact(action, task, version)
            consumes = [
                e
                for e in self.fixture["journal"]
                if e["action"] == "consume"
                and e["task_id"] == task["task_id"]
                and e["version_id"] == version["version_id"]
                and e["status"] == "verified"
            ]
            require(consumes, "Consume the exact approved version first")
            attempt_id = str(
                self.chain.version(task["task_id"], version["version_id"])[7]
            )
            if action == "publish":
                return self.service.execute(
                    task["task_id"],
                    {
                        "version_id": version["version_id"],
                        "attempt_id": attempt_id,
                        "start_transaction_hash": consumes[-1]["transaction_hash"],
                    },
                )
            if action == "record_receipt":
                return self.transact(
                    action,
                    task,
                    version,
                    self.service.receipt(attempt_id, task["task_id"]),
                )
            if action in ("verify", "tamper"):
                bundle = self.service.export_acceptance(task["task_id"], attempt_id)
                if action == "tamper":
                    entries = read_zip(bundle)
                    entries["published/artifact.html"] += b"!"
                    bundle = pack(entries)
                result = verify(
                    bundle,
                    deployment=self.deployment,
                    online=payload.get("online", False),
                )
                if payload.get("online"):
                    current = self.service.artifact(task["task_id"])
                    result["live_artifact_verified"] = (
                        sha256(current) == version["artifact_hash"]
                    )
                    result["checks"]["live_artifact"] = (
                        "verified" if result["live_artifact_verified"] else "mismatch"
                    )
                return result
            raise ValueError("Unsupported local demonstration action")


def app_for(demo: LocalDemo):
    from fastapi import FastAPI, Request, Body
    from fastapi.responses import JSONResponse, Response, FileResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def local_boundary(request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        origin = request.headers.get("origin")
        if (
            host not in ("127.0.0.1", "localhost", "testserver")
            or request.headers.get("sec-fetch-site") == "cross-site"
            or (origin and origin != str(request.base_url).rstrip("/"))
        ):
            return JSONResponse(
                {"error": "Local same-origin demonstration only"}, status_code=403
            )
        if int(request.headers.get("content-length", "0")) > 200000:
            return JSONResponse(
                {"error": "Request exceeds local limit"}, status_code=413
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def error(request, error):
        return JSONResponse({"error": str(error)[:1500]}, status_code=400)

    @app.get("/api/local/health")
    def health():
        demo.chain.identity()
        return {
            "service": "cluetide-local-demo",
            "version": "0.2.0",
            "root": str(demo.data.resolve()),
        }

    @app.get("/api/local/state")
    def state():
        return demo.state()

    @app.post("/api/local/{action}")
    def command(action: str, payload: dict = Body(default={})):
        return demo.command(action, payload)

    @app.get("/api/local/deployment.json")
    def profile():
        return demo.deployment.to_dict()

    @app.get("/api/local/acceptance.zip")
    def acceptance():
        task = demo.current()
        attempt = str(demo.chain.version(task["task_id"], len(task["versions"]))[7])
        return Response(
            demo.service.export_acceptance(task["task_id"], attempt),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=cluetide-local-v2.zip"
            },
        )

    @app.get("/api/local/proposal.json")
    def proposal():
        return demo.fixture["proposals"].get(demo.fixture["active_task"])

    @app.get("/api/local/artifact")
    def artifact():
        return Response(
            demo.service.artifact(demo.current()["task_id"]),
            media_type="text/html",
            headers={
                "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'"
            },
        )

    app.mount(
        "/",
        StaticFiles(directory=demo.root / "frontend/dist-local", html=True),
        name="local-ui",
    )
    return app
