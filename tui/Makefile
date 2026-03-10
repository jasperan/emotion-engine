BINARY := emotionsim-tui
VERSION := 0.1.0
GOFLAGS := -ldflags "-s -w -X main.version=$(VERSION)"

.PHONY: build run clean ssh

build:
	go build $(GOFLAGS) -o $(BINARY) .

run:
	go run . --server http://localhost:8000

clean:
	rm -f $(BINARY)

ssh:
	go run . --server http://localhost:8000 --ssh-port 2222
