"""Project-local, checksum-verified tools. No system configuration is changed."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
NODE_VERSION = "24.19.0"
FOUNDRY_VERSION = "1.8.6"
FOUNDRY_HASHES = {
    "win32_amd64": "924d6395786af438e7cb315f6835185f99d727ed6127dbbc4e6a62eb14edcfff",
    "linux_amd64": "58850106984038f3a7200f38a4182c8cb423d3a4f4c7848eacbc2453e6bc35fc",
}

def download(url, path, sha256):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        request = urllib.request.Request(url, headers={"User-Agent": "ClueTide/0.2.0"})
        with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as output:
            shutil.copyfileobj(response, output)
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise RuntimeError("Tool download checksum mismatch")
    return path

def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                if not (destination / name).resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError("Unsafe tool archive")
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter="data")

def node_tools():
    system = "win" if os.name == "nt" else "linux"
    arch = "arm64" if platform.machine().lower() in ("aarch64", "arm64") else "x64"
    folder = TOOLS / f"node-v{NODE_VERSION}-{system}-{arch}"
    node = folder / ("node.exe" if os.name == "nt" else "bin/node")
    npm = folder / ("node_modules/npm/bin/npm-cli.js" if os.name == "nt" else "lib/node_modules/npm/bin/npm-cli.js")
    if not node.exists() or not npm.exists():
        filename = folder.name + (".zip" if os.name == "nt" else ".tar.xz")
        base = f"https://nodejs.org/dist/v{NODE_VERSION}/"
        sums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=30).read().decode()
        expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == filename)
        extract(download(base + filename, TOOLS / filename, expected), TOOLS)
    return node, npm

def foundry_tools():
    key = "win32_amd64" if os.name == "nt" else "linux_amd64"
    if platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("This bootstrap supports x86_64 Windows/Linux. Install pinned Foundry manually on other platforms.")
    folder = TOOLS / f"foundry-{FOUNDRY_VERSION}"
    suffix = ".exe" if os.name == "nt" else ""
    if not all((folder / (name + suffix)).exists() for name in ("anvil", "forge", "cast")):
        filename = f"foundry_v{FOUNDRY_VERSION}_{key}" + (".zip" if os.name == "nt" else ".tar.gz")
        base = f"https://github.com/foundry-rs/foundry/releases/download/v{FOUNDRY_VERSION}/"
        extract(download(base + filename, TOOLS / filename, FOUNDRY_HASHES[key]), folder)
    return {name: folder / (name + suffix) for name in ("anvil", "forge", "cast")}

def node_environment():
    node, _ = node_tools()
    env = os.environ.copy()
    env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
    return env

def npm_run(*args, cwd=ROOT):
    node, npm = node_tools()
    return subprocess.run([str(node), str(npm), *args], cwd=cwd, env=node_environment(), check=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=("install", "npm", "node", "forge", "anvil", "cast"))
    args, rest = parser.parse_known_args()
    if args.tool == "install":
        node_tools()
        foundry_tools()
        print("Pinned Node and Foundry are ready in .tools")
    elif args.tool == "npm":
        npm_run(*rest)
    elif args.tool == "node":
        subprocess.run([str(node_tools()[0]), *rest], cwd=ROOT, env=node_environment(), check=True)
    else:
        subprocess.run([str(foundry_tools()[args.tool]), *rest], cwd=ROOT, check=True)
