FROM python:3.12-alpine3.22
RUN apk add --no-cache curl iproute2 bind-tools iptables && adduser -D -u 10001 lab
WORKDIR /opt/lab
COPY service.py /opt/lab/service.py
USER 10001:10001
CMD ["python", "-u", "/opt/lab/service.py"]
