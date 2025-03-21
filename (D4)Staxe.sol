pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

contract Staxe {
    using SafeMath for uint256;

    // Token interfaces for staking and rewards
    IERC20 public stakingToken;  // Token to be staked
    IERC20 public rewardToken;   // Token distributed as rewards

    // Staking state
    uint256 public totalStaked;                    // Total amount of tokens staked
    mapping(address => uint256) public stakedBalances;  // Staked amount per user

    // Reward state
    uint256 public rewardRate;                     // Reward rate (tokens per second)
    uint256 public lastUpdateTime;                 // Last time rewards were updated
    uint256 public rewardPerTokenStored;           // Accumulated reward per token
    mapping(address => uint256) public userRewardPerTokenPaid;  // Reward per token paid to user
    mapping(address => uint256) public rewards;    // Pending rewards per user

    // Constructor to initialize tokens and reward rate
    constructor(address _stakingToken, address _rewardToken, uint256 _rewardRate) {
        stakingToken = IERC20(_stakingToken);
        rewardToken = IERC20(_rewardToken);
        rewardRate = _rewardRate;
        lastUpdateTime = block.timestamp;
    }

    // Stake tokens into the contract
    function stake(uint256 amount) external {
        require(amount > 0, "Cannot stake 0");
        updateReward(msg.sender);
        stakingToken.transferFrom(msg.sender, address(this), amount);
        stakedBalances[msg.sender] = stakedBalances[msg.sender].add(amount);
        totalStaked = totalStaked.add(amount);
    }

    // Unstake tokens from the contract
    function unstake(uint256 amount) external {
        require(amount > 0, "Cannot unstake 0");
        require(stakedBalances[msg.sender] >= amount, "Insufficient staked amount");
        updateReward(msg.sender);
        stakedBalances[msg.sender] = stakedBalances[msg.sender].sub(amount);
        totalStaked = totalStaked.sub(amount);
        stakingToken.transfer(msg.sender, amount);
    }

    // Claim accumulated rewards
    function claimReward() external {
        updateReward(msg.sender);
        uint256 reward = rewards[msg.sender];
        if (reward > 0) {
            rewards[msg.sender] = 0;
            rewardToken.transfer(msg.sender, reward);
        }
    }

    // View accumulated reward per token
    function rewardPerToken() public view returns (uint256) {
        if (totalStaked == 0) {
            return rewardPerTokenStored;
        }
        return rewardPerTokenStored.add(
            block.timestamp.sub(lastUpdateTime).mul(rewardRate).mul(1e18).div(totalStaked)
        );
    }

    // View earned rewards for an account
    function earned(address account) public view returns (uint256) {
        return stakedBalances[account]
            .mul(rewardPerToken().sub(userRewardPerTokenPaid[account]))
            .div(1e18)
            .add(rewards[account]);
    }

    // Internal function to update rewards
    function updateReward(address account) internal {
        rewardPerTokenStored = rewardPerToken();
        lastUpdateTime = block.timestamp;
        if (account != address(0)) {
            rewards[account] = earned(account);
            userRewardPerTokenPaid[account] = rewardPerTokenStored;
        }
    }
}
