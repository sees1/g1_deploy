import requests
from config import URL

payload = {
    "state": "Passive"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(URL, json=payload, headers=headers)

print(response.status_code)
print(response.text)
