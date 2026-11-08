FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts/uvicorn-wrapper.sh /usr/local/bin/uvicorn
RUN chmod +x /usr/local/bin/uvicorn
EXPOSE 8000
CMD ["python", "-m", "app"]
