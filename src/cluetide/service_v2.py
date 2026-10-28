"""Versioned protocol over the existing locked, durable file publisher."""
import secrets
from pathlib import Path
from eth_account import Account
from eth_account.messages import encode_typed_data
from .bundles import canonical_json_bytes
from .deployment import Deployment,sha256
from .releases import ReleaseService,CreateTask,CreateVersion,ReleaseError,now,identifier
from .verification import verify_task,verify_receipt,typed_receipt,acceptance_bundle,require

class ReleaseServiceV2(ReleaseService):
    def __init__(self,root:Path,*,deployment:Deployment,chain,signing_key,clock=None):
        kwargs={"clock":clock} if clock else {}
        super().__init__(root,chain=chain,signing_key=signing_key,**kwargs)
        self.deployment=deployment
        require(self._signer().address.lower()==deployment.receipt_signer,"Publisher signer differs from deployment")

    def _task(self,task_id):
        task=self._json(self._task_path(identifier(task_id)))
        verify_task(task,self.deployment)
        return task

    def _detail(self,task):
        return {**task,"attempts":self._attempts(task["task_id"])}

    def _version(self,task,version_id):
        verify_task(task,self.deployment)
        require(type(version_id) is int and 1<=version_id<=len(task["versions"]),"Version not found")
        version=task["versions"][version_id-1]
        directory=self._version_path(task["task_id"],version_id)
        require(self._safe(directory/"artifact.html").read_bytes()==version["artifact_text"].encode("utf-8"),"Stored artifact differs")
        require(self._safe(directory/"manifest.json").read_bytes()==version["manifest_text"].encode("utf-8"),"Stored manifest differs")
        return version

    def create_task(self,payload):
        fields=CreateTask.model_validate(payload).model_dump()
        with self._locked():
            require(len(list((self.root/"tasks").glob("*/task.json")))<100,"Local task limit reached")
            salt="0x"+secrets.token_hex(32)
            task_id=self.deployment.task_id(fields["owner"],salt)
            task={"schema":"cluetide.release-task.v2",**fields,"salt":salt,"task_id":task_id,
                "deployment":self.deployment.context(),"receipt_signer":self.deployment.receipt_signer,
                "target":self.deployment.target,"target_id":self.deployment.target_id(task_id),
                "created_at":now(),"version_count":0,"versions":[]}
            verify_task(task,self.deployment)
            self._save(self._task_path(task_id),task,immutable=True)
            return self._detail(task)

    def create_version(self,task_id,payload):
        value=CreateVersion.model_validate(payload)
        require(self._clock()<value.expires_at<=self._clock()+30*86400,"Deadline must be within 30 days")
        artifact=value.artifact_text.encode("utf-8")
        require(0<len(artifact)<=self.deployment.artifact_limit,"Artifact exceeds publication policy")
        with self._locked():
            task=self._task(task_id)
            require(len(task["versions"])<50,"Version limit reached")
            number=len(task["versions"])+1
            manifest={"schema":"cluetide.release-manifest.v2","deployment":self.deployment.context(),
                "task_id":task_id,"version_id":number,"parent_version_id":number-1,"summary":value.summary,
                "source_reference":value.source_reference,"test_evidence":value.test_evidence,
                "artifact":{"filename":"artifact.html","bytes":len(artifact),"sha256":sha256(artifact)},
                "target_id":task["target_id"],"operation":"publish_static","target":self.deployment.target,
                "policy_version":self.deployment.policy,"expires_at":value.expires_at}
            raw=canonical_json_bytes(manifest)
            version={"version_id":number,"parent_version_id":number-1,"manifest_hash":sha256(raw),
                "artifact_hash":sha256(artifact),"expires_at":value.expires_at,"created_at":now(),
                "manifest":manifest,"manifest_text":raw.decode(),"artifact_text":value.artifact_text,
                "bundle_url":f"/api/v2/tasks/{task_id}/acceptance"}
            task["versions"].append(version)
            task["version_count"]=number
            verify_task(task,self.deployment)
            directory=self._version_path(task_id,number)
            self._write(directory/"artifact.html",artifact,immutable=True)
            self._write(directory/"manifest.json",raw,immutable=True)
            self._save(self._task_path(task_id),task)
            return version

    def _check_authorization(self,task,version,attempt_id,tx_hash):
        return self.chain.verify_grant(task,version,attempt_id,tx_hash)

    def _verify_signature(self,task,version,attempt,envelope):
        try:
            receipt=verify_receipt(task,version,envelope,self.deployment)
            return receipt["attempt_id"]==attempt["attempt_id"] and receipt["authorization_tx"]==attempt["start_transaction_hash"]
        except (ValueError,KeyError,TypeError):
            return False

    def _finish(self,task,version,attempt,status):
        require(status in ("succeeded","failed"),"Only a final observation can be signed")
        directory=self._attempt_path(task["task_id"],attempt["attempt_id"])
        path=directory/"receipt.json"
        if path.exists():
            envelope=self._json(path)
            require(self._verify_signature(task,version,attempt,envelope),"Saved receipt failed verification")
        else:
            receipt={"schema":"cluetide.execution-receipt.v2",**self.deployment.context(),
                "task_id":task["task_id"],"version_id":version["version_id"],"attempt_id":attempt["attempt_id"],
                "manifest_hash":version["manifest_hash"],"artifact_hash":version["artifact_hash"],
                "output_hash":version["artifact_hash"] if status=="succeeded" else None,"target_id":task["target_id"],
                "operation":"publish_static","environment":"isolated-demo","executor":task["executor"],
                "receipt_signer":task["receipt_signer"],"authorization_tx":attempt["start_transaction_hash"],
                "status":status,"started_at":attempt["started_at"],"completed_at":now()}
            receipt_hash=sha256(canonical_json_bytes(receipt))
            signature=Account.sign_message(encode_typed_data(full_message=typed_receipt(receipt,receipt_hash)),self._key).signature
            envelope={"receipt":receipt,"receipt_hash":receipt_hash,"signature":"0x"+signature.hex().removeprefix("0x"),
                "signer":task["receipt_signer"],"signature_scheme":"EIP-712"}
            self._save(path,envelope,immutable=True)
        attempt.update(status=envelope["receipt"]["status"],stage="complete",completed_at=envelope["receipt"]["completed_at"],
            receipt_url=f"/api/v2/tasks/{task['task_id']}/receipt",artifact_url=f"/api/v2/tasks/{task['task_id']}/artifact")
        self._save(directory/"state.json",attempt)
        return attempt

    def export_acceptance(self,task_id,attempt_id):
        with self._locked():
            task=self._task(task_id)
            envelope=self._receipt(task,attempt_id)
            require(envelope["verification"]["signature_valid"],"Receipt is invalid")
            envelope={k:envelope[k] for k in ("receipt","receipt_hash","signature","signer","signature_scheme")}
            artifact=None
            if envelope["receipt"]["status"]=="succeeded":
                artifact=self._safe(self._target(task)/"releases"/attempt_id/"artifact.html").read_bytes()
            feedback=[self._json(p) for p in sorted((self.root/"feedback"/task_id).glob("*.json"))]
            return acceptance_bundle(task,envelope,self.deployment,artifact,feedback)
