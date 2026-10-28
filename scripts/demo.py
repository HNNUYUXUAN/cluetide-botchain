"""One-command, project-local Anvil + Safe + isolated publisher demonstration."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import venv
from toolchain import ROOT, node_tools, foundry_tools, npm_run, node_environment


def available(port):
    with socket.socket() as connection:
        return connection.connect_ex(("127.0.0.1", port)) != 0


def health(port):
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/local/health", timeout=3
        ) as response:
            return json.load(response)
    except Exception:
        return None


def spawn(args, log):
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with log.open("ab") as output:
        return subprocess.Popen(
            args,
            cwd=ROOT,
            env={**node_environment(), "PYTHONUTF8": "1"},
            stdout=output,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **options,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--rpc-port", type=int, default=18545)
    parser.add_argument("--data", type=Path, default=ROOT / ".local-demo/default")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Reuse the prepared project environment and frontend build",
    )
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    data = args.data.resolve()
    if not data.is_relative_to(ROOT.resolve()) or data == ROOT.resolve():
        raise RuntimeError("Demo state must be in a subdirectory of this checkout")
    if (
        not all(1024 <= p <= 65535 for p in (args.port, args.rpc_port))
        or args.port == args.rpc_port
    ):
        raise RuntimeError("Choose two distinct unprivileged ports")
    if args.serve:
        from cluetide.local_demo import LocalDemo, app_for
        import uvicorn

        demo = LocalDemo(
            ROOT, data, f"http://127.0.0.1:{args.rpc_port}", str(node_tools()[0])
        )
        uvicorn.run(
            app_for(demo), host="127.0.0.1", port=args.port, log_level="warning"
        )
        return
    existing = health(args.port)
    if (
        existing
        and existing.get("service") == "cluetide-local-demo"
        and existing.get("root") == str(data)
    ):
        print(f"Healthy demo reused: http://127.0.0.1:{args.port}")
        return
    if not available(args.port):
        raise RuntimeError(
            f"Port {args.port} is occupied. Choose --port; no process was stopped."
        )
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Install Python 3.12, then run this command again")
    data.mkdir(parents=True, exist_ok=True)
    python = ROOT / (
        ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
    )
    if not args.skip_install:
        if not python.exists():
            venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
        subprocess.run(
            [str(python), "-m", "pip", "install", "-e", ".[dev]"], cwd=ROOT, check=True
        )
        npm_run("ci", "--no-audit", "--no-fund")
        npm_run("run", "compile:check")
        npm_run("ci", "--no-audit", "--no-fund", cwd=ROOT / "frontend")
        npm_run("run", "build:local", cwd=ROOT / "frontend")
    if not python.exists() or not (ROOT / "frontend/dist-local/index.html").exists():
        raise RuntimeError("Run without --skip-install to prepare the environment")
    anvil = None
    if available(args.rpc_port):
        anvil = spawn(
            [
                str(foundry_tools()["anvil"]),
                "--host",
                "127.0.0.1",
                "--port",
                str(args.rpc_port),
                "--chain-id",
                "31337",
                "--state",
                str(data / "anvil.json"),
                "--state-interval",
                "1",
                "--silent",
            ],
            data / "anvil.log",
        )
        for _ in range(100):
            if not available(args.rpc_port):
                break
            if anvil.poll() is not None:
                raise RuntimeError("Anvil failed; inspect anvil.log")
            time.sleep(0.1)
    elif not (data / "processes.json").exists():
        raise RuntimeError(
            f"RPC port {args.rpc_port} is occupied. Choose --rpc-port; no process was stopped."
        )
    # A resumed RPC is additionally checked for Anvil, chain, contract runtime and fixture by the server.
    server = spawn(
        [
            str(python),
            str(Path(__file__).resolve()),
            "--serve",
            "--port",
            str(args.port),
            "--rpc-port",
            str(args.rpc_port),
            "--data",
            str(data),
        ],
        data / "server.log",
    )
    (data / "processes.json").write_text(
        json.dumps(
            {
                "server_pid": server.pid,
                "anvil_pid": anvil.pid if anvil else None,
                "port": args.port,
                "rpc_port": args.rpc_port,
                "root": str(data),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for _ in range(180):
        result = health(args.port)
        if result:
            print(
                f"ClueTide v0.2.0 · Anvil 31337 · http://127.0.0.1:{args.port}\nState and logs: {data}"
            )
            return
        if server.poll() is not None:
            raise RuntimeError(f"Demo startup failed. Inspect {data / 'server.log'}")
        time.sleep(0.5)
    raise RuntimeError(f"Demo startup timed out. Inspect {data / 'server.log'}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
