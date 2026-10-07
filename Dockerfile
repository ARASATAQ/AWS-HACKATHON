FROM python:3.11-slim

WORKDIR /app

COPY disaster_system/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY disaster_system/ .

# Expose the port App Runner expects (8080)
EXPOSE 8080

# Command to run the FastAPI application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
