import copy
import json
from pathlib import Path
import pytest
from eth_tester import EthereumTester,PyEVMBackend
from web3 import Web3,EthereumTesterProvider
from cluetide.chain_v2 import WitnessChain,artifact_v2,hex_value
from cluetide.deployment import Deployment,sha256
from cluetide.service_v2 import ReleaseServiceV2
from cluetide.verification import verify,pack,verify_task
from cluetide.release_exchange import read_zip
from cluetide.bundles import canonical_json_bytes

@pytest.fixture
def system(tmp_path):
    tester=EthereumTester(PyEVMBackend());w=Web3(EthereumTesterProvider(tester));a=artifact_v2()
    factory=w.eth.contract(abi=a['abi'],bytecode=a['bytecode'])
    receipt=w.eth.wait_for_transaction_receipt(factory.constructor().transact({'from':w.eth.accounts[0]}))
    d=Deployment(chain_id=w.eth.chain_id,contract_address=receipt.contractAddress,runtime_sha256=sha256(bytes(w.eth.get_code(receipt.contractAddress))),receipt_signer=w.eth.accounts[4],rpc_url='http://127.0.0.1:1',confirmations=1)
    chain=WitnessChain(d,w)
    service=ReleaseServiceV2(tmp_path,deployment=d,chain=chain,signing_key=tester.backend.account_keys[4],clock=lambda:w.eth.get_block('latest').timestamp)
    task=service.create_task(dict(title='Independent release',**{key:w.eth.accounts[i] for i,key in enumerate(('owner','proposer','reviewer','executor'))}))
    def send(action,version=None,envelope=None):
        sender={'create_task':0,'propose_version':1,'approve':2,'request_correction':2,'consume':3,'record_receipt':3}[action]
        tx=chain.function(action,task,version,envelope).transact({'from':w.eth.accounts[sender]})
        w.eth.wait_for_transaction_receipt(tx)
        chain.verify_action(action,task,version,hex_value(tx),envelope=envelope)
        return hex_value(tx)
    send('create_task')
    version=service.create_version(task['task_id'],dict(summary='Version one',source_reference='local fixture',test_evidence=['pytest'],artifact_text='<h1>Exact bytes</h1>',expires_at=w.eth.get_block('latest').timestamp+3600))
    task=service.get_task(task['task_id']);send('propose_version',version);send('approve',version)
    tx=send('consume',version)
    request=dict(version_id=1,attempt_id='1',start_transaction_hash=tx)
    return service,chain,d,task,version,request,send

def publish(system):
    s,c,d,t,v,r,send=system
    assert s.execute(t['task_id'],r)['status']=='succeeded'
    send('record_receipt',v,s.receipt('1',t['task_id']))
    return s.export_acceptance(t['task_id'],'1')

def test_v2_offline_separates_observation(system,monkeypatch):
    bundle=publish(system)
    monkeypatch.setattr(Web3,'HTTPProvider',lambda *a,**k:pytest.fail('Offline verifier attempted network access'))
    result=verify(bundle,deployment=system[2])
    assert result['status']=='verified' and result['checks']['eoa_signature']=='verified'
    assert result['checks']['chain_authorization']=='not_checked' and not result['live_artifact_verified']
    with pytest.raises(ValueError,match='trusted deployment'):
        verify(bundle)

@pytest.mark.parametrize('mutation',['byte','signature','duplicate','path','copy','deployment','signer','unknown','inventory'])
def test_v2_rejects_tampering(system,mutation):
    entries=read_zip(publish(system));d=system[2]
    if mutation=='byte':entries['published/artifact.html']+=b'!'
    if mutation=='signature':
        r=json.loads(entries['receipt.json']);r['signature']='0x'+'00'*65;entries['receipt.json']=canonical_json_bytes(r)
    if mutation=='duplicate':entries['acceptance.json']=entries['acceptance.json'].replace(b'{',b'{"schema":"ambiguous",',1)
    if mutation=='path':entries['../outside']=b'bad'
    if mutation=='copy':entries['versions/1/manifest.json']+=b' '
    if mutation=='deployment':d=Deployment(**{**d.to_dict(),'contract_address':'0x'+'11'*20})
    if mutation=='signer':d=Deployment(**{**d.to_dict(),'receipt_signer':'0x'+'11'*20})
    if mutation=='unknown':
        r=json.loads(entries['receipt.json']);r['receipt']['status']='unknown';entries['receipt.json']=canonical_json_bytes(r)
    if mutation=='inventory':
        r=json.loads(entries['acceptance.json']);r['files'].append(r['files'][0]);entries['acceptance.json']=canonical_json_bytes(r)
    with pytest.raises((ValueError,KeyError)):
        verify(pack(entries),deployment=d)

@pytest.mark.parametrize('point',['before_stage','after_target','before_receipt','after_receipt'])
def test_crash_recovery_does_not_repeat_publication(system,monkeypatch,point):
    s,c,d,t,v,r,send=system
    writes=[];switch=s._switch_target;save=s._save;finish=s._finish;write=s._write
    def counted(task,marker):
        writes.append(marker);switch(task,marker)
        if point=='after_target':raise RuntimeError('simulated crash after target write')
    monkeypatch.setattr(s,'_switch_target',counted)
    if point=='before_stage':
        def broken(path,payload,**kwargs):
            if path.name=='artifact.html':raise OSError('simulated staging failure')
            return write(path,payload,**kwargs)
        monkeypatch.setattr(s,'_write',broken)
    if point=='before_receipt':monkeypatch.setattr(s,'_finish',lambda *args:(_ for _ in ()).throw(OSError('simulated signer unavailable')))
    if point=='after_receipt':
        def failed_save(path,payload,**kwargs):
            save(path,payload,**kwargs)
            if path.name=='receipt.json':raise OSError('simulated post-receipt crash')
        monkeypatch.setattr(s,'_save',failed_save)
    first=s.execute(t['task_id'],r)
    resumed=ReleaseServiceV2(s.root,deployment=d,chain=c,signing_key=s._key,clock=s._clock)
    monkeypatch.setattr(resumed,'_switch_target',lambda *a:pytest.fail('Recovery published again'))
    second=resumed.execute(t['task_id'],r)
    assert second['status']==('failed' if point=='before_stage' else 'succeeded')
    assert len(writes)==(0 if point=='before_stage' else 1)
    assert resumed.execute(t['task_id'],r)['status']==second['status']

def test_historical_v1_still_verifies():
    path=Path(__file__).resolve().parents[1]/'evidence/complete-mainnet/acceptance-v3.zip'
    result=verify(path.read_bytes())
    assert result['status']=='verified' and result['current_chain_verified'] is False

def test_rpc_unavailable_is_unverified(system):
    result=verify(publish(system),deployment=system[2],online=True)
    assert result['status']=='incomplete' and result['checks']['chain_authorization']=='unverified'
