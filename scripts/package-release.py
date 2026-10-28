"""Package an already validated source revision and distributions with SHA-256 sums."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ci-url", required=True)
parser.add_argument("--validated-head", required=True)
args = parser.parse_args()
version = "0.2.0"
revision = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
).strip()
output = ROOT / "dist" / ("release-v" + version)
output.mkdir(parents=True, exist_ok=True)


def archive(name, paths):
    target = output / name
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative in paths:
            source = ROOT / relative
            files = sorted(source.rglob("*")) if source.is_dir() else [source]
            for item in files:
                if item.is_file():
                    bundle.write(item, item.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as bundle:
        assert bundle.testzip() is None


for pattern in ("*.whl", "*.tar.gz"):
    packages = list((ROOT / "dist").glob(pattern))
    assert len(packages) == 1, f"Expected exactly one built {pattern}"
    shutil.copyfile(packages[0], output / packages[0].name)
subprocess.run(
    [
        "git",
        "archive",
        "--format=zip",
        "--prefix=cluetide-botchain-v0.2.0/",
        "--output=" + str(output / "cluetide-botchain-v0.2.0-source.zip"),
        "HEAD",
    ],
    cwd=ROOT,
    check=True,
)
archive(
    "cluetide-v0.2.0-contracts-and-config.zip",
    [
        "contracts",
        "configs",
        "schemas",
        "fixtures/v2/deployment.json",
        ".gas-snapshot",
        "foundry.toml",
    ],
)
archive(
    "cluetide-v0.2.0-acceptance-samples.zip",
    [
        "fixtures/v2",
        "evidence/complete-mainnet/acceptance-v3.zip",
        "docs/provenance-v0.2.0.md",
    ],
)
archive("cluetide-v0.2.0-static-site.zip", ["frontend/dist"])
archive(
    "cluetide-v0.2.0-validation.zip",
    [
        "docs/release-v0.2.0",
        "test-results/browser-results.json",
        ".local-demo/python-results.xml",
        ".local-demo/safe-results.xml",
        ".gas-snapshot",
        "docs/media/recording.json",
    ],
)
shutil.copyfile(
    ROOT / "docs/media/cluetide-v0.2.0-local-demo.webm",
    output / "cluetide-v0.2.0-local-demo.webm",
)
manifest = {
    "schema": "cluetide.release-distribution.v1",
    "version": version,
    "source_revision": revision,
    "validated_head": args.validated_head,
    "ci_url": args.ci_url,
    "packaged_at": datetime.now(timezone.utc).isoformat(),
    "solidity": "0.8.30",
    "evm": "paris",
    "optimizer_runs": 200,
    "foundry": "1.8.6",
    "safe": "1.4.1",
    "protocol_kit": "8.0.7",
    "deployment_scope": "local-v2; historical-mainnet-v1-read-only",
}
(output / "release-manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
)
sums = []
for item in sorted(output.iterdir()):
    if item.name != "SHA256SUMS.txt" and item.is_file():
        sums.append(hashlib.sha256(item.read_bytes()).hexdigest() + "  " + item.name)
(output / "SHA256SUMS.txt").write_text(
    "\n".join(sums) + "\n", encoding="utf-8", newline="\n"
)
for line in sums:
    digest, name = line.split("  ", 1)
    assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
print(
    json.dumps(
        {
            "output": str(output),
            "source_revision": revision,
            "files": len(sums),
            "checksums": "verified",
        },
        indent=2,
    )
)
