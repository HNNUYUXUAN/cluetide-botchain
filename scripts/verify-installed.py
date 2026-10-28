"""Install wheel and sdist into fresh environments and verify outside the checkout."""

import argparse, json, os, subprocess, tempfile, venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--wheel-only", action="store_true")
args = parser.parse_args()
packages = sorted((ROOT / "dist").glob("*.whl"))
if not args.wheel_only:
    packages += sorted((ROOT / "dist").glob("*.tar.gz"))
assert packages, "Build distributions first: python -m build"
for package in packages:
    with tempfile.TemporaryDirectory(prefix="cluetide-installed-") as name:
        folder = Path(name)
        venv.EnvBuilder(with_pip=True).create(folder / "env")
        python = folder / (
            "env/Scripts/python.exe" if os.name == "nt" else "env/bin/python"
        )
        cli = folder / (
            "env/Scripts/cluetide-release.exe"
            if os.name == "nt"
            else "env/bin/cluetide-release"
        )
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        subprocess.run(
            [str(python), "-m", "pip", "install", str(package)],
            cwd=folder,
            env=env,
            check=True,
        )
        for mode in ("eoa", "safe"):
            result = subprocess.run(
                [
                    str(cli),
                    "verify",
                    str(ROOT / f"fixtures/v2/{mode}-acceptance-v3.zip"),
                    "--deployment",
                    str(ROOT / "fixtures/v2/deployment.json"),
                ],
                cwd=folder,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            assert json.loads(result.stdout)["status"] == "verified"
        subprocess.run(
            [
                str(cli),
                "verify",
                str(ROOT / "evidence/complete-mainnet/acceptance-v3.zip"),
            ],
            cwd=folder,
            env=env,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            [
                str(cli),
                "verify",
                str(ROOT / "fixtures/v2/tampered-acceptance.zip"),
                "--deployment",
                str(ROOT / "fixtures/v2/deployment.json"),
            ],
            cwd=folder,
            env=env,
            capture_output=True,
            text=True,
        )
        assert (
            result.returncode == 1 and json.loads(result.stdout)["status"] == "invalid"
        )
        print(
            package.name + ": installed independently; v1/v2 valid, tamper rejected",
            flush=True,
        )
