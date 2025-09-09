import os
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import uuid
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = os.urandom(24)

# This is necessary for OAuth 2.0 compliance.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Replace this URL with your n8n webhook URL
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/93efbc4c-d97d-4e12-8dc5-a7dac6323f8f"

# Scopes required for the Google APIs you want to use
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.addons.current.message.action',
    'https://www.googleapis.com/auth/gmail.addons.current.action.compose'
]

# Path to your client secret file from Google Cloud Console
CLIENT_SECRETS_FILE = "client_secret.json"

@app.route('/')
def home():
    """Renders the main chat interface page or login page."""
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    if 'sessionId' not in session:
        session['sessionId'] = str(uuid.uuid4())
        
    return render_template('index.html', email=session.get('email'))

@app.route('/login')
def login():
    """Renders the login page."""
    return render_template('login.html')

@app.route('/auth')
def auth():
    """Initiates the Google OAuth 2.0 flow."""
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Callback route for Google OAuth 2.0."""
    state = session['state']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    # Get user info
    service = build('oauth2', 'v2', credentials=credentials)
    user_info = service.userinfo().get().execute()
    session['email'] = user_info['email']
    
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handles incoming chat messages and file uploads.
    Sends the data to the n8n webhook, ensuring all fields are present.
    """
    if 'credentials' not in session:
        return jsonify({"status": "error", "message": "User not authenticated"}), 401

    try:
        if 'sessionId' not in session:
            session['sessionId'] = str(uuid.uuid4())
        
        sessionId = session['sessionId']
        message = request.form.get('message', '')
        file = request.files.get('file')
        
        credentials = session['credentials']
        access_token = credentials['token']

        data = {
            "message": message,
            "filename": "",
            "sessionId": sessionId,
            "accessToken": access_token
        }
        files = {}

        if file and file.filename:
            data['filename'] = file.filename
            files['file'] = (file.filename, file.read(), file.mimetype)
        else:
            files['file'] = ('', '', 'application/octet-stream')

        response = requests.post(N8N_WEBHOOK_URL, data=data, files=files)

        if response.status_code == 200:
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
    app.run(debug=True)