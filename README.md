# API Scanner

Tool to detect API endpoints on websites.

## Features
    ### Static Analysis
    - Parses HTML/JS files using BeautifulSoup
    - Detects URLs in:
      - Script `src` attributes
      - Link `href` attributes
      - AJAX patterns in JS code (fetch/XMLHttpRequest)
    - Basic regex matching for API-like patterns

    ### Network Monitoring
    - Captures browser DevTools performance logs
    - Extracts URLs from network requests:
      - XHR/fetch calls
      - Document/page resources
      - All HTTP(S) traffic during page load
    - Limited to first 500 unique URLs

    ### Validation System
    - Basic endpoint verification through:
      - HEAD requests
      - Content-Type header checks
      - Simple keyword matching ("api" in response)
    - Tests GET/POST methods with dummy payloads

    ### Technical Implementation
    - Browser automation via Selenium
    - Supports Chrome/Firefox/Edge (Chromium-based)
    - ThreadPoolExecutor for parallel requests
    - JSON report generation with:
      - Endpoint URLs
      - HTTP methods tested
      - Response status codes
      - Basic parameter extraction

    ### Limitations
    - Requires modern browser versions
    - Network logging depends on browser DevTools support
    - No authentication mechanisms
    - Basic parameter fuzzing (no smart generation)
    - Static analysis depth limited to initial page

## Requirements

- Python 3.10+
- Chrome, Firefox or Edge browser
- Internet connection

## Installation

```bash
Clone repository:
git clone https://github.com/mounsys/not-a-webscrapper
cd nowbs

Install dependencies:
pip install -r requirements.txt

Start a program

python script.py

    Main menu:

[1] Set target URL
[2] Select browser
[3] Configure proxy
[4] Advanced options
[5] Start scan
[6] Exit

    Reports saved in:

/results/reports/

Quick Commands

    Run with proxy:
python api_scanner.py --proxy http://localhost:8080

    Headless mode:
python api_scanner.py --headless

    Specify browser:
python api_scanner.py --browser firefox

    Configuration

Edit api_scanner_config/config.json for permanent settings:
json

{
    "target_url": "https://example.com",
    "browser": "chrome",
    "headless": true,
    "proxy": null,
    "depth": 2,
    "workers": 10,
    "timeout": 15
}

