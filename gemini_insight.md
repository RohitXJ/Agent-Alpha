End-to-End Application Architecture
Your application is composed of three distinct parts working in tandem to handle user requests:

Frontend/Backend (Python App): This is the user-facing part. It serves the chat interface and handles the initial Google authentication flow. It's the secure intermediary that receives the user's prompt and their temporary access token.

n8n Workflow (Docker Container): This is the core logic. It's a self-contained automation engine that listens for requests from your Python app. It contains the AI agent and the Google tool nodes (Gmail, Drive, etc.).

Datastore (Firebase Firestore): This is your database for managing persistent data, specifically chat history and the user's query quota.

Deployment on Render with Docker
To make this system ready for deployment, you'll containerize it using Docker.

You will create a Dockerfile that packages your Python backend and the n8n workflow together into a single, deployable unit.

Secure API Keys: Your personal Google Cloud API key for the AI agent will not be stored in any code files. Instead, you'll configure it as a secret environment variable within your Render dashboard. When the Docker container launches, Render securely injects this variable, and your n8n workflow accesses it. This is the most secure method for managing your billing credentials.

Google OAuth 2.0 and User Credentials
This is the process that allows your app to act on a user's behalf without ever seeing their password.

Initial Setup: You will have already created an OAuth 2.0 Client ID in your Google Cloud Project.

User Action: On your Python app's frontend, a user clicks a "Sign in with Google" button. Your Python backend initiates the Google OAuth flow.

User Consent: The user is redirected to a Google Consent Screen  where they log in and grant your application permission to access specific services like Gmail and Drive.

Token Delivery: Upon successful consent, Google sends an authorization code back to your Python backend. Your backend then exchanges this code for a user-specific ID token and a short-lived access token.

Backend's Role: Your Python backend securely holds onto this accessToken and will pass it as a parameter in its HTTP request to the n8n webhook.

Automated n8n Workflow Configuration
This is the most critical part of the process, ensuring the right credentials are used at the right time.

Webhook Node: The n8n workflow starts with a Webhook node that listens for requests from your Python backend. It receives the user's prompt, their sessionId (for chat history), and their accessToken as a JSON payload.

Quota Management: Before anything else, the workflow should check the sessionId in your Firestore database to see if the user has exceeded their daily query quota. If so, the workflow ends and returns a "limit reached" message.

AI Agent's Role: If the quota is not met, the user's prompt is sent to the AI Agent node. The AI Agent's job is not to use the accessToken; its job is to analyze the prompt and decide which "tool" to call (e.g., "send an email," "create a drive file").

Tool Node Configuration: This is where the automation happens. Each of your Google tool nodes (e.g., Gmail Send, Google Drive) will be configured not to use a pre-saved credential. Instead, you'll set it to use the accessToken that was just received by the webhook. This is usually done by using a variable or expression that points to the incoming webhook data. This tells the node, "Hey, for this specific run of the workflow, use this user's access token to perform your action."

This architecture ensures that your personal API keys are kept secret, while the user's sensitive credentials are used only for a single task and never stored permanently in your workflow.

---

## To-Do List

- [x] Update `gemini_insight.md` with a to-do list.
- [ ] Update `docker-compose.yml` to remove `ollama` and `postgres`.
- [ ] Delete `app.py`.
- [ ] Create `requirements.txt` with necessary libraries for Google OAuth.
- [ ] Update `app_test_gemini.py` and `app_test.py` to include Google OAuth login and token handling.
- [ ] Update `templates/index.html` with a "Sign in with Google" button and to handle the login flow.
- [ ] Provide the JSON format for the token sent to n8n.

---

## Summary of Tool Authentication Issue (for future reference)

**Problem:**
The application's architecture involves passing a user-specific `accessToken` from an external Python app to the n8n workflow. The pre-built AI tool nodes in n8n (like the "Send a message in Gmail" tool) are not designed to use an externally provided `accessToken`. They are built to use credentials fully managed by n8n's internal credential store. This incompatibility causes an "Unable to sign without access token" error, even when the token is present in the workflow's data, because the node doesn't know how to access it.

**Solution:**
The correct solution is to replace the incompatible, pre-built AI tool nodes with the standard **"HTTP Request"** node. This provides full control over the API call.

**Implementation Steps:**
1.  **Replace the Node:** Delete the "Send a message in Gmail" node and replace it with an "HTTP Request" node.
2.  **Configure the Node:**
    *   **Method:** `POST`
    *   **URL:** The direct URL for the Google API endpoint (e.g., `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`).
    *   **Authentication:** Use a `Header Auth` credential.
    *   **Credential Configuration:** The `Header Auth` credential should be configured with a `Name` of `Authorization` and a `Value` of `Bearer {{ $json.accessToken }}` to correctly use the token from the workflow's input.
    *   **Body:** The request body must be manually constructed to match the API's requirements. For the Gmail API, this involves creating a `raw` parameter containing a base64url-encoded email message. This can be done with an n8n expression, for example: `={{ btoa( 'To: ' + $json.parameters.to + ... ) }}`.
3.  **Update Agent Prompt:** The AI Agent's system prompt must be updated to instruct it to output the necessary parameters (e.g., `to`, `subject`, `body`) that the "HTTP Request" node will need to build the API call body.