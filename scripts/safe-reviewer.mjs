/** Real Safe 1.4.1 transactions on the isolated Anvil demonstration network. */
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import Safe, {EthSafeSignature} from "@safe-global/protocol-kit";
import {createPublicClient,createWalletClient,http,recoverAddress,recoverMessageAddress} from "viem";
import {mnemonicToAccount} from "viem/accounts";
import {foundry} from "viem/chains";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const input=JSON.parse(fs.readFileSync(0,"utf8"));
const url=new URL(input.rpc);
if(url.protocol!=="http:" || !["127.0.0.1","localhost"].includes(url.hostname))throw Error("Local demonstration RPC required");
const publicClient=createPublicClient({chain:foundry,transport:http(input.rpc)});
if(await publicClient.getChainId()!==31337)throw Error("Anvil chain 31337 required");
const mnemonic="test test test test test test test test test test test junk";
const account=index=>mnemonicToAccount(mnemonic,{addressIndex:index});
const wallet=index=>createWalletClient({chain:foundry,transport:http(input.rpc),account:account(index)});
const artifact=(file,name)=>JSON.parse(fs.readFileSync(path.join(root,"node_modules/@safe-global/safe-contracts/build/artifacts/contracts",file,name+".json"),"utf8"));
let result;
if(input.command==="deploy"){
  const network={};
  for(const [key,file,name] of [
    ["safeSingletonAddress","Safe.sol","Safe"],["safeProxyFactoryAddress","proxies/SafeProxyFactory.sol","SafeProxyFactory"],
    ["fallbackHandlerAddress","handler/CompatibilityFallbackHandler.sol","CompatibilityFallbackHandler"],
    ["multiSendAddress","libraries/MultiSend.sol","MultiSend"],["multiSendCallOnlyAddress","libraries/MultiSendCallOnly.sol","MultiSendCallOnly"],
    ["signMessageLibAddress","libraries/SignMessageLib.sol","SignMessageLib"],["createCallAddress","libraries/CreateCall.sol","CreateCall"],
    ["simulateTxAccessorAddress","accessors/SimulateTxAccessor.sol","SimulateTxAccessor"]]){
    const a=artifact(file,name);
    const hash=await wallet(0).deployContract({abi:a.abi,bytecode:a.bytecode});
    const receipt=await publicClient.waitForTransactionReceipt({hash});
    network[key]=receipt.contractAddress;
  }
  const owners=[5,6,7].map(i=>account(i).address);
  const kit=await Safe.init({provider:input.rpc,signer:account(0).getHdKey().privateKey? "0x"+Buffer.from(account(0).getHdKey().privateKey).toString("hex"):undefined,
    predictedSafe:{safeAccountConfig:{owners,threshold:2,fallbackHandler:network.fallbackHandlerAddress},
      safeDeploymentConfig:{safeVersion:"1.4.1"}},isL1SafeSingleton:true,contractNetworks:{"31337":network}});
  const transaction=await kit.createSafeDeploymentTransaction();
  const hash=await wallet(0).sendTransaction({to:transaction.to,data:transaction.data,value:BigInt(transaction.value)});
  await publicClient.waitForTransactionReceipt({hash});
  result={address:await kit.getAddress(),owners,threshold:2,network,version:"1.4.1",deployment_tx:hash};
}else{
  const owner=input.owner ?? 5;
  if(![5,6,7].includes(owner))throw Error("Choose a demonstration Safe owner");
  const kit=await Safe.init({provider:input.rpc,safeAddress:input.safe.address,
    signer:"0x"+Buffer.from(account(owner).getHdKey().privateKey).toString("hex"),
    isL1SafeSingleton:true,contractNetworks:{"31337":input.safe.network}});
  if(input.command==="inspect"){
    result={owners:await kit.getOwners(),threshold:await kit.getThreshold(),nonce:await kit.getNonce()};
  }else if(input.command==="message"){
    let message=kit.createMessage(input.message);
    message=await kit.signMessage(message);
    result={signatures:[...message.signatures.values()].map(s=>({signer:s.signer,data:s.data})),encoded:message.encodedSignatures()};
  }else{
    const p=input.proposal;
    const transaction=await kit.createTransaction({transactions:[{to:p.to,value:"0",data:p.data,operation:0}],options:{nonce:p.nonce,safeTxGas:p.safeTxGas??"0",baseGas:"0",gasPrice:"0",gasToken:"0x0000000000000000000000000000000000000000",refundReceiver:"0x0000000000000000000000000000000000000000"}});
    for(const signature of p.signatures||[])transaction.addSignature(new EthSafeSignature(signature.signer,signature.data));
    const transactionHash=await kit.getTransactionHash(transaction);
    const owners=new Set((await kit.getOwners()).map(a=>a.toLowerCase()));
    const seen=new Set();
    for(const signature of p.signatures||[]){
      const signer=signature.signer.toLowerCase();
      if(seen.has(signer)||!owners.has(signer))throw Error("Duplicate or unsupported owner signature");
      seen.add(signer);
      const v=Number.parseInt(signature.data.slice(-2),16);
      const recovered=v>30?await recoverMessageAddress({message:{raw:transactionHash},signature:signature.data.slice(0,-2)+(v-4).toString(16)}):await recoverAddress({hash:transactionHash,signature:signature.data});
      if(recovered.toLowerCase()!==signer)throw Error("Owner signature does not match the exact Safe transaction");
    }
    if(p.safe_tx_hash&&p.safe_tx_hash!==transactionHash)throw Error("Safe transaction hash differs");
    if(input.command==="sign"){
      const signed=await kit.signTransaction(transaction);
      result={...p,safeTxGas:signed.data.safeTxGas,signatures:[...signed.signatures.values()].map(s=>({signer:s.signer,data:s.data})),safe_tx_hash:await kit.getTransactionHash(signed)};
    }else if(input.command==="validate"){
      result={...p,safe_tx_hash:transactionHash};
    }else if(input.command==="execute"){
      const execution=await kit.executeTransaction(transaction);
      const receipt=await publicClient.waitForTransactionReceipt({hash:execution.hash});
      result={transaction_hash:execution.hash,status:receipt.status,safe_tx_hash:await kit.getTransactionHash(transaction)};
    }else throw Error("Unsupported Safe command");
  }
}
process.stdout.write(JSON.stringify(result));
