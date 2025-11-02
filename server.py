"""
Relay Server for Solo PoW Blockchain
Maintains the official blockchain and provides API endpoints
"""

import json
import os
import hashlib
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

BLOCKCHAIN_FILE = "solopowharzblockchain.json"
USERS_FILE = "miners_accounts.json"
GENESIS_REWARD = 1000
HALVING_INTERVAL = 50


class Blockchain:
    def __init__(self):
        self.chain = []
        self.load_blockchain()
        if not self.chain:
            self.create_genesis_block()

    def create_genesis_block(self):
        """Create the genesis block instantly"""
        genesis = {
            "index": 0,
            "previous_hash": "0" * 64,  # 64 zeros for SHA256
            "timestamp": int(time.time()),
            "nonce": 0,
            "miner_id": "genesis",
            "reward": GENESIS_REWARD,
            "hash": self.calculate_hash(0, "0" * 64, int(time.time()), 0, "genesis", GENESIS_REWARD)
        }
        self.chain.append(genesis)
        self.save_blockchain()
        print(f"Genesis block created: {genesis['hash']}")

    def calculate_hash(self, index, previous_hash, timestamp, nonce, miner_id, reward):
        """Calculate SHA256 hash of block"""
        block_string = f"{index}{previous_hash}{timestamp}{nonce}{miner_id}{reward}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def get_latest_block(self):
        """Get the latest block in the chain"""
        return self.chain[-1] if self.chain else None

    def get_difficulty(self):
        """Calculate current difficulty based on recent block times to maintain ~5 min block time"""
        if len(self.chain) < 2:
            return 3  # Start with 3 leading zeros
        
        # Look at last 10 blocks (or fewer if chain is shorter) to calculate average time
        lookback = min(10, len(self.chain) - 1)
        if lookback < 2:
            return 3
        
        recent_blocks = self.chain[-lookback:]
        
        # Calculate average time between blocks
        time_differences = []
        for i in range(1, len(recent_blocks)):
            time_diff = recent_blocks[i]["timestamp"] - recent_blocks[i-1]["timestamp"]
            time_differences.append(time_diff)
        
        if not time_differences:
            return 3
        
        avg_time = sum(time_differences) / len(time_differences)
        target_time = 300  # 5 minutes in seconds
        
        # Get current difficulty estimate from last few blocks
        # Use minimum leading zeros as baseline (all blocks met at least this requirement)
        recent_difficulties = [self.count_leading_zeros(b["hash"]) for b in recent_blocks[-5:]]
        if not recent_difficulties:
            current_difficulty = 3
        else:
            # Use minimum as baseline (conservative, but accurate)
            # All blocks had at least this many leading zeros
            min_difficulty = min(recent_difficulties)
            # Use average rounded up for smoother transitions
            avg_difficulty = sum(recent_difficulties) / len(recent_difficulties)
            current_difficulty = max(int(avg_difficulty), min_difficulty)
        
        # Adjust difficulty based on average block time
        # If blocks are too fast, increase difficulty
        # If blocks are too slow, decrease difficulty
        if avg_time < target_time * 0.7:  # Much faster than target
            new_difficulty = min(current_difficulty + 2, 6)
        elif avg_time < target_time * 0.85:  # Faster than target
            new_difficulty = min(current_difficulty + 1, 6)
        elif avg_time > target_time * 1.5:  # Much slower than target
            new_difficulty = max(current_difficulty - 2, 3)
        elif avg_time > target_time * 1.15:  # Slower than target
            new_difficulty = max(current_difficulty - 1, 3)
        else:
            new_difficulty = current_difficulty  # Keep current difficulty
        
        return new_difficulty

    def count_leading_zeros(self, hash_string):
        """Count leading zeros in hash"""
        count = 0
        for char in hash_string:
            if char == '0':
                count += 1
            else:
                break
        return count

    def calculate_reward(self, block_index):
        """Calculate reward with halving every 50 blocks"""
        halvings = block_index // HALVING_INTERVAL
        reward = GENESIS_REWARD
        for _ in range(halvings):
            reward = reward // 2
        return reward

    def validate_block(self, block):
        """Validate a submitted block"""
        latest = self.get_latest_block()
        
        # Check index is sequential
        if block["index"] != latest["index"] + 1:
            return False, f"Invalid index. Expected {latest['index'] + 1}, got {block['index']}"
        
        # Check previous hash matches
        if block["previous_hash"] != latest["hash"]:
            return False, "Previous hash does not match latest block hash"
        
        # Check difficulty
        difficulty = self.get_difficulty()
        block_hash = block.get("hash")
        if not block_hash:
            # Calculate hash if not provided
            block_hash = self.calculate_hash(
                block["index"],
                block["previous_hash"],
                block["timestamp"],
                block["nonce"],
                block["miner_id"],
                block["reward"]
            )
        
        leading_zeros = self.count_leading_zeros(block_hash)
        if leading_zeros < difficulty:
            return False, f"Hash does not meet difficulty requirement. Need {difficulty} leading zeros, got {leading_zeros}"
        
        # Verify hash is correct
        calculated_hash = self.calculate_hash(
            block["index"],
            block["previous_hash"],
            block["timestamp"],
            block["nonce"],
            block["miner_id"],
            block["reward"]
        )
        if calculated_hash != block_hash:
            return False, "Block hash verification failed"
        
        # Check for duplicate block index (already in chain)
        for existing_block in self.chain:
            if existing_block["index"] == block["index"]:
                return False, f"Block with index {block['index']} already exists"
        
        # Verify reward is correct
        expected_reward = self.calculate_reward(block["index"])
        if block["reward"] != expected_reward:
            return False, f"Invalid reward. Expected {expected_reward}, got {block['reward']}"
        
        return True, "Valid block"

    def add_block(self, block):
        """Add a valid block to the chain"""
        block["hash"] = self.calculate_hash(
            block["index"],
            block["previous_hash"],
            block["timestamp"],
            block["nonce"],
            block["miner_id"],
            block["reward"]
        )
        self.chain.append(block)
        self.save_blockchain()
        return block

    def save_blockchain(self):
        """Save blockchain to JSON file"""
        with open(BLOCKCHAIN_FILE, 'w') as f:
            json.dump(self.chain, f, indent=2)

    def load_blockchain(self):
        """Load blockchain from JSON file"""
        if os.path.exists(BLOCKCHAIN_FILE):
            try:
                with open(BLOCKCHAIN_FILE, 'r') as f:
                    self.chain = json.load(f)
                print(f"Loaded {len(self.chain)} blocks from blockchain.json")
            except Exception as e:
                print(f"Error loading blockchain: {e}")
                self.chain = []
        else:
            self.chain = []


