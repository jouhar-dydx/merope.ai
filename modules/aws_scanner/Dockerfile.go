FROM golang:1.21-alpine

WORKDIR /app

RUN apk add --no-cache git gcc musl-dev

COPY . .

RUN go mod init merope-scanner && \
    go mod tidy && \
    go build -o /scanner ec2_scanner.go

CMD ["/scanner"]