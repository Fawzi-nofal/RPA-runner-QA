FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "run_rpa.py", "scenarios/example_login.yaml"]
