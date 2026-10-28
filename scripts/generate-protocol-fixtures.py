"""Generate shared Python/TypeScript vectors and portable v2 schema documents."""
import json
from pathlib import Path
from eth_account.messages import encode_typed_data
from cluetide.bundles import canonical_json_bytes
from cluetide.deployment import Deployment,sha256
from cluetide.verification import typed_receipt,pack
from cluetide.release_exchange import read_zip,strict_json
ROOT=Path(__file__).resolve().parents[1]
d=Deployment.load(ROOT/'fixtures/v2/deployment.json')
entries=read_zip((ROOT/'fixtures/v2/eoa-acceptance-v3.zip').read_bytes())
t=strict_json(entries['task.json']);e=strict_json(entries['receipt.json']);v=t['versions'][-1]
vector={'deployment':d.to_dict(),'owner':t['owner'],'salt':t['salt'],'task_id':t['task_id'],
    'manifest_text':v['manifest_text'],'manifest_hash':v['manifest_hash'],'artifact_text':v['artifact_text'],'artifact_hash':v['artifact_hash'],
    'receipt':e,'typed_receipt':typed_receipt(e['receipt'],e['receipt_hash'])}
(ROOT/'fixtures/v2/shared-vectors.json').write_bytes(canonical_json_bytes(vector))
entries['published/artifact.html']+=b'!'
(ROOT/'fixtures/v2/tampered-acceptance.zip').write_bytes(pack(entries))
address={'type':'string','pattern':'^0x[0-9a-f]{40}$'}
digest={'type':'string','pattern':'^0x[0-9a-f]{64}$'}
integer={'type':'integer','minimum':1,'maximum':9007199254740991}
context={'type':'object','additionalProperties':False,'required':['protocol_version','chain_id','contract_address'],
    'properties':{'protocol_version':{'const':2},'chain_id':integer,'contract_address':address}}
def schema(name,properties):
    value={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':f'https://github.com/HNNUYUXUAN/cluetide-botchain/schemas/{name}.json',
        'title':name,'type':'object','required':list(properties),'properties':properties}
    (ROOT/f'schemas/{name}.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
schema('task-v2',{'schema':{'const':'cluetide.release-task.v2'},'deployment':context,'task_id':digest,'salt':digest,
    **{key:address for key in ('owner','proposer','reviewer','executor','receipt_signer')},'target_id':digest,'target':{'const':'demo-site'},
    'title':{'type':'string','minLength':1,'maxLength':160},'version_count':{'type':'integer','minimum':0,'maximum':50},'versions':{'type':'array','maxItems':50}})
schema('manifest-v2',{'schema':{'const':'cluetide.release-manifest.v2'},'deployment':context,'task_id':digest,'version_id':integer,
    'parent_version_id':{'type':'integer','minimum':0},'summary':{'type':'string','minLength':1,'maxLength':1000},
    'source_reference':{'type':'string','minLength':1,'maxLength':300},'test_evidence':{'type':'array','minItems':1,'maxItems':12,'items':{'type':'string','minLength':1,'maxLength':1000}},
    'artifact':{'type':'object','required':['filename','bytes','sha256'],'properties':{'filename':{'const':'artifact.html'},'bytes':{'type':'integer','minimum':1,'maximum':32768},'sha256':digest}},
    'target_id':digest,'operation':{'const':'publish_static'},'target':{'const':'demo-site'},'policy_version':{'const':'cluetide.demo-release.v2'},'expires_at':integer})
schema('receipt-v2',{'schema':{'const':'cluetide.execution-receipt.v2'},**context['properties'],'task_id':digest,'version_id':integer,
    'attempt_id':{'type':'string','pattern':'^[1-9][0-9]*$'},'manifest_hash':digest,'artifact_hash':digest,'target_id':digest,'executor':address,'receipt_signer':address,
    'authorization_tx':digest,'status':{'enum':['succeeded','failed']},'output_hash':{'oneOf':[digest,{'type':'null'}]},
    'operation':{'const':'publish_static'},'environment':{'const':'isolated-demo'},'started_at':{'type':'string'},'completed_at':{'type':'string'}})
schema('feedback-v2',{'schema':{'const':'cluetide.review-feedback.v2'},'deployment':context,'task_id':digest,'version_id':integer,'manifest_hash':digest,
    'reviewer':address,'correction_transaction_hash':digest,'content_hash':digest,'reason':{'type':'string','minLength':1,'maxLength':4000},
    'acceptance_conditions':{'type':'array','maxItems':12,'items':{'type':'string','minLength':1,'maxLength':1000}},
    'signature_scheme':{'enum':['EIP-712','ERC-1271']},'signature':{'type':'string','pattern':'^0x[0-9a-f]+$','maxLength':32770}})
schema('acceptance-v2',{'schema':{'const':'cluetide.acceptance-bundle.v2'},'deployment':context,'task_id':digest,'version_id':integer,
    'attempt_id':{'type':'string','pattern':'^[1-9][0-9]*$'},'observed_at':{'type':'string'},'files':{'type':'array','minItems':3,'items':{'type':'object','required':['path','bytes','sha256'],'properties':{'path':{'type':'string'},'bytes':{'type':'integer','minimum':0},'sha256':digest}}}})
print('Generated v2 schemas, cross-language vectors and one-byte tamper sample')
