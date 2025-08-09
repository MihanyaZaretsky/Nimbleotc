import requests

resp = requests.get("https://aaio.so/api/public/ips")
print(resp.text)