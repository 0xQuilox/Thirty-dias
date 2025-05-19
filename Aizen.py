import requests
import sys
import time

# Solscan API key provided by the user
SOLSCAN_API_KEY = ""

def get_pair_data(chain_id, pair_address):
    """
    Fetch pair data from Dexscreener API.
    
    Args:
        chain_id (str): Blockchain identifier (e.g., 'ethereum', 'bsc', 'solana').
        pair_address (str): Address of the trading pair.
    
    Returns:
        dict: Pair data, or None if the request fails.
    """
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{pair_address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("pair")
    except requests.RequestException as e:
        print(f"Error fetching pair data from Dexscreener: {e}")
        return None

def get_market_cap(chain_id, token_address):
    """
    Fetch market cap for Ethereum and BSC from CoinGecko API.
    
    Args:
        chain_id (str): Blockchain identifier.
        token_address (str): Token contract address.
    
    Returns:
        float or None: Market cap in USD, or None if unavailable.
    """
    platform_map = {
        "ethereum": "ethereum",
        "bsc": "binance-smart-chain"
    }
    platform = platform_map.get(chain_id)
    if not platform:
        return None
    
    url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{token_address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("market_data", {}).get("market_cap", {}).get("usd")
    except requests.RequestException:
        return None

def get_solscan_token_info(token_address):
    """
    Fetch token market cap and reputation from Solscan API for Solana.
    
    Args:
        token_address (str): Solana token mint address.
    
    Returns:
        tuple: (market_cap, reputation) or (None, None) if the request fails.
    """
    url = f"https://pro-api.solscan.io/v2.0/token/meta?address={token_address}"
    headers = {"Authorization": f"Bearer {SOLSCAN_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", {})
        market_cap = data.get("marketCapUSD")  # Adjust based on actual Solscan response
        # Solscan doesn't directly provide "reputation"; using holder count as a proxy
        reputation = "Known" if data.get("holderCount", 0) > 0 else "Unknown"
        return market_cap, reputation
    except requests.RequestException as e:
        print(f"Error fetching token info from Solscan: {e}")
        return None, None

def is_contract_verified(chain_id, token_address):
    """
    Check if the token's contract is verified using blockchain explorer APIs.
    
    Args:
        chain_id (str): Blockchain identifier.
        token_address (str): Token contract address.
    
    Returns:
        bool: True if verified, False otherwise.
    """
    explorer_map = {
        "ethereum": "https://api.etherscan.io/api",
        "bsc": "https://api.bscscan.com/api"
    }
    explorer_api = explorer_map.get(chain_id)
    if not explorer_api:
        return False
    
    url = f"{explorer_api}?module=contract&action=getsourcecode&address={token_address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "1" and data.get("result")[0].get("SourceCode"):
            return True
        return False
    except requests.RequestException:
        return False

def calculate_pair_age(pair_created_at):
    """
    Calculate the age of the pair in days.
    
    Args:
        pair_created_at (int): Timestamp in milliseconds when the pair was created.
    
    Returns:
        float: Age of the pair in days.
    """
    current_time = int(time.time() * 1000)  # Current time in milliseconds
    age_ms = current_time - pair_created_at
    age_days = age_ms / (1000 * 60 * 60 * 24)  # Convert milliseconds to days
    return age_days

def scrape_token_info(chain_id, pair_address):
    """
    Scrape token information based on the blockchain.
    
    Args:
        chain_id (str): Blockchain identifier ('ethereum', 'bsc', 'solana').
        pair_address (str): Pair address on the DEX.
    """
    # Validate supported chains
    supported_chains = ["ethereum", "bsc", "solana"]
    if chain_id not in supported_chains:
        print(f"Error: Unsupported chain '{chain_id}'. Supported chains: {', '.join(supported_chains)}")
        return
    
    # Fetch pair data from Dexscreener
    pair = get_pair_data(chain_id, pair_address)
    if not pair:
        print("Failed to retrieve pair data or pair not found.")
        return
    
    price = pair.get("priceUsd")
    pair_created_at = pair.get("pairCreatedAt")
    token_address = pair.get("baseToken", {}).get("address")
    
    if not all([price, pair_created_at, token_address]):
        print("Incomplete pair data received.")
        return
    
    # Calculate pair age
    pair_age_days = calculate_pair_age(pair_created_at)
    
    # Chain-specific logic
    if chain_id == "solana":
        market_cap, reputation = get_solscan_token_info(token_address)
        deployment_status = reputation if reputation else "Unknown"
    else:  # Ethereum or BSC
        market_cap = get_market_cap(chain_id, token_address)
        deployment_status = is_contract_verified(chain_id, token_address)
    
    # Output results
    print(f"Chain: {chain_id}")
    print(f"Token Price: {price} USD")
    print(f"Market Cap: {market_cap if market_cap else 'Not Available'} USD")
    print(f"Deployment Status: {'Verified' if deployment_status is True else deployment_status if isinstance(deployment_status, str) else 'Not Verified'}")
    print(f"Pair Age: {pair_age_days:.2f} days")

def main():
    """Main function to execute the scraping logic."""
    if len(sys.argv) != 3:
        print("Usage: python script.py <chainId> <pairAddress>")
        print("Supported chains: ethereum, bsc, solana")
        print("Example: python script.py solana 7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs")
        sys.exit(1)
    
    chain_id = sys.argv[1].lower()
    pair_address = sys.argv[2]
    scrape_token_info(chain_id, pair_address)

if __name__ == "__main__":
    main()
