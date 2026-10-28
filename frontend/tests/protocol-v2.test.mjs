import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {keccak256,encodeAbiParameters,sha256,stringToHex,recoverTypedDataAddress} from 'viem';
const vector=JSON.parse(fs.readFileSync(new URL('../../fixtures/v2/shared-vectors.json',import.meta.url),'utf8'));
test('v2 Python/TypeScript task namespace and exact byte commitments',()=>{
  const {deployment:d,owner,salt}=vector;
  assert.equal(keccak256(encodeAbiParameters([{type:'uint256'},{type:'address'},{type:'address'},{type:'bytes32'}],[BigInt(d.chain_id),d.contract_address,owner,salt])),vector.task_id);
  assert.equal(sha256(stringToHex(vector.manifest_text)),vector.manifest_hash);
  assert.equal(sha256(stringToHex(vector.artifact_text)),vector.artifact_hash);
});
test('v2 receipt EIP-712 is interoperable',async()=>{
  const t=vector.typed_receipt;
  assert.equal((await recoverTypedDataAddress({...t,signature:vector.receipt.signature})).toLowerCase(),vector.deployment.receipt_signer);
  assert.notEqual((await recoverTypedDataAddress({...t,domain:{...t.domain,version:'1'},signature:vector.receipt.signature})).toLowerCase(),vector.deployment.receipt_signer);
});
