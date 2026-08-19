import requests
from config import URL

payload = {
    "state": "Mimic_Dance_103"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(URL, json=payload, headers=headers)

print(response.status_code)
print(response.text)
