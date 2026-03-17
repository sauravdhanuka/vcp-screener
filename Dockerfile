FROM python:3.11-slim-bookworm

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

# Timezone
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Layer caching: install deps first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Install package (provides `vcp` CLI entry point)
RUN pip install --no-cache-dir -e .

# Data directory
RUN mkdir -p /app/data

EXPOSE 8501

CMD ["streamlit", "run", "src/vcp_screener/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
