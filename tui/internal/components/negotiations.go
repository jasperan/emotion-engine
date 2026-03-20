package components

import (
	"fmt"
	"strings"

	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// NegotiationStatus describes the current state of a proposal.
type NegotiationStatus int

const (
	NegPending  NegotiationStatus = iota
	NegAccepted                   // proposal was accepted
	NegRejected                   // proposal was rejected
	NegExpired                    // proposal timed out
	NegCountered                  // counter-proposal issued
)

// NegotiationEntry holds a single proposal and all responses to it.
type NegotiationEntry struct {
	ProposalID string
	Proposer   string
	Target     string
	Terms      string
	Status     NegotiationStatus
	Step       int
	Responses  []NegotiationResponse
}

// NegotiationResponse is one agent's reply to a proposal.
type NegotiationResponse struct {
	AgentName string
	Action    string // "accepted", "rejected", "countered"
	Detail    string
	Step      int
}

// NegotiationTheaterData is the render input for the negotiations panel.
type NegotiationTheaterData struct {
	Entries   []NegotiationEntry
	ScrollPos int
	Width     int
	Height    int
}

// statusIcon returns the coloured icon for a proposal status.
func statusIcon(s NegotiationStatus) string {
	switch s {
	case NegAccepted:
		return theme.StatusActive.Render("+")
	case NegRejected:
		return theme.ErrorText.Render("x")
	case NegExpired:
		return theme.MutedText.Render("-")
	case NegCountered:
		return theme.HazardMedium.Render("~")
	default: // NegPending
		return theme.HazardMedium.Render("*")
	}
}

// actionStyle colours an action label.
func actionStyle(action string) string {
	switch action {
	case "accepted":
		return theme.StatusActive.Render(action)
	case "rejected":
		return theme.ErrorText.Render(action)
	case "countered":
		return theme.HazardMedium.Render(action)
	default:
		return theme.MutedText.Render(action)
	}
}

// RenderNegotiationTheater renders the proposal timeline panel.
func RenderNegotiationTheater(d NegotiationTheaterData) string {
	subtitle := theme.Subtitle.Render("NEGOTIATIONS")

	if len(d.Entries) == 0 {
		body := subtitle + "\n\n" + theme.MutedText.Render("No negotiations yet...")
		return theme.Panel.Width(d.Width - 2).Height(d.Height - 2).Render(body)
	}

	var lines []string
	lines = append(lines, subtitle)
	lines = append(lines, "")

	for _, entry := range d.Entries {
		icon := statusIcon(entry.Status)
		terms := entry.Terms
		if len(terms) > 40 {
			terms = terms[:40] + "..."
		}
		header := fmt.Sprintf("%s %s -> %s: %q [step %d]",
			icon, entry.Proposer, entry.Target, terms, entry.Step)
		lines = append(lines, header)

		for _, resp := range entry.Responses {
			action := actionStyle(resp.Action)
			line := fmt.Sprintf("  +-- %s %s", resp.AgentName, action)
			if resp.Detail != "" {
				detail := resp.Detail
				if len(detail) > 30 {
					detail = detail[:30] + "..."
				}
				line += ": " + detail
			}
			line += fmt.Sprintf(" [step %d]", resp.Step)
			lines = append(lines, line)
		}

		lines = append(lines, "") // spacing between proposals
	}

	// Apply scroll offset
	if d.ScrollPos > 0 && d.ScrollPos < len(lines) {
		lines = lines[d.ScrollPos:]
	}

	body := strings.Join(lines, "\n")
	return theme.Panel.Width(d.Width - 2).Height(d.Height - 2).Render(body)
}
