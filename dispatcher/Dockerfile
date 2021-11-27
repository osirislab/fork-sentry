FROM golang:1.16-buster as builder

WORKDIR /app

# Copy over and build bot for execution
COPY go.* ./
RUN go mod download
COPY . ./
RUN go build -v -o dispatcher

FROM debian:buster-slim
RUN set -x && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Start bot
COPY --from=builder /app/dispatcher /app/dispatcher
CMD ["/app/dispatcher"]
