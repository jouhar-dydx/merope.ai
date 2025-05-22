FROM golang:1.21

WORKDIR /app

# Install required tools
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy source code
COPY . .

# Build binary
RUN go mod init merope-scanner && \
    go mod tidy && \
    CGO_ENABLED=0 go build -o /scanner ec2_scanner.go

CMD ["/scanner"]
