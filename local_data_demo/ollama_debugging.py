import requests

url = "http://localhost:11434/api/generate"
payload = {
    "model": "llama3.2:1b",
    "prompt": "Say hello",
    "stream": False
}

print(f"Testing Ollama at: {url}")
print(f"Model: llama3.2:1b")

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ Ollama works!")
        print(f"Response: {response.json()}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"✗ Request failed: {e}")