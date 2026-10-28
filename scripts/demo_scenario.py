"""Exercise actual EOA and Safe transactions; export reproducible acceptance samples."""

import argparse
from pathlib import Path
from toolchain import ROOT, node_tools
from cluetide.local_demo import LocalDemo
from cluetide.bundles import canonical_json_bytes


def scenario(demo, mode):
    task = demo.command("create", {"mode": mode})

    def review(action):
        demo.command(action, {})
        if mode == "safe":
            demo.command("safe_sign", {"owner": 5})
            demo.command("safe_sign", {"owner": 6})
            demo.command("safe_execute", {})

    for version in (1, 2, 3):
        demo.command(
            "propose",
            {
                "summary": f"Version {version}: exact release verification",
                "artifact": f"<!doctype html><html lang=en><meta charset=utf-8><title>ClueTide local release</title><h1>Local release v{version}</h1><p>Chain 31337. Independently verified delivery.</p></html>",
            },
        )
        if version < 3:
            review("request_correction")
            demo.command(
                "feedback",
                {"reason": f"Clarify verification evidence for revision {version + 1}"},
            )
    review("approve")
    demo.command("consume", {})
    result = demo.command("publish", {})
    assert result["status"] == "succeeded", result
    demo.command("record_receipt", {})
    result = demo.command("verify", {"online": True})
    assert result["status"] == "verified" and result["current_chain_verified"], result
    output = demo.data / "samples"
    output.mkdir(exist_ok=True)
    (output / f"{mode}-acceptance-v3.zip").write_bytes(
        demo.service.export_acceptance(task["task_id"], "1")
    )
    (output / f"{mode}-verification.json").write_bytes(canonical_json_bytes(result))
    try:
        demo.command("tamper", {})
    except ValueError:
        pass
    else:
        raise AssertionError("Tampered package was accepted")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="http://127.0.0.1:18545")
    parser.add_argument("--data", type=Path, default=ROOT / ".local-demo/scenario")
    args = parser.parse_args()
    demo = LocalDemo(ROOT, args.data, args.rpc, str(node_tools()[0]))
    for mode in ("eoa", "safe"):
        print(mode, scenario(demo, mode), flush=True)
