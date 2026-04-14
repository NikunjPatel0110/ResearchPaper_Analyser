import requests

API_KEY = "db786005-43d7-49ee-b642-2057117ecbf0"
URL = "https://api.zerogpt.com/api/detect/detectText"

headers = {
    "ApiKey": API_KEY, 
    "Content-Type": "application/json"
}

payload = {
    "input_text": "This is a simple test sentence to verify if my ZeroGPT API key is fully activated and working."
}

print("Testing ZeroGPT API Key...")
response = requests.post(URL, json=payload, headers=headers)

print(f"Status Code: {response.status_code}")
print("Raw JSON Response:")
print(response.text)