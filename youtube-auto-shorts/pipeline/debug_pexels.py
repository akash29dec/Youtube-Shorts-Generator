import requests

# Paste your key here again to test
API_KEY = "YOUR_REAL_KEY_HERE" 

headers = {"Authorization": API_KEY}
url = "https://api.pexels.com/videos/search?query=nature&per_page=1"

print(f"Testing Key: {API_KEY[:5]}...{API_KEY[-5:]}")

try:
    r = requests.get(url, headers=headers, verify=False)
    print(f"Status Code: {r.status_code}")
    
    if r.status_code == 200:
        print("✅ SUCCESS! The key works. You can proceed.")
        print(f"Found video: {r.json()['videos'][0]['url']}")
    elif r.status_code == 401:
        print("❌ ERROR 401: Unauthorized. Your API Key is wrong.")
    elif r.status_code == 403:
        print("❌ ERROR 403: Forbidden. You might be banned or key is empty.")
    else:
        print(f"❌ ERROR {r.status_code}: {r.text}")
        
except Exception as e:
    print(f"❌ CRITICAL CONNECTION ERROR: {e}")