package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// FeedEntry represents a single message in the feed.
type FeedEntry struct {
	AgentName   string
	Content     string
	MessageType string
	Location    string
	Step        int
}

// MessageFeedData holds data for rendering the message feed.
type MessageFeedData struct {
	Entries   []FeedEntry
	ScrollPos int
	Height    int
	Width     int
}

// RenderMessageFeed renders a scrollable conversation feed grouped by location.
func RenderMessageFeed(d MessageFeedData) string {
	if len(d.Entries) == 0 {
		return theme.MutedText.Render("No messages yet...")
	}

	contentWidth := d.Width - 4 // padding
	if contentWidth < 1 {
		contentWidth = 1
	}

	var rendered []string
	currentLocation := ""

	for _, entry := range d.Entries {
		// Location header when location changes
		if entry.Location != currentLocation {
			currentLocation = entry.Location
			locHeader := theme.Subtitle.Render(fmt.Sprintf("── %s ──", currentLocation))
			rendered = append(rendered, "", locHeader)
		}

		// Agent name + step
		header := fmt.Sprintf("%s %s",
			theme.AgentName.Render(entry.AgentName),
			theme.MutedText.Render(fmt.Sprintf("[step %d]", entry.Step)),
		)

		// Truncate long messages
		content := entry.Content
		maxContentLen := contentWidth * 3 // allow ~3 lines
		if len(content) > maxContentLen {
			content = content[:maxContentLen] + "..."
		}

		// Style based on message type
		var msgStyle lipgloss.Style
		switch entry.MessageType {
		case "error":
			msgStyle = theme.ErrorText
		case "system":
			msgStyle = theme.MutedText
		default:
			msgStyle = theme.TokenText
		}

		rendered = append(rendered, header, msgStyle.Render(content))
	}

	// Apply scroll
	allLines := strings.Split(strings.Join(rendered, "\n"), "\n")

	start := d.ScrollPos
	if start < 0 {
		start = 0
	}
	if start >= len(allLines) {
		start = len(allLines) - 1
	}
	if start < 0 {
		start = 0
	}

	end := start + d.Height
	if end > len(allLines) {
		end = len(allLines)
	}

	visible := allLines[start:end]
	return strings.Join(visible, "\n")
}
