# Agent Alpha: AI-Powered Automation Platform

## Project Overview

Agent Alpha is a robust, locally-hosted AI automation platform designed to streamline complex workflows by integrating large language models (LLMs) with powerful automation tools. This project leverages `docker-compose` to orchestrate three core services:

*   **Ollama:** For running and managing various large language models (LLMs) locally, enabling AI capabilities such as text generation, understanding, and potentially multimodal interactions.
*   **n8n:** A powerful workflow automation tool that allows you to connect various services, APIs, and custom logic to create sophisticated automated processes.
*   **PostgreSQL:** A reliable and scalable relational database serving as the persistent data store for n8n, ensuring workflow data and configurations are securely managed.

This setup provides a self-contained environment for developing and deploying AI-driven automation solutions, keeping your data and models local.

## Features

*   **Local LLM Hosting:** Run cutting-edge language models directly on your machine via Ollama.
*   **Workflow Automation:** Design and execute complex automation workflows using n8n.
*   **Persistent Data Storage:** Securely store n8n data and configurations with PostgreSQL.
*   **GPU Acceleration:** Leverage NVIDIA GPUs for accelerated LLM inference (if available and configured).
*   **Pre-loaded Workflows:** Easily share and deploy n8n workflows by simply placing them in a designated directory.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Docker:** [Install Docker](https://docs.docker.com/get-docker/)
*   **Docker Compose:** Docker Desktop typically includes Docker Compose. If not, [install Docker Compose](https://docs.docker.com/compose/install/).

## Getting Started

Follow these steps to set up and run Agent Alpha on your local machine.

### 1. Clone the Repository

First, clone this repository to your local machine:

```bash
git clone https://github.com/your-username/Agent-Alpha.git
cd Agent-Alpha
```
*(Note: Replace `https://github.com/your-username/Agent-Alpha.git` with the actual repository URL if different.)*

### 2. Configure Credentials and Environment Variables

Sensitive information for n8n and PostgreSQL is managed via environment variables within the `docker-compose.yml` file. It is highly recommended to use a `.env` file for production environments, but for local development, you can directly edit the `docker-compose.yml` for simplicity.

**n8n Credentials:**

Locate the `n8n` service in `docker-compose.yml` and modify the following environment variables:

```yaml
  n8n:
    # ...
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin             # <--- Change 'admin' to your desired username
      - N8N_BASIC_AUTH_PASSWORD=yourpassword  # <--- Change 'yourpassword' to a strong password
      # ...
```
**PostgreSQL Credentials:**

Locate the `postgres` service in `docker-compose.yml` and modify the following environment variables:

```yaml
  postgres:
    # ...
    environment:
      - POSTGRES_PASSWORD=mysecretpassword    # <--- Change 'mysecretpassword' to a strong password
      - POSTGRES_USER=postgres                # <--- Change 'postgres' if desired
      - POSTGRES_DB=n8n                       # <--- Change 'n8n' if desired
    # ...
```
**Important Security Note:** For production deployments, never hardcode credentials directly in `docker-compose.yml`. Instead, use a `.env` file and reference variables like `${N8N_BASIC_AUTH_PASSWORD}` in your `docker-compose.yml`.

### 3. Start the Services

Once you have configured the credentials and placed any desired n8n workflows, start all services using Docker Compose:

```bash
docker-compose up -d
```
The `-d` flag runs the services in detached mode, allowing them to run in the background.

### 4. Pull Language Models (Ollama)

After the Ollama service is up and running, you can pull the required language models.

**Pulling Llama 3.1 (Text-only):**

To pull the standard Llama 3.1 model for text conversations:

```bash
docker exec ollama ollama pull llama3.1
```

**Pulling Gemma 3 (Text-only):**

To pull the Gemma 3 model:

```bash
docker exec ollama ollama pull gemma3:latest
```

**Regarding Multimodal Models (Image Detection):**

The base Llama 3.1 and Gemma 3 models are primarily text-only. If you require image detection capabilities, you will need to:

*   **Search for a Multimodal Llama 3.1 Variant on Ollama:** Look for models specifically fine-tuned for vision, often named with "vision" or "multimodal" in their tags (e.g., `llama3.1-vision`). You can browse available models on the [Ollama website](https://ollama.com/library) or by running `docker exec ollama ollama list` (though this only shows downloaded models).
*   **Integrate with External Vision Tools:** Alternatively, you can use a separate computer vision tool or API for image detection and then pass the textual results to your Llama 3.1 model in n8n for further processing.

Once you identify a multimodal model on Ollama, you can pull it using a similar command:

```bash
docker exec ollama ollama pull <multimodal_model_name>
```
*(Replace `<multimodal_model_name>` with the actual model tag, e.g., `llava` or `llama3.1-vision` if it exists).*

### 5. Accessing the Services

*   **n8n User Interface:**
    Open your web browser and navigate to: `http://localhost:5678`
    Log in using the `N8N_BASIC_AUTH_USER` and `N8N_BASIC_AUTH_PASSWORD` you configured.

*   **Ollama API:**
    The Ollama API is accessible internally within the Docker network at `http://ollama:11434`. From your host machine, it's exposed at `http://localhost:11434`.

*   **PostgreSQL Database:**
    The PostgreSQL database is accessible internally within the Docker network at `my-postgres:5432`. From your host machine, it's exposed at `localhost:5432`.

## Stopping the Services

To stop all running services:

```bash
docker-compose down
```
This command will stop and remove the containers, networks, and volumes created by `docker-compose up`. Your `ollama` and `postgres-data` volumes (and `n8n` workflows) will persist on your host machine.

## Troubleshooting

*   **Port Conflicts:** If you encounter errors related to ports already being in use, ensure no other applications are using `5678`, `11434`, or `5432`. You can change the host port mappings in `docker-compose.yml` if necessary (e.g., `5679:5678`).
*   **Ollama GPU Issues:** If Ollama fails to start or utilize your GPU, ensure your NVIDIA drivers are up to date and that Docker has proper GPU support configured. Refer to the [Ollama documentation](https://ollama.com/blog/ollama-is-now-available-as-a-docker-image) for more details.
*   **n8n Database Connection:** If n8n fails to connect to PostgreSQL, double-check the `DB_POSTGRESDB_HOST`, `DB_POSTGRESDB_USER`, `DB_POSTGRESDB_PASSWORD`, and `DB_POSTGRESDB_DATABASE` environment variables in `docker-compose.yml`. Ensure the `postgres` service is fully up and running before n8n attempts to connect.
