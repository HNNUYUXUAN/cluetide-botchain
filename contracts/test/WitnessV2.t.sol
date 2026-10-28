// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;
import "../ClueTideReleaseWitnessV2.sol";
interface Vm {function prank(address) external; function chainId(uint256) external;}
contract SequenceHandler {
    Vm constant vm=Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    ClueTideReleaseWitnessV2 public witness;
    bytes32 public task;
    bytes32 constant M=keccak256("manifest");
    bytes32 constant A=keccak256("artifact");
    bool public valid=true;
    mapping(uint256=>uint256) public consumptions;
    constructor() {
        witness=new ClueTideReleaseWitnessV2();
        task=witness.deriveTaskId(address(this),bytes32(uint256(1)));
        witness.createTask(task,bytes32(uint256(1)),address(1),address(2),address(3),address(4),M);
    }
    function step(uint256 seed) external {
        uint256 version=witness.getTask(task).versionCount;
        uint256 action=seed%7;
        if(version==0 || action==0){
            vm.prank(address(1));witness.proposeVersion(task,version,M,A,uint64(block.timestamp+86400));return;
        }
        ClueTideReleaseWitnessV2.VersionRecord memory state=witness.getVersion(task,version);
        bytes memory callData;address sender;
        if(action==1){sender=address(2);callData=abi.encodeCall(witness.approve,(task,version,M,A,state.deadline));}
        if(action==2){sender=address(2);callData=abi.encodeCall(witness.revoke,(task,version));}
        if(action==3){sender=address(2);callData=abi.encodeCall(witness.requestCorrection,(task,version));}
        if(action==4){sender=address(3);callData=abi.encodeCall(witness.consume,(task,version,M,A));}
        if(action==5){sender=address(99);callData=abi.encodeCall(witness.approve,(task,version,M,A,state.deadline));}
        if(action==6){sender=address(3);callData=abi.encodeCall(witness.consume,(task,version,bytes32(seed),A));}
        bytes32 beforeHash=keccak256(abi.encode(witness.getTask(task),state));
        vm.prank(sender);(bool ok,)=address(witness).call(callData);
        if(action==4 && ok){consumptions[version]++;if(consumptions[version]>1)valid=false;}
        if(action==5 || action==6){if(ok || beforeHash!=keccak256(abi.encode(witness.getTask(task),witness.getVersion(task,version))))valid=false;}
    }
}
contract WitnessV2Test {
    Vm constant vm=Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    SequenceHandler handler;
    function setUp() public {handler=new SequenceHandler();}
    function targetContracts() public view returns(address[] memory values){values=new address[](1);values[0]=address(handler);}
    function invariantAuthorizationAndSingleConsumption() public view {require(handler.valid(),"authorization invariant violated");}
    function testFuzzNamespace(address owner,bytes32 salt,uint64 chain) public {
        ClueTideReleaseWitnessV2 w=handler.witness();bytes32 id=w.deriveTaskId(owner,salt);
        require(id==keccak256(abi.encode(block.chainid,address(w),owner,salt)));
        if(owner!=address(99))require(id!=w.deriveTaskId(address(99),salt));
        ClueTideReleaseWitnessV2 other=new ClueTideReleaseWitnessV2();require(id!=other.deriveTaskId(owner,salt));
        if(chain!=block.chainid){vm.chainId(chain);require(id!=w.deriveTaskId(owner,salt));}
    }
    function testGasLifecycle() public {
        handler.step(0);handler.step(1);handler.step(4);
        require(handler.witness().getVersion(handler.task(),1).decision==4);
        handler.step(4);require(handler.consumptions(1)==1);
    }
    function testFuzzRandomSequence(uint256 seed) public {
        for(uint256 i;i<32;i++){seed=uint256(keccak256(abi.encode(seed,i)));handler.step(seed);}require(handler.valid());
    }
}
