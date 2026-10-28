import {encodeFunctionData,parseAbi,hashTypedData,recoverAddress,recoverMessageAddress,type Hex,type Address} from "viem";
export type SafeReview={schema:string;deployment:{chain_id:number;protocol_version:number;contract_address:string};safe:string;task_id:Hex;version_id:number;manifest_hash:Hex;action:string;nonce:number;to:Address;data:Hex;safeTxGas:string;signatures:{signer:string;data:Hex}[];safe_tx_hash?:Hex};
const abi=parseAbi(["function approve(bytes32,uint256,bytes32,bytes32,uint64)","function requestCorrection(bytes32,uint256)","function revoke(bytes32,uint256)"]);
const zero="0x0000000000000000000000000000000000000000" as const;
export async function validateSafeReview(p:SafeReview,context:{task_id:string;version_id:number;manifest_hash:string;artifact_hash:string;expires_at:number;contract:string;safe:string;nonce:number;owners:string[]}){
  if(p.schema!=="cluetide.safe-review.v2"||p.deployment.chain_id!==31337||p.deployment.protocol_version!==2||p.deployment.contract_address!==context.contract||p.to!==context.contract||p.safe!==context.safe.toLowerCase()||p.task_id!==context.task_id||p.version_id!==context.version_id||p.manifest_hash!==context.manifest_hash||p.nonce!==context.nonce||p.safeTxGas!=="0")throw Error("Safe proposal differs from the exact local release");
  const functionName=p.action==="request_correction"?"requestCorrection":p.action;
  if(!["approve","requestCorrection","revoke"].includes(functionName))throw Error("Unsupported reviewer action");
  const data=functionName==="approve"?encodeFunctionData({abi,functionName:"approve",args:[p.task_id,BigInt(p.version_id),p.manifest_hash,context.artifact_hash as Hex,BigInt(context.expires_at)]}):encodeFunctionData({abi,functionName:functionName as "revoke"|"requestCorrection",args:[p.task_id,BigInt(p.version_id)]});
  if(p.data!==data)throw Error("Safe calldata differs from the reviewed version");
  const fields=[{name:"to",type:"address"},{name:"value",type:"uint256"},{name:"data",type:"bytes"},{name:"operation",type:"uint8"},{name:"safeTxGas",type:"uint256"},{name:"baseGas",type:"uint256"},{name:"gasPrice",type:"uint256"},{name:"gasToken",type:"address"},{name:"refundReceiver",type:"address"},{name:"nonce",type:"uint256"}];
  const hash=hashTypedData({domain:{chainId:31337,verifyingContract:p.safe as Address},primaryType:"SafeTx",types:{SafeTx:fields},message:{to:p.to,value:0n,data:p.data,operation:0,safeTxGas:0n,baseGas:0n,gasPrice:0n,gasToken:zero,refundReceiver:zero,nonce:BigInt(p.nonce)}});
  if(p.safe_tx_hash&&p.safe_tx_hash!==hash)throw Error("Safe transaction hash differs");
  const owners=new Set(context.owners.map(x=>x.toLowerCase())),seen=new Set<string>();
  if(p.signatures.length>3)throw Error("Invalid signature count");
  for(const s of p.signatures){
    const signer=s.signer.toLowerCase();if(seen.has(signer)||!owners.has(signer)||s.data.length!==132)throw Error("Duplicate or unsupported owner signature");seen.add(signer);
    const v=parseInt(s.data.slice(-2),16);
    const recovered=v>30?await recoverMessageAddress({message:{raw:hash},signature:(s.data.slice(0,-2)+(v-4).toString(16)) as Hex}):await recoverAddress({hash,signature:s.data});
    if(recovered.toLowerCase()!==signer)throw Error("Owner signature differs from the exact Safe transaction");
  }
  return hash;
}
