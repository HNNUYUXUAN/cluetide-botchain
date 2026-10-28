"""EOA and ERC-1271 feedback with explicit historical state observations."""
from datetime import datetime
from eth_account.messages import encode_typed_data
from eth_abi import encode
from eth_utils import keccak
from .bundles import canonical_json_bytes
from .deployment import sha256,commitment
from .verification import require,recover_eoa

def typed_feedback(record,deployment):
    return {"types":{
        "EIP712Domain":[{"name":"name","type":"string"},{"name":"version","type":"string"},{"name":"chainId","type":"uint256"},{"name":"verifyingContract","type":"address"}],
        "ReviewFeedback":[{"name":"taskId","type":"bytes32"},{"name":"versionId","type":"uint256"},{"name":"manifestHash","type":"bytes32"},{"name":"correctionTransactionHash","type":"bytes32"},{"name":"contentHash","type":"bytes32"}]},
        "primaryType":"ReviewFeedback","domain":{"name":"ClueTideReviewFeedback","version":"2","chainId":deployment.chain_id,"verifyingContract":deployment.contract_address},
        "message":{"taskId":record["task_id"],"versionId":record["version_id"],"manifestHash":record["manifest_hash"],
            "correctionTransactionHash":record["correction_transaction_hash"],"contentHash":record["content_hash"]}}

def feedback_digest(record,deployment):
    message=encode_typed_data(full_message=typed_feedback(record,deployment))
    return keccak(b"\x19"+message.version+message.header+message.body)

def verify_feedback(record,task,deployment,*,chain=None):
    require(record["schema"]=="cluetide.review-feedback.v2" and record["deployment"]==deployment.context(),"Feedback deployment differs")
    require(record["task_id"]==task["task_id"] and record["reviewer"]==task["reviewer"],"Feedback reviewer differs")
    require(type(record["version_id"]) is int and 1<=record["version_id"]<=len(task["versions"]),"Feedback version missing")
    version=task["versions"][record["version_id"]-1]
    require(record["manifest_hash"]==version["manifest_hash"],"Feedback manifest differs")
    require(isinstance(record["reason"],str) and 0<len(record["reason"])<=4000,"Invalid correction reason")
    conditions=record["acceptance_conditions"]
    require(isinstance(conditions,list) and len(conditions)<=12 and all(isinstance(x,str) and 0<len(x)<=1000 for x in conditions),"Invalid acceptance conditions")
    require(record["content_hash"]==sha256(canonical_json_bytes({"reason":record["reason"],"acceptance_conditions":conditions})),"Feedback text differs")
    commitment(record["correction_transaction_hash"])
    if chain is not None:
        chain.verify_action("request_correction",task,version,record["correction_transaction_hash"],safe_nonce=record.get("safe_nonce"))
    if record["signature_scheme"]=="EIP-712":
        require(recover_eoa(typed_feedback(record,deployment),record["signature"])==task["reviewer"],"Reviewer signature differs")
    else:
        require(record["signature_scheme"]=="ERC-1271","Unsupported signature scheme")
        signature=bytes.fromhex(record["signature"].removeprefix("0x"))
        require(0<len(signature)<=16384,"Invalid contract signature size")
        if chain is None:
            return {"status":"requires_chain_state"}
        observation=record.get("verification")
        block=observation["block_number"] if observation else chain.w3.eth.block_number-deployment.confirmations+1
        require(type(block) is int and block>=0,"No confirmed validation block")
        anchor=chain.w3.eth.get_block(block)["hash"]
        if observation:
            require("0x"+anchor.hex().removeprefix("0x")==observation["block_hash"],"Validation block was reorganized")
        from web3 import Web3
        reviewer=Web3.to_checksum_address(task["reviewer"])
        require(len(chain.w3.eth.get_code(reviewer,block_identifier=block))>0,"Reviewer has no contract code")
        data=keccak(text="isValidSignature(bytes32,bytes)")[:4]+encode(["bytes32","bytes"],[feedback_digest(record,deployment),signature])
        value=chain.w3.eth.call({"to":reviewer,"data":"0x"+data.hex()},block_identifier=block)
        require(bytes(value)==bytes.fromhex("1626ba7e")+bytes(28),"ERC-1271 rejected the signature")
        require(chain.w3.eth.get_block(block)["hash"]==anchor,"Validation block changed")
        return {"status":"verified","block_number":block,"block_hash":"0x"+anchor.hex().removeprefix("0x"),"observed_at":datetime.now().astimezone().isoformat()}
    return {"status":"verified"}
