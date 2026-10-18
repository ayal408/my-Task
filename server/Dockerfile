FROM python:3.12-slim
WORKDIR /app
COPY certs/ /tmp/local-certs/
RUN cat /etc/ssl/certs/ca-certificates.crt > /tmp/combined-ca.pem \
    && for cert in /tmp/local-certs/*.crt; do if [ -f "$cert" ]; then cat "$cert" >> /tmp/combined-ca.pem; printf '\n' >> /tmp/combined-ca.pem; fi; done
ENV PIP_CERT=/tmp/combined-ca.pem SSL_CERT_FILE=/tmp/combined-ca.pem REQUESTS_CA_BUNDLE=/tmp/combined-ca.pem
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
