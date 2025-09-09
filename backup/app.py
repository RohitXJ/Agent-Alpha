import os
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import uuid
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build

import io
import base64
import pandas as pd
import pdfplumber
from PIL import Image

import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool
from langchain_google_vertexai import ChatVertexAI
from langchain.memory import ConversationBufferWindowMemory

app = Flask(__name__)
app.secret_key = os.urandom(24)

# This is necessary for OAuth 2.0 compliance.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- Configuration ---
GOOGLE_CLOUD_PROJECT_ID = "agent-alpha-471408" # From n8n workflow
CLIENT_SECRETS_FILE = "client_secret.json"

# Scopes for User Authentication (from app_test.py)
# Updated to match the scopes returned by Google exactly to satisfy oauthlib's strict validation
USER_AUTH_SCOPES = [
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.modify',
    'openid',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/gmail.addons.current.action.compose',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.addons.current.message.action',
    'https://www.googleapis.com/auth/gmail.send'
]

# Scopes for Agent Tools (from agent_backend.py)
AGENT_TOOL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]

# Initialize Vertex AI
vertexai.init(project=GOOGLE_CLOUD_PROJECT_ID)

# --- Google OAuth Functions for Agent Tools ---
# This is separate from the user authentication in app_test.py
AGENT_CREDENTIALS_FILE = "agent_token.json"

def get_agent_google_credentials():
    creds = None
    if os.path.exists(AGENT_CREDENTIALS_FILE):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(AGENT_CREDENTIALS_FILE, AGENT_TOOL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            # Use a fixed port for the local server to avoid redirect_uri_mismatch with dynamic ports
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, AGENT_TOOL_SCOPES)
            creds = flow.run_local_server(port=8080) # Fixed port for agent OAuth
        with open(AGENT_CREDENTIALS_FILE, "w") as token:
            token.write(creds.to_json())
    return creds

# --- Custom Tools for LangChain Agent ---

def send_gmail_message(to: str, subject: str, message_text: str) -> str:
    """Sends an email message via Gmail.
    Args:
        to: The recipient's email address.
        subject: The subject of the email.
        message_text: The body of the email.
    Returns:
        A string indicating success or failure.
    """
    try:
        creds = get_agent_google_credentials()
        service = build("gmail", "v1", credentials=creds)
        message = {
            "raw": base64.urlsafe_b64encode(
                f"To: {to}\nSubject: {subject}\n\n{message_text}".encode("utf-8")
            ).decode("utf-8")
        }
        send_message = (
            service.users()
            .messages()
            .send(userId="me", body=message)
            .execute()
        )
        return f"Email sent successfully! Message Id: {send_message['id']}"
    except Exception as e:
        return f"Error sending email: {e}"

def create_google_calendar_event(
    summary: str, description: str, start_time: str, end_time: str, calendar_id: str = "primary"
) -> str:
    """Creates an event in Google Calendar.
    Args:
        summary: The summary/title of the event.
        description: The description of the event.
        start_time: The start time of the event in ISO format (e.g., '2023-10-27T10:00:00-07:00').
        end_time: The end time of the event in ISO format (e.g., '2023-10-27T11:00:00-07:00').
        calendar_id: The ID of the calendar to create the event in (default: 'primary').
    Returns:
        A string indicating success or failure.
    """
    try:
        creds = get_agent_google_credentials()
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_time, "timeZone": "UTC"}, # Assuming UTC for simplicity, adjust as needed
            "end": {"dateTime": end_time, "timeZone": "UTC"}, # Assuming UTC for simplicity, adjust as needed
        }
        event = service.events().insert(calendarId=calendar_id, body=event).execute()
        return f"Event created: {event.get('htmlLink')}"
    except Exception as e:
        return f"Error creating calendar event: {e}"

# --- File Processing Functions ---

def extract_csv_insights(file_content: bytes) -> str:
    try:
        df = pd.read_csv(io.BytesIO(file_content))
        # Try converting numeric columns
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="ignore")

        buf = io.StringIO()
        df.info(buf=buf)
        info_str = buf.getvalue()
        describe_str = df.describe(include="all").to_string()
        combined = (
            "📊 DataFrame Info:\n" + info_str +
            "\n\n📈 DataFrame Describe:\n" + describe_str
        )
        return combined
    except Exception as e:
        return f"❌ Error during CSV analysis: {e}"

