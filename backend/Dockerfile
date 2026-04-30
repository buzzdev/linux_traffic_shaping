FROM python:3.12-slim

# iproute2 provides tc and ip commands; network-manager provides nmcli for hotspot management;
# iptables needed to fix Docker FORWARD chain for hotspot NAT; iw for wifi client list
RUN apt-get update \
    && apt-get install -y --no-install-recommends iproute2 network-manager iptables iw \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
