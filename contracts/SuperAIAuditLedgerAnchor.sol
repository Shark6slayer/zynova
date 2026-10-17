// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SuperAIAuditLedgerAnchor
 * @dev Minimal, non-upgradeable contract for anchoring cryptographic checkpoint commitments
 * from the SUPER_AI private audit ledger to an EVM-compatible public blockchain.
 *
 * Security properties:
 * - Zero PII/User Data: Stores strictly 32-byte SHA-256 hashes, sequence numbers, and version tags.
 * - Access Control: Only the authorized anchoring relayer can record commitments.
 * - Replay & Reordering Defense: Sequence numbers must strictly increase.
 * - Non-financial: No tokens, payable methods, or funds accepted.
 */
contract SuperAIAuditLedgerAnchor {
    address public owner;
    address public relayer;
    uint256 public latestAnchoredSequence;
    bytes32 public latestAnchoredHash;
    uint256 public totalAnchorsCount;

    struct CheckpointAnchor {
        uint256 sequence;
        bytes32 checkpointHash;
        string schemaVersion;
        uint256 timestamp;
        address submitter;
    }

    // Mapping from sequence number to CheckpointAnchor
    mapping(uint256 => CheckpointAnchor) public checkpoints;

    // Events emitted for independent verifier log indexing
    event CheckpointAnchored(
        uint256 indexed sequence,
        bytes32 indexed checkpointHash,
        string schemaVersion,
        uint256 timestamp,
        address indexed submitter
    );

    event RelayerUpdated(address indexed previousRelayer, address indexed newRelayer);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can perform this action");
        _;
    }

    modifier onlyAuthorized() {
        require(msg.sender == owner || msg.sender == relayer, "Not authorized to anchor checkpoints");
        _;
    }

    constructor(address _relayer) {
        require(_relayer != address(0), "Relayer cannot be zero address");
        owner = msg.sender;
        relayer = _relayer;
    }

    /**
     * @notice Records a tamper-evident audit ledger checkpoint commitment.
     * @param sequence Monotonically increasing ledger sequence number.
     * @param checkpointHash 32-byte SHA-256 hash of the Phase 10 checkpoint.
     * @param schemaVersion Version string of the ledger schema (e.g. "1.0.0").
     */
    function anchorCheckpoint(
        uint256 sequence,
        bytes32 checkpointHash,
        string calldata schemaVersion
    ) external onlyAuthorized {
        require(sequence > latestAnchoredSequence, "Sequence must be strictly greater than latest anchored sequence");
        require(checkpointHash != bytes32(0), "Checkpoint hash cannot be zero");
        require(bytes(schemaVersion).length > 0 && bytes(schemaVersion).length <= 16, "Invalid schema version length");

        latestAnchoredSequence = sequence;
        latestAnchoredHash = checkpointHash;
        totalAnchorsCount += 1;

        checkpoints[sequence] = CheckpointAnchor({
            sequence: sequence,
            checkpointHash: checkpointHash,
            schemaVersion: schemaVersion,
            timestamp: block.timestamp,
            submitter: msg.sender
        });

        emit CheckpointAnchored(
            sequence,
            checkpointHash,
            schemaVersion,
            block.timestamp,
            msg.sender
        );
    }

    /**
     * @notice Retrieves verified checkpoint record for a given sequence.
     */
    function getCheckpoint(uint256 sequence) external view returns (
        uint256 seq,
        bytes32 cpHash,
        string memory version,
        uint256 ts,
        address submitter
    ) {
        CheckpointAnchor memory cp = checkpoints[sequence];
        require(cp.sequence != 0, "Checkpoint not found");
        return (cp.sequence, cp.checkpointHash, cp.schemaVersion, cp.timestamp, cp.submitter);
    }

    /**
     * @notice Updates authorized relayer address.
     */
    function setRelayer(address _newRelayer) external onlyOwner {
        require(_newRelayer != address(0), "New relayer cannot be zero address");
        emit RelayerUpdated(relayer, _newRelayer);
        relayer = _newRelayer;
    }

    /**
     * @notice Transfers contract ownership.
     */
    function transferOwnership(address _newOwner) external onlyOwner {
        require(_newOwner != address(0), "New owner cannot be zero address");
        emit OwnershipTransferred(owner, _newOwner);
        owner = _newOwner;
    }
}
