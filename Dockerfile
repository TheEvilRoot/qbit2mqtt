FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY qbit2mqtt /app/qbit2mqtt

ENV PYTHONPATH=/app
CMD ["python", "qbit2mqtt/__init__.py"]