import requests

url = "http://localhost:1234/v1/chat/completions"

payload = {
    "model": "qwen2.5-vl-7b-instruct",
    "messages": [
        {"role": "system", "content": "You are an RFP analysis assistant."},
        {"role": "user", "content": "Summarize the following text: The vendor shall provide a project management system that supports 200 users and delivers training."}
    ],
    "temperature": 0.3,
}

response = requests.post(url, json=payload)
print("\nResponse:\n", response.json()["choices"][0]["message"]["content"])