def extract_pdf_text(file_content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        return f"❌ Error extracting text from PDF: {e}"

def extract_txt_content(file_content: bytes) -> str:
    try:
        return file_content.decode("utf-8")
    except Exception as e:
        return f"❌ Error extracting text from TXT: {e}"

def analyze_image(file_content: bytes, mime_type: str = "image/jpeg") -> str:
    """Analyzes an image using Google Gemini Vision model and returns a description."""
    try:
        model = GenerativeModel("gemini-pro-vision") # Use gemini-pro-vision for image analysis
        image_part = Part.from_data(data=file_content, mime_type=mime_type)
        response = model.generate_content([image_part, "Describe this image in detail, focusing on key objects, colors, and overall scene."])
        return response.text
    except Exception as e:
        return f"❌ Error analyzing image with Gemini Vision: {e}"

# --- LangChain Agent Setup ---

# Define tools
tools = [
    Tool(
        name="SendGmailMessage",
        func=send_gmail_message,
        description="""Send an email message via Gmail.
        Input should be a JSON string with 'to', 'subject', and 'message_text' keys.
        Example: {\"to\": \"recipient@example.com\", \"subject\": \"Hello\", \"message_text\": \"This is a test email.\"}
        """,
    ),
    Tool(
        name="CreateGoogleCalendarEvent",
        func=create_google_calendar_event,
        description="""Creates an event in Google Calendar.
        Input should be a JSON string with 'summary', 'description', 'start_time', and 'end_time' keys.
        'start_time' and 'end_time' should be in ISO format (e.g., '2023-10-27T10:00:00-07:00').
        Example: {\"summary\": \"Meeting\", \"description\": \"Project discussion\", \"start_time\": \"2023-10-27T10:00:00-07:00\", \"end_time\": \"2023-10-27T11:00:00-07:00\"}
        """,
    ),
]

# Agent Alpha System Prompt (from n8n workflow)
AGENT_ALPHA_SYSTEM_PROMPT = """Agent Alpha System Prompt
Persona: You are Agent Alpha, a helpful, moderate, and efficient AI assistant. Your goal is to complete user requests accurately and concisely.

Core Principles:

Reply quickly and to the point. Keep responses short unless details are requested.

Act like a person. Use a natural, conversational tone.

Respond in text only. Do not use any other formats like JSON.

Tools are for specific tasks. Only use the email tool when the user's explicit request is to "send an email" or "draft an email." Do not use it for any other reason.

Handle incomplete requests. If a request to send an email lacks a recipient's email address, ask for it. Do not attempt to send an email without a valid recipient.

Be conversational and greet casually. If the user initiates a normal conversation, respond in a friendly, human-like manner without using any tools.

Constraints:

Do not respond with a "tool call" unless the prompt clearly asks for it.

Do not provide any commentary about your decision-making process, tool usage, or lack thereof. Simply respond directly to the user's request.

Never use the email tool for anything other than explicit email-sending instructions.

Do not include any meta-commentary about your instructions or your own abilities.

If an email recipient's address is not provided, you must ask for it.

Do not include what you are thinking, just give the output"""

# Initialize LangChain components
llm = ChatVertexAI(project=GOOGLE_CLOUD_PROJECT_ID, model_name="gemini-2.5-flash")
memory = ConversationBufferWindowMemory(memory_key="chat_history", k=5) # k=5 is arbitrary, adjust as needed

# Create the agent
prompt = PromptTemplate.from_template(
    AGENT_ALPHA_SYSTEM_PROMPT +
    "\n\n" +
    "You have access to the following tools:\n" +
    "{tools}\n\n" +
    "Use the following format:\n\n" +
    "Question: the input question you must answer\n" +
    "Thought: you should always think about what to do\n" +
    "Action: the action to take, should be one of [{tool_names}]\n" +
    "Action Input: the input to the action\n" +
    "Observation: the result of the action\n" +
    "... (this Thought/Action/Action Input/Observation can repeat N times)\n" +
    "Thought: I now know the final answer\n" +
    "Final Answer: the final answer to the original input question\n\n" +
    "Begin!\n\n" +
    "Chat History:\n{chat_history}\n" +
    "Question: {input}\n" +
    "Thought:{agent_scratchpad}"
)

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=False, handle_parsing_errors=True)

# --- Frontend Routes (from app_test.py) ---
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
    """Initiates the Google OAuth 2.0 flow for user authentication."""
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=USER_AUTH_SCOPES)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Callback route for Google OAuth 2.0 for user authentication."""
    state = session['state']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=USER_AUTH_SCOPES, state=state)
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

# --- API Endpoint (from app_test.py, now integrated with agent_backend.py logic) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handles incoming chat messages and file uploads.
    Processes them with the LangChain Agent.
    """
    if 'credentials' not in session:
        return jsonify({"status": "error", "message": "User not authenticated"}), 401

    try:
        if 'sessionId' not in session:
            session['sessionId'] = str(uuid.uuid4())
        
        sessionId = session['sessionId'] # Not directly used by agent_executor, but kept for consistency
        message = request.form.get('message', '')
        file = request.files.get('file')
        
        # No need for accessToken from user session for agent tools, as agent_token.json handles it

        combined_message = message
        insights = ""

        if file:
            filename = file.filename
            file_content = file.read()
            mime_type = file.content_type

            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                insights = analyze_image(file_content, mime_type=mime_type)
            elif filename.lower().endswith(".csv"):
                insights = extract_csv_insights(file_content)
            elif filename.lower().endswith(".txt"):
                insights = extract_txt_content(file_content)
            elif filename.lower().endswith(".pdf"):
                insights = extract_pdf_text(file_content)
            else:
                insights = f"Unsupported file type: {filename}"

        if insights:
            combined_message += f"\n Here is the data extracted from the file given \n{insights}"

        # Pass the combined message to the LangChain agent
        response = agent_executor.invoke({"input": combined_message})
        output = response.get("output", "No response from agent.")

        return jsonify({
            "status": "success",
            "message": "Message and file (if any) processed.",
            "response_from_n8n": output # Renamed to match original frontend expectation
        })

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({
            "status": "error",
            "message": "An internal server error occurred."
        }), 500

if __name__ == '__main__':
    # This part will guide the user through OAuth for agent tools if agent_token.json doesn't exist or is invalid
    print("Checking Agent Google API credentials...")
    try:
        get_agent_google_credentials()
        print("Agent Google API credentials are valid or have been refreshed.")
    except Exception as e:
        print(f"Could not get Agent Google API credentials. Please ensure {CLIENT_SECRETS_FILE} is present and valid, and follow the OAuth flow if prompted. Error: {e}")

    app.run(debug=False, port=5000) # Run the Flask app on port 5000