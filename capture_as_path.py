from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    # viewport size
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto('http://127.0.0.1:8421/as-path?q=4242421234,4242424100')
    page.wait_for_load_state('networkidle')
    # wait for force layout to finish simulating
    time.sleep(2)
    
    page.screenshot(path='/workspace/as_path_screenshot.png', full_page=True)
    browser.close()
