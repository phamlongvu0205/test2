from fake_useragent import UserAgent


base_url = 'https://apipubaws.tcbs.com.vn'
analysis_url = 'tcanalysis'

DEFAULT_HEADERS = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            "Accept-Encoding": "gzip, deflate, br",
            'Accept-Language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            "Sec-Fetch-Mode": "navigate",
            'Sec-Fetch-Site': 'same-site',
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            'Accept-Language': 'vi',
            'Cache-Control': 'no-cache',
            'Sec-Fetch-Mode': 'cors',
            'DNT': '1',
            'Pragma': 'no-cache',
        }

def get_headers(random_agent=True):
   
    ua = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36')
    headers = DEFAULT_HEADERS.copy()
    if random_agent:
        headers['User-Agent'] = ua.random
    else:
        headers['User-Agent'] = ua.chrome
    return headers