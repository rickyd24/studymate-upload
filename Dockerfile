FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home app && mkdir /data && chown app:app /data
COPY app.py extract_pdf.py index.html style.css upload.js ./
USER app
ENV DATABASE_PATH=/data/materials.sqlite3
EXPOSE 8080
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--timeout", "45", "--access-logfile", "-"]
