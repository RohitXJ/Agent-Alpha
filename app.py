import os
import requests
import base64
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Replace this URL with your n8n webhook URL
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/93efbc4c-d97d-4e12-8dc5-a7dac6323f8f"

@app.route('/')
def home():
    """Renders the main chat interface page."""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handles incoming chat messages and file uploads.
    Sends the data to the n8n webhook, ensuring all fields are present.
    """
    try:
        message = request.form.get('message', '')
        file = request.files.get('file')

        # Initialize data payload, ensuring message and filename are always present
        data = {
            "message": message,
            "filename": ""
        }
        files = {}

        # If a file is provided, populate filename and the files payload
        if file and file.filename:
            data['filename'] = file.filename
            files['file'] = (file.filename, file.read(), file.mimetype)
        else:
            # If no file is provided, send an empty 'file' part to ensure the field exists
            files['file'] = ('', '', 'application/octet-stream')

        # Send the payload to the n8n webhook as multipart/form-data
        response = requests.post(N8N_WEBHOOK_URL, data=data, files=files)

        # Check if the request was successful
        if response.status_code == 200:
            # Try to parse the response as JSON, but fall back to text if it fails
            try:
                response_data = response.json()
            except ValueError:
                response_data = response.text
            return jsonify({
                "status": "success",
                "message": "Message and file (if any) sent to n8n.",
                "response_from_n8n": response_data
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to send data to n8n. Status code: {response.status_code}",
                "n8n_response": response.text
            }), response.status_code

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({
            "status": "error",
            "message": "An internal server error occurred."
        }), 500

if __name__ == '__main__':
    # You can set debug=True for development, but set it to False for production
    app.run(debug=True)