# Initialize blockchain
blockchain = Blockchain()


class UserManager:
    """Manages miner accounts - username only, miner_id derived from username"""
    
    def __init__(self):
        self.users = {}
        self.load_users()
    
    def load_users(self):
        """Load users from JSON file"""
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r') as f:
                    self.users = json.load(f)
                print(f"Loaded {len(self.users)} user accounts")
            except Exception as e:
                print(f"Error loading users: {e}")
                self.users = {}
        else:
            self.users = {}
    
    def save_users(self):
        """Save users to JSON file"""
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def get_miner_id_from_username(self, username):
        """Generate deterministic miner_id from username using SHA256"""
        # Hash username to get consistent miner_id (64 char hex string)
        return hashlib.sha256(username.encode()).hexdigest()
    
    def register_or_login_user(self, username):
        """Register or login user - miner_id is derived from username"""
        username = username.strip()
        
        if not username:
            return False, "Username cannot be empty"
        
        if len(username) < 3:
            return False, "Username must be at least 3 characters"
        
        # Generate miner_id from username (deterministic)
        miner_id = self.get_miner_id_from_username(username)
        
        # Register user if not exists
        if username not in self.users:
            self.users[username] = {
                "miner_id": miner_id,
                "created_at": int(time.time())
            }
            self.save_users()
            return True, miner_id
        
        # User exists, return their miner_id
        return True, self.users[username]["miner_id"]
    
    def get_miner_id(self, username):
        """Get miner_id for a user"""
        if username in self.users:
            return self.users[username]["miner_id"]
        # Generate on-the-fly if not registered yet
        return self.get_miner_id_from_username(username)


# Initialize user manager
user_manager = UserManager()

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1434624818044473430/Qb6kRS1QmR-KajodHDcKKQJCOX-TKXuIBwsOKIY1o4OXTVkiLYjdbyDD-oqN87dGvUpW"

