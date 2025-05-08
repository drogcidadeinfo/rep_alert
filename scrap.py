import os, time, logging, requests 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# set up logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "your_bot_token_here"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "your_chat_id_here"

# set up chrome options for headless mode/configure download behavior
chrome_options = Options()
chrome_options.add_argument("--headless")  
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

prefs = {
    "safebrowsing.enabled": False,  # disable safe browsing (meh)
    "safebrowsing.disable_download_protection": True
}
chrome_options.add_experimental_option("prefs", prefs)

# initialize webdriver
driver = webdriver.Chrome(options=chrome_options)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",  # Optional, allows formatting
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("📨 Telegram alert sent.")
    except Exception as e:
        logging.error(f"❌ Failed to send Telegram message: {e}")

# start download process 
try:
    logging.info("Navigate to the target URL")
    driver.maximize_window() # maximize window
    driver.get("http://drogcidade.ddns.net:4647/replicador")

    # wait til page loads completely
    WebDriverWait(driver, 10).until(
        lambda x: x.execute_script("return document.readyState === 'complete'")
    )
    
    logging.info("Navigating to replication status table...")

    # Wait for the table to be present
    table = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.XPATH, "//table")
    )

    """
    # Get all rows in the table body
    rows = table.find_elements(By.XPATH, ".//tbody/tr")
    for i, row in enumerate(rows, start=1):
        print(f"Row {i}: {row.text}")
        
        # Find all rows in the table
    all_rows = table.find_elements(By.XPATH, ".//tbody/tr")

    # Get the second row (index 1 because it's zero-based)
    if len(all_rows) >= 2:
        header_cells = all_rows[1].find_elements(By.TAG_NAME, "th")
        column_names = [cell.text.strip() for cell in header_cells]
        print("Column names:", column_names)
    else:
        print("Table has fewer than 2 rows.")"""
    
    columns = ['Código', 'Nome da Filial', 'última conexão', 'Filial -> Central', 'Central -> Filial', 'Status']
    col_index_filial_central = columns.index("Filial -> Central")
    col_index_central_filial = columns.index("Central -> Filial")

    # Get all data rows (starting after header)
    data_rows = table.find_elements(By.XPATH, ".//tbody/tr")

    problems = []

    for row in data_rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        
        if not cells:
            continue  # skip if row is empty

        # Get the two relevant cells
        cell_filial_central = cells[col_index_filial_central]
        cell_central_filial = cells[col_index_central_filial]

        # Get the computed color style
        color_fc = cell_filial_central.value_of_css_property("color")
        color_cf = cell_central_filial.value_of_css_property("color")

        # Convert to hex
        def rgba_to_hex(rgba_string):
            import re
            match = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', rgba_string)
            if match:
                r, g, b = map(int, match.groups())
                return '#{:02X}{:02X}{:02X}'.format(r, g, b)
            return None

        hex_fc = rgba_to_hex(color_fc)
        hex_cf = rgba_to_hex(color_cf)

        # Check if either is red (#FF3535)
        if hex_fc == "#FF3535" or hex_cf == "#FF3535":
            problems.append(row.text)

    # Send alert if any issues found
    if problems:
        alert_text = "🚨 Replication issues detected:\n" + "\n".join(problems)
        send_telegram_alert(alert_text)
    else:
        send_telegram_alert("✅ No replication alerts found.")
        logging.info("✅ No replication color alerts found.")
        
finally:
    time.sleep(2)
    driver.quit()
