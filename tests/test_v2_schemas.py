import json
from pathlib import Path
import jsonschema
from cluetide.deployment import Deployment,sha256
from cluetide.verification import verify,recover_eoa
from cluetide.release_exchange import read_zip,strict_json
ROOT=Path(__file__).resolve().parents[1]
def test_shared_vectors():
    v=json.loads((ROOT/'fixtures/v2/shared-vectors.json').read_text(encoding='utf-8'))
    d=Deployment(**v['deployment'])
    assert d.task_id(v['owner'],v['salt'])==v['task_id']
    assert sha256(v['manifest_text'].encode())==v['manifest_hash']
    assert recover_eoa(v['typed_receipt'],v['receipt']['signature'])==d.receipt_signer
def test_schemas_and_portable_samples():
    d=Deployment.load(ROOT/'fixtures/v2/deployment.json')
    for mode in ('eoa','safe'):
        payload=(ROOT/f'fixtures/v2/{mode}-acceptance-v3.zip').read_bytes()
        assert verify(payload,deployment=d)['status']=='verified'
        entries=read_zip(payload)
        documents=[('task',strict_json(entries['task.json'])),('receipt',strict_json(entries['receipt.json'])['receipt']),('acceptance',strict_json(entries['acceptance.json']))]
        documents += [('manifest',strict_json(value)) for name,value in entries.items() if name.endswith('/manifest.json')]
        documents += [('feedback',item) for item in strict_json(entries['feedback.json'])]
        for name,document in documents:
            jsonschema.validate(document,json.loads((ROOT/f'schemas/{name}-v2.json').read_text()))
