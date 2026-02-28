FROM python:3.10-slim
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install flask psycopg2-binary pandas openpyxl fpdf requests
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]