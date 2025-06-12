import os
import time
import logging
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# set up logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# set up chrome options for headless mode/configure download behavior
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

prefs = {
    "safebrowsing.enabled": False,
    "safebrowsing.disable_download_protection": True
}
chrome_options.add_experimental_option("prefs", prefs)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("📨 Telegram alert sent.")
    except requests.exceptions.HTTPError as e:
        logging.error(f"❌ Telegram API error {response.status_code}: {response.text}")
    except Exception as e:
        logging.error(f"❌ Unexpected error sending Telegram message: {e}")

# initialize webdriver
driver = webdriver.Chrome(options=chrome_options)

def time_difference_in_minutes(time_str):
    """Compares the given time string to the current time and returns the difference in minutes."""
    try:
        # Example time format: "12/06/2025 11:40:01"
        time_obj = datetime.strptime(time_str, "%d/%m/%Y %H:%M:%S")
        time_diff = datetime.now() - time_obj
        return time_diff.total_seconds() / 60  # returns difference in minutes
    except ValueError as e:
        logging.error(f"Error parsing time: {e}")
        return None

# start download process 
try:
    logging.info("Navigate to the target URL")
    driver.maximize_window()  # maximize window
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

    columns = ['Código', 'Nome da Filial', 'última conexão', 'Filial -> Central', 'Central -> Filial', 'Status']
    col_index_filial_central = columns.index("Filial -> Central")
    col_index_central_filial = columns.index("Central -> Filial")

    # Get all data rows (starting after header)
    data_rows = table.find_elements(By.XPATH, ".//tbody/tr")

    problem_branches_color = set()  # Branches with color issues
    problem_branches_time = set()   # Branches with time issues
    alert_needed_color = False      # Flag for color-based alert
    alert_needed_time = False       # Flag for time-based alert

    for row in data_rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if not cells:
            continue

        # Get the two relevant cells for time check
        cell_filial_central = cells[col_index_filial_central]
        cell_central_filial = cells[col_index_central_filial]

        # Extract time from 'Filial -> Central'
        time_str_fc = cell_filial_central.text.strip()
        if time_str_fc:
            time_diff_fc = time_difference_in_minutes(time_str_fc)
            if time_diff_fc is not None and time_diff_fc > 15:
                branch_name = cells[1].text.strip()  # 'Nome da Filial'
                if branch_name:
                    problem_branches_time.add(f"{branch_name} (Filial -> Central time: {time_str_fc})")
                    alert_needed_time = True

        # Extract time from 'Central -> Filial'
        time_str_cf = cell_central_filial.text.strip()
        if time_str_cf:
            time_diff_cf = time_difference_in_minutes(time_str_cf)
            if time_diff_cf is not None and time_diff_cf > 15:
                branch_name = cells[1].text.strip()  # 'Nome da Filial'
                if branch_name:
                    problem_branches_time.add(f"{branch_name} (Central -> Filial time: {time_str_cf})")
                    alert_needed_time = True

        # Get the computed color style for 'Filial -> Central' and 'Central -> Filial'
        color_fc = cell_filial_central.value_of_css_property("color")
        color_cf = cell_central_filial.value_of_css_property("color")

        def rgba_to_hex(rgba_string):
            import re
            match = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', rgba_string)
            if match:
                r, g, b = map(int, match.groups())
                return '#{:02X}{:02X}{:02X}'.format(r, g, b)
            return None

        hex_fc = rgba_to_hex(color_fc)
        hex_cf = rgba_to_hex(color_cf)

        if hex_fc == "#FF3535" or hex_cf == "#FF3535":
            branch_name = cells[1].text.strip()  # 'Nome da Filial'
            if branch_name:
                problem_branches_color.add(f"{branch_name} (Color Issue)")
                alert_needed_color = True

    # Prepare alert messages based on the conditions
    if problem_branches_color:
        if alert_needed_color:
            from datetime import datetime, timezone
            from zoneinfo import ZoneInfo

            now_brazil = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%-I%p update")
            branches_str = ", ".join(sorted(problem_branches_color))
            alert_text_color = f"🚨 {now_brazil} - Há problemas na replicação na(s) filial(is) {branches_str}!"
            send_telegram_alert(alert_text_color)
            print(alert_text_color)  # Send to Telegram or log

    if problem_branches_time:
        if alert_needed_time:
            now_brazil = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%-I%p update")
            branches_str = ", ".join(sorted(problem_branches_time))
            alert_text_time = f"🚨 {now_brazil} - O replicador está parado a mais de 15 minutos na(s) filial(is) {branches_str}!"
            send_telegram_alert(alert_text_time)
            print(alert_text_time)  # Send to Telegram or log

    if not problem_branches_color and not problem_branches_time:
        logging.info("✅ Nenhum problema de replicação identificado.")

finally:
    time.sleep(2)
    driver.quit()
