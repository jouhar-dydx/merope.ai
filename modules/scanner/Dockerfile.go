FROM golang:1.22

WORKDIR /app

# Install required system packages
RUN apt-get update && \
    apt-get install -y git gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .

# Only run 'go mod init' if go.mod doesn't exist
RUN if [ ! -f go.mod ]; then \
        go mod init merope-scanner; \
    fi && \
    go mod tidy && \
    CGO_ENABLED=0 go build -o /scanner ec2_scanner.go

CMD ["/scanner"]
