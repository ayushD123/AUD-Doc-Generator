import os
import requests

print("HTTP_PROXY =", os.getenv("HTTP_PROXY"))
print("HTTPS_PROXY =", os.getenv("HTTPS_PROXY"))

r = requests.get(
    "https://objectstorage.us-chicago-1.oraclecloud.com",
    timeout=10,
)
print(r.status_code)