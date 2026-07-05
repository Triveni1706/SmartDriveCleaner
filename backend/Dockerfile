FROM python:3.12-slim

WORKDIR /app

# System deps: libgl1/libglib for opencv-python-headless, unrar for archive_analyzer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Reports and any scan-target mount point
RUN mkdir -p /app/reports

EXPOSE 8811

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8811"]
