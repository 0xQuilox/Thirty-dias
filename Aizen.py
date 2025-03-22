import requests
import sys
import time

def get_pair_data(chain_id, pair_address):
    """
    Fetch pair data from Dexscreener API.
    
    Args:
        chain_id (str): The blockchain identifier (e.g., 'ethereum', 'bsc').
        pair_address (str): The address of the trading pair.
    
    Returns:
        dict: JSON response containing pair data, or None if the request fails.
    """
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{pair_address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching pair data: {e}")
        return None

def get_market_cap(chain_id, token_address):
    """
    Fetch market cap from CoinGecko API.
    
    Args:
        chain_id (str): The blockchain identifier.
        token_address (str): The token's contract address.
    
    Returns:
        float or None: Market cap in USD, or None if not available.
    """
    # Mapping Dexscreener chain IDs to CoinGecko platform IDs
    platform_map = {
        "ethereum": "ethereum",
        "bsc": "binance-smart-chain",
        # Add more mappings for other chains as needed
    }
    platform = platform_map.get(chain_id)
    if not platform:
        print(f"Unsupported chain ID for CoinGecko: {chain_id}")
        return None
    
    url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{token_address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("market_data", {}).get("market_cap", {}).get("usd")
    except requests.RequestException:
        return None

def is_contract_verified(chain_id, token_address):
    """
    Check if the token's contract is verified using the blockchain explorer API.
    
    Args:
        chain_id (str): The blockchain identifier.
        token_address (str): The token's contract address.
    
    Returns:
        bool: True if the contract is verified, False otherwise.
    """
    # Mapping chain IDs to explorer API endpoints
    explorer_map = {
        "ethereum": "https://api.etherscan.io/api",
        "bsc": "https://api.bscscan.com/api",
        # Add more mappings for other chains as needed
    }
    explorer_api = explorer_map.get(chain_id)
    if not explorer_api:
        print(f"Unsupported chain ID for explorer: {chain_id}")
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
    current_time = int(time.time() * 1000)  # Convert current time to milliseconds
    age_ms = current_time - pair_created_at
    age_days = age_ms / (1000 * 60 * 60 * 24)  # Convert milliseconds to days
    return age_days

def main():
    """Main function to execute the scraping logic."""
    # Check command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python script.py <chainId> <pairAddress>")
        print("Example: python script.py ethereum 0x1d42064Fc4Beb5F8aAF85F4617AE8b3b5B8Bd801")
        sys.exit(1)
    
    chain_id = sys.argv[1]
    pair_address = sys.argv[2]
    
    # Fetch pair data from Dexscreener
    pair_data = get_pair_data(chain_id, pair_address)
    if not pair_data or "pair" not in pair_data:
        print("Failed to retrieve pair data or pair not found.")
        return
    
    pair = pair_data["pair"]
    price = pair.get("priceUsd")
    pair_created_at = pair.get("pairCreatedAt")
    token_address = pair.get("baseToken", {}).get("address")
    
    if not all([price, pair_created_at, token_address]):
        print("Incomplete pair data received.")
        return
    
    # Fetch additional data
    market_cap = get_market_cap(chain_id, token_address)
    contract_verified = is_contract_verified(chain_id, token_address)
    pair_age_days = calculate_pair_age(pair_created_at)
    
    # Output results
    print(f"Token Price: {price} USD")
    print(f"Market Cap: {market_cap} USD" if market_cap else "Market Cap: Not available")
    print(f"Contract Verified: {contract_verified}")
    print(f"Pair Age: {pair_age_days:.2f} days")

if __name__ == "__main__":
    main()
