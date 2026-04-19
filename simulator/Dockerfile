FROM alpine:3.20

RUN apk add --no-cache bash curl docker-cli grep sed coreutils

WORKDIR /home/opc/security-research

CMD ["bash", "attacks/mixed_traffic_simulator.sh"]
