FROM postgres:16-alpine

RUN apk add --no-cache python3 py3-cryptography

WORKDIR /app
COPY backup_recovery.py /app/backup_recovery.py

ENTRYPOINT ["python3", "/app/backup_recovery.py"]
