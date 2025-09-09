import json

print("Attempting to create .env file from agent-alpha.json...")

try:
    with open('agent-alpha.json', 'r') as f:
        credentials = json.load(f)

    email = credentials.get('client_email')
    private_key = credentials.get('private_key')

    if not email or not private_key:
        raise ValueError("Could not find 'client_email' or 'private_key' in the JSON file.")

    with open('.env', 'w') as f:
        f.write(f"VERTEX_AI_EMAIL={email}\n")
        # Replace newlines in the key with a literal \n for .env compatibility
        f.write(f"VERTEX_AI_PRIVATE_KEY=\"{private_key.replace('\n', '\\n')}\"")
    
    print("Successfully created .env file with separate Vertex AI credentials.")

except FileNotFoundError:
    print("Error: 'agent-alpha.json' not found. Please make sure the file exists in the root of your project.")
except Exception as e:
    print(f"An error occurred: {e}")