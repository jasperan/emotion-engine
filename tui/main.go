package main

import "github.com/jasperan/emotion-engine/tui/cmd"

var version = "dev"

func main() {
	cmd.Version = version
	cmd.Execute()
}
