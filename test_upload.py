import requests
import base64
import os

# --- Configuration ---
# Path to the file you want to upload
file_path = 'test.txt'
# A message to accompany the file
message = 'This is a test message with a file.'
# Your n8n webhook URL
webhook_url = 'http://localhost:5678/webhook-test/f3d9982a-0c81-4847-8e5d-56f1e01cdf1b' # <-- IMPORTANT: Replace with your n8n webhook URL

# --- Script ---
# Create a dummy file for testing
print(f"Creating a dummy file: {file_path}")
with open(file_path, 'w') as f:
    f.write('Hello from the test script!\n')

# Read the file and encode it in base64
print("Reading and encoding the file in base64...")
with open(file_path, 'rb') as f:
    file_content = f.read()
    base64_encoded_data = base64.b64encode(file_content).decode('utf-8')

# Prepare the JSON payload
payload = {
    'filename': os.path.basename(file_path),
    'filedata': base64_encoded_data,
    'message': message
}

# Send the POST request to the n8n webhook
print(f"Sending the file to: {webhook_url}")
try:
    response = requests.post(webhook_url, json=payload)
    response.raise_for_status()  # Raise an exception for bad status codes (like 404 or 500)
    print("\n--- Success! ---")
    print("File uploaded successfully to n8n.")
    print(f"Response from webhook: {response.text}")
except requests.exceptions.RequestException as e:
    print("\n--- Error ---")
    print(f"An error occurred while sending the file: {e}")
    print("Please check the following:")
    print("1. Is your n8n instance running?")
    print("2. Is the webhook URL correct?")
    print("3. Is the workflow active?")

# Clean up the dummy file
#os.remove(file_path)
