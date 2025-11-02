# GCoin Solo PoW Blockchain

A Python-based solo Proof-of-Work blockchain system with a central relay server and GUI miner client.

## Features

- **Solo Mining**: Each miner works independently on their own blocks
- **Dynamic Difficulty**: Automatically adjusts between 3-6 leading zeros to maintain ~5 minute block times
- **Reward System**: Starts at 1000 GCoins, halves every 50 blocks
- **GUI Miner**: Bitcoin Core-style interface built with tkinter
- **Relay Server**: Central server maintains the official blockchain
- **Discord Integration**: Sends webhook notifications when blocks are mined
- **Persistent Storage**: Blockchain stored in JSON format

## Installation

1. Install Python 3.7 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Relay Server

```bash
python server.py
```

The server will:
- Create a genesis block automatically
- Start on `http://localhost:5000`
- Save blockchain to `blockchain.json`

### Starting the Miner Client

```bash
python miner.py
```

The miner will:
- Open a GUI window
- Allow you to enter a nickname
- Connect to the relay server at `http://localhost:5000`
- Start mining blocks when you click "Start Mining"

## API Endpoints

- `GET /api/latest` - Get latest block info and current difficulty
- `POST /api/submit` - Submit a newly mined block
- `GET /api/chain` - Get the full blockchain
- `GET /api/stats` - Get blockchain statistics

## Block Structure

Each block contains:
- `index`: Block number
- `previous_hash`: Hash of the previous block
- `timestamp`: Unix timestamp
- `nonce`: Proof-of-work nonce
- `miner_id`: Unique ID of the miner
- `reward`: GCoin reward for this block
- `hash`: SHA256 hash of the block

## Mining

- Miners check the relay server every 6 seconds for the latest block
- Mining uses SHA256 hashing
- Difficulty dynamically adjusts to maintain ~5 minute block times
- Only the first valid block submission gets the reward

## Configuration

Edit `miner.py` to change:
- `RELAY_SERVER_URL`: Server address (default: `http://localhost:5000`)
- `CHECK_INTERVAL`: Server check interval in seconds (default: 6)

Edit `server.py` to change:
- `GENESIS_REWARD`: Starting reward (default: 1000)
- `HALVING_INTERVAL`: Blocks between halvings (default: 50)
- `DISCORD_WEBHOOK_URL`: Discord webhook URL

## Notes

- The genesis block is created automatically when the server starts
- Blocks are validated for correct previous hash, difficulty, and reward
- Duplicate block indices are rejected
- The miner will automatically update when new blocks are found

