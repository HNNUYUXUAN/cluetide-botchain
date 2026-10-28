import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import {fileURLToPath} from "node:url";
import solc from "solc";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
if (!solc.version().startsWith("0.8.30+commit.73712a01")) throw Error("Unexpected Solidity compiler");
for (const name of ["ClueTideReleaseWitness", "ClueTideReleaseWitnessV2"]) {
  const source = fs.readFileSync(path.join(root, "contracts", name + ".sol"));
  const input = {language:"Solidity", sources:{[name+".sol"]:{content:source.toString("utf8")}},
    settings:{optimizer:{enabled:true,runs:200},evmVersion:"paris",
      outputSelection:{"*":{"*":["abi","evm.bytecode.object","evm.deployedBytecode.object"]}}}};
  const output = JSON.parse(solc.compile(JSON.stringify(input)));
  const errors = (output.errors || []).filter(item=>item.severity==="error");
  if (errors.length) throw Error(errors.map(item=>item.formattedMessage).join("\n"));
  const result = output.contracts[name+".sol"][name];
  const artifact = {contractName:name, compiler:"0.8.30+commit.73712a01",
    evmVersion:"paris",optimizerRuns:200,sourceSha256:crypto.createHash("sha256").update(source).digest("hex"),
    abi:result.abi,bytecode:"0x"+result.evm.bytecode.object,deployedBytecode:"0x"+result.evm.deployedBytecode.object};
  const target = path.join(root,"contracts","artifacts",name+".json");
  if (name === "ClueTideReleaseWitness" || process.argv.includes("--check")) {
    const saved = JSON.parse(fs.readFileSync(target,"utf8"));
    for (const key of Object.keys(artifact)) if (JSON.stringify(saved[key])!==JSON.stringify(artifact[key])) throw Error(name+" artifact mismatch: "+key);
  } else fs.writeFileSync(target,JSON.stringify(artifact,null,2)+"\n");
  if (name.endsWith("V2")) {
    const resource=path.join(root,"src/cluetide/resources",name+".json");
    if (process.argv.includes("--check")) {
      if(!fs.readFileSync(resource).equals(fs.readFileSync(target))) throw Error("Packaged contract artifact differs");
    } else {
      fs.mkdirSync(path.dirname(resource),{recursive:true});
      fs.copyFileSync(target,resource);
    }
  }
  console.log(name+": source, ABI and bytecode verified with solc "+solc.version());
}
