import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from urllib.parse import urljoin, urlparse
import time
import re
import logging

# Configure logging
logging.basicConfig(filename='idor_detection.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def login(driver, login_url, username, password, username_field, password_field, submit_button):
    """Log in to the website with provided credentials."""
    try:
        driver.get(login_url)
        driver.find_element(By.NAME, username_field).send_keys(username)
        driver.find_element(By.NAME, password_field).send_keys(password)
        driver.find_element(By.NAME, submit_button).click()
        time.sleep(2)  # Wait for login to complete
        logging.info(f"Successfully logged in as {username}")
        return True
    except Exception as e:
        logging.error(f"Login failed for {username}: {e}")
        return False

def logout(driver, logout_url):
    """Log out from the website."""
    try:
        driver.get(logout_url)
        time.sleep(1)
        logging.info("Successfully logged out")
    except Exception as e:
        logging.error(f"Logout failed: {e}")

def crawl(driver, start_url, max_depth, visited, params_collected, pattern):
    """Crawl the website and collect URLs with parameters where pattern is present."""
    if max_depth <= 0 or start_url in visited:
        return
    visited.add(start_url)
    try:
        driver.get(start_url)
        time.sleep(1)  # Wait for page to load
        page_source = driver.page_source

        # Check if the pattern (e.g., User A's data) is in the response
        if re.search(pattern, page_source):
            parsed = urlparse(start_url)
            query_params = parsed.query
            path = parsed.path

            # Store URL if it has parameters
            url_params = {}
            if query_params:
                url_params['query'] = query_params
            if re.search(r'\d+', path):  # Heuristic: digits in path might indicate an ID
                url_params['path'] = path
            if url_params:
                params_collected[start_url] = url_params

        # Find all links to crawl further
        links = driver.find_elements(By.TAG_NAME, 'a')
        for link in links:
            href = link.get_attribute('href')
            if href and urlparse(href).netloc == urlparse(start_url).netloc:
                absolute_url = urljoin(start_url, href)
                crawl(driver, absolute_url, max_depth - 1, visited, params_collected, pattern)
    except Exception as e:
        logging.error(f"Error crawling {start_url}: {e}")

def check_idor(driver, url, pattern):
    """Check if the URL reveals User A's data when accessed by User B."""
    try:
        driver.get(url)
        time.sleep(1)
        if re.search(pattern, driver.page_source):
            logging.info(f"Potential IDOR detected at: {url}")
            return True
        return False
    except Exception as e:
        logging.error(f"Error checking {url} for IDOR: {e}")
        return False

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="IDOR Detection Bot")
    parser.add_argument('-u', '--url', required=True, help="Starting URL to crawl")
    parser.add_argument('-l', '--login_url', required=True, help="Login URL")
    parser.add_argument('-a', '--user_a', required=True, help="Username for User A")
    parser.add_argument('-p', '--pass_a', required=True, help="Password for User A")
    parser.add_argument('-b', '--user_b', required=True, help="Username for User B")
    parser.add_argument('-q', '--pass_b', required=True, help="Password for User B")
    parser.add_argument('-f', '--username_field', default='username', help="Username field name in login form")
    parser.add_argument('-w', '--password_field', default='password', help="Password field name in login form")
    parser.add_argument('-s', '--submit_button', default='submit', help="Submit button name in login form")
    parser.add_argument('-o', '--logout_url', required=True, help="Logout URL")
    parser.add_argument('-m', '--max_depth', type=int, default=3, help="Maximum crawl depth")
    parser.add_argument('-t', '--pattern', required=True, help="Pattern to identify User A's data (e.g., username)")
    args = parser.parse_args()

    # Set up Firefox in headless mode
    firefox_options = Options()
    firefox_options.headless = True
    firefox_options.add_argument("--no-sandbox")
    service = Service(executable_path="/usr/local/bin/geckodriver")
    driver = webdriver.Firefox(service=service, options=firefox_options)

    try:
        # Step 1: Log in as User A and crawl
        if not login(driver, args.login_url, args.user_a, args.pass_a, 
                     args.username_field, args.password_field, args.submit_button):
            print("Login failed for User A. Exiting.")
            return

        visited = set()
        params_collected = {}
        logging.info(f"Starting crawl as {args.user_a} from {args.url}")
        crawl(driver, args.url, args.max_depth, visited, params_collected, args.pattern)
        logging.info(f"Collected {len(params_collected)} URLs with parameters for User A")

        # Step 2: Log out User A
        logout(driver, args.logout_url)

        # Step 3: Log in as User B
        if not login(driver, args.login_url, args.user_b, args.pass_b, 
                     args.username_field, args.password_field, args.submit_button):
            print("Login failed for User B. Exiting.")
            return

        # Step 4: Test for IDOR as User B
        print("Checking for IDOR vulnerabilities...")
        for url in params_collected:
            if check_idor(driver, url, args.pattern):
                print(f"Potential IDOR found: {url}")

        # Step 5: Log out User B
        logout(driver, args.logout_url)

    except Exception as e:
        logging.error(f"Script execution failed: {e}")
        print(f"An error occurred: {e}")
    finally:
        driver.quit()
        logging.info("Script execution completed")

if __name__ == "__main__":
    main()
