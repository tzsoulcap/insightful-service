import fitz
import requests
import re
import json

misspell_api_key = "app-iIy7qQePuRTusfMiw0itpDio"
misspell_base_url = "http://localhost/v1"

pdf_path = r"D:\llm_dev\knowledge\output_prepared\ATTG-S-SHE 081 การติดตั้งอุปกรณ์ความปลอดภัย Light curtain..pdf"
doc = fitz.open(pdf_path)
list_text = []
for page in doc:
    list_text.append(page.get_text())

text = list_text[0]

# request to dify for misspell correction post /chat-messages
url = f"{misspell_base_url}/chat-messages"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {misspell_api_key}"
}
payload = {
    "inputs": {},
    "query": text,
    "response_mode": "blocking",
    "conversation_id": "",
    "user": "abc-123",
    "files": [
    ]
}
response = requests.post(url, json=payload, headers=headers)
if response.status_code == 200:
    print("Response:", response.json())
else:
    print("Error:", response.status_code, response.text)


# get answer as json format without thinking message
json_res = response.json().get("answer")
json_res = re.sub(r"<think>.*?</think>", "", json_res, flags=re.DOTALL)
print(json_res)

match = re.search(r"json\s*(\{.*?\})\s*", json_res, flags=re.DOTALL) 
# print(match)
if match: 
    result = json.loads(match.group(1)) 
    print(f"Type of result: {type(result)}")
    print(result.get("CORRECTED")) 
else: 
    print("ไม่พบ JSON ใน response")