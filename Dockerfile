FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 
    PYTHONDONTWRITEBYTECODE=1 
    PIP_NO_CACHE_DIR=1 
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends 
    build-essential 
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Install the application
RUN pip install -e .

# Expose the Streamlit port
EXPOSE 8501

# Command to run the dashboard
CMD ["streamlit", "run", "src/vcp_screener/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
