"""Explicit trust roots for versioned witness deployments."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from eth_abi import encode
from eth_utils import keccak

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")


def address(value):
    if (
        not isinstance(value, str)
        or not ADDRESS.fullmatch(value)
        or int(value, 16) == 0
    ):
        raise ValueError("Invalid address")
    return value.lower()


def commitment(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError("Invalid bytes32")
    return value.lower()


def sha256(value: bytes):
    return "0x" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class Deployment:
    chain_id: int
    contract_address: str
    runtime_sha256: str
    receipt_signer: str
    rpc_url: str
    confirmations: int = 3
    protocol_version: int = 2
    policy: str = "cluetide.demo-release.v2"
    target: str = "demo-site"
    artifact_limit: int = 32768

    def __post_init__(self):
        if (
            type(self.chain_id) is not int
            or self.chain_id <= 0
            or self.protocol_version != 2
        ):
            raise ValueError("Unsupported deployment version or chain")
        if type(self.confirmations) is not int or not 1 <= self.confirmations <= 100:
            raise ValueError("Invalid confirmation policy")
        if (
            self.policy != "cluetide.demo-release.v2"
            or self.target != "demo-site"
            or self.artifact_limit != 32768
        ):
            raise ValueError("Unsupported publication policy")
        for key in ("contract_address", "receipt_signer"):
            object.__setattr__(self, key, address(getattr(self, key)))
        object.__setattr__(self, "runtime_sha256", commitment(self.runtime_sha256))
        url = urlsplit(self.rpc_url)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.fragment
            or (
                url.scheme != "https"
                and not (
                    url.scheme == "http"
                    and url.hostname in ("127.0.0.1", "localhost", "::1")
                )
            )
        ):
            raise ValueError("RPC must use HTTPS or a loopback HTTP endpoint")

    @classmethod
    def load(cls, path):
        from .release_exchange import strict_json

        return cls(**strict_json(Path(path).read_bytes()))

    def context(self):
        return {
            "protocol_version": 2,
            "chain_id": self.chain_id,
            "contract_address": self.contract_address,
        }

    def to_dict(self):
        return asdict(self)

    def task_id(self, owner, salt):
        return (
            "0x"
            + keccak(
                encode(
                    ["uint256", "address", "address", "bytes32"],
                    [
                        self.chain_id,
                        self.contract_address,
                        address(owner),
                        bytes.fromhex(commitment(salt)[2:]),
                    ],
                )
            ).hex()
        )

    def target_id(self, task_id):
        return sha256((self.policy + "/" + commitment(task_id)).encode())