def send_discord_notification(block, nickname):
    """Send Discord webhook notification when block is mined"""
    # Calculate difficulty that was required for this block
    difficulty = blockchain.count_leading_zeros(block["hash"])
    
    embed = {
        "title": f"BLOCK {block['index']} MINED!",
        "color": 15105570,  # Orange color
        "fields": [
            {"name": "Hash", "value": block["hash"], "inline": False},
            {"name": "Previous Hash", "value": block["previous_hash"], "inline": False},
            {"name": "Difficulty", "value": f"{difficulty} leading zeros", "inline": True},
            {"name": "Reward", "value": f"{block['reward']} GCoins", "inline": True},
            {"name": "Mined by", "value": nickname, "inline": True},
            {"name": "Miner ID", "value": block["miner_id"][:16] + "...", "inline": True}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print(f"Discord notification sent for block {block['index']}")
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")


@app.route('/api/latest', methods=['GET'])
def get_latest_block():
    """Get the latest block and current difficulty"""
    latest = blockchain.get_latest_block()
    if not latest:
        return jsonify({"error": "No blocks found"}), 404
    
    difficulty = blockchain.get_difficulty()
    reward = blockchain.calculate_reward(latest["index"] + 1)
    
    return jsonify({
        "latest_block": latest,
        "difficulty": difficulty,
        "next_reward": reward
    })


@app.route('/api/submit', methods=['POST'])
def submit_block():
    """Submit a newly mined block"""
    try:
        block_data = request.json
        nickname = request.json.get("nickname", "Unknown")
        
        # Validate block
        is_valid, message = blockchain.validate_block(block_data)
        
        if not is_valid:
            return jsonify({"success": False, "error": message}), 400
        
        # Add block to chain
        block = blockchain.add_block(block_data)
        
        # Send Discord notification
        send_discord_notification(block, nickname)
        
        return jsonify({
            "success": True,
            "message": f"Block {block['index']} added successfully",
            "block": block
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/chain', methods=['GET'])
def get_chain():
    """Get the full blockchain (optional endpoint)"""
    return jsonify({"chain": blockchain.chain, "length": len(blockchain.chain)})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get comprehensive blockchain statistics"""
    latest = blockchain.get_latest_block()
    if not latest:
        return jsonify({"error": "No blocks found"}), 404
    
    # Calculate total GCoins mined
    total_gcoins = 0
    for block in blockchain.chain:
        total_gcoins += block.get("reward", 0)
    
    # Calculate difficulty stats
    difficulties = []
    for block in blockchain.chain[1:]:  # Skip genesis
        difficulties.append(blockchain.count_leading_zeros(block["hash"]))
    
    avg_difficulty = sum(difficulties) / len(difficulties) if difficulties else 0
    min_difficulty = min(difficulties) if difficulties else 0
    max_difficulty = max(difficulties) if difficulties else 0
    
    # Calculate block times
    block_times = []
    for i in range(1, len(blockchain.chain)):
        time_diff = blockchain.chain[i]["timestamp"] - blockchain.chain[i-1]["timestamp"]
        block_times.append(time_diff)
    
    avg_block_time = sum(block_times) / len(block_times) if block_times else 0
    
    # Count blocks per miner
    miner_stats = {}
    for block in blockchain.chain[1:]:  # Skip genesis
        miner_id = block.get("miner_id", "unknown")
        if miner_id not in miner_stats:
            miner_stats[miner_id] = {"blocks": 0, "rewards": 0}
        miner_stats[miner_id]["blocks"] += 1
        miner_stats[miner_id]["rewards"] += block.get("reward", 0)
    
    current_difficulty = blockchain.get_difficulty()
    current_reward = blockchain.calculate_reward(latest["index"])
    next_reward = blockchain.calculate_reward(latest["index"] + 1)
    
    return jsonify({
        "total_blocks": len(blockchain.chain),
        "latest_index": latest["index"],
        "current_difficulty": current_difficulty,
        "difficulty_stats": {
            "current": current_difficulty,
            "average": round(avg_difficulty, 2),
            "min": min_difficulty,
            "max": max_difficulty
        },
        "rewards": {
            "current": current_reward,
            "next": next_reward,
            "total_gcoins_mined": total_gcoins,
            "halving_count": latest["index"] // 50
        },
        "block_times": {
            "average_seconds": round(avg_block_time, 2),
            "average_minutes": round(avg_block_time / 60, 2)
        },
        "top_miners": dict(sorted(
            miner_stats.items(),
            key=lambda x: x[1]["blocks"],
            reverse=True
        )[:10]),  # Top 10 miners
        "total_unique_miners": len(miner_stats)
    })


@app.route('/api/login', methods=['POST'])
def login():
    """Login/Register miner - username only, miner_id derived from username"""
    try:
        data = request.json
        username = data.get("username", "").strip()
        
        if not username:
            return jsonify({"success": False, "error": "Username is required"}), 400
        
        if len(username) < 3:
            return jsonify({"success": False, "error": "Username must be at least 3 characters"}), 400
        
        success, miner_id = user_manager.register_or_login_user(username)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Login successful",
                "miner_id": miner_id,
                "username": username
            })
        else:
            return jsonify({"success": False, "error": miner_id}), 400
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    print("Starting Relay Server...")
    print(f"Blockchain initialized with {len(blockchain.chain)} blocks")
    print("API Endpoints:")
    print("  GET  /api/latest  - Get latest block info")
    print("  POST /api/submit  - Submit a new block")
    print("  GET  /api/chain   - Get full blockchain")
    print("  GET  /api/stats   - Get blockchain stats")
    print("  POST /api/login   - Login/Register miner (username only)")
    app.run(host='0.0.0.0', port=5000, debug=True)

