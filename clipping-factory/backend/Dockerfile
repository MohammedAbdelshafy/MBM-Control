FROM mcr.microsoft.com/playwright/python:v1.47.0-noble

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    git \
    libgl1 \
    libglib2.0-0 \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Higgsfield CLI
RUN curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
