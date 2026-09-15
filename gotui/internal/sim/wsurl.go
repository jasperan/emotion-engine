// Package sim holds the pure, server-free core of the gotui front-end: endpoint
// parsing and the argv builders that mirror the `emotionsim` click options.
//
// Everything here is deterministic and testable without a running engine, which
// is the only mode available when the FastAPI server and vLLM are unreachable.
package sim

import (
	"fmt"
	"net/url"
	"strings"
)

const (
	// DefaultWSBase matches `emotionsim monitor --url` (emotionsim/cli.py:714).
	DefaultWSBase = "ws://localhost:8000/api/ws"
	// wsSuffix is the route the server registers the socket on:
	// @router.websocket("/ws/{run_id}") under the /api prefix.
	wsSuffix = "/ws"
)

// Endpoint is the validated pair of bases the front-end talks to. The REST base
// is derived from the socket base so the two can never disagree.
type Endpoint struct {
	// WSBase is the socket base, e.g. ws://localhost:8000/api/ws.
	WSBase string
	// RESTBase is the HTTP base for the same server, e.g. http://localhost:8000/api.
	RESTBase string
}

// RunURL returns the socket URL for one run: {WSBase}/{runID}, which is what
// `emotionsim monitor` builds in _monitor_websocket.
func (e Endpoint) RunURL(runID string) (string, error) {
	id := strings.TrimSpace(runID)
	if id == "" {
		return "", fmt.Errorf("run id is required")
	}
	if strings.ContainsAny(id, "/?#") {
		return "", fmt.Errorf("run id %q must not contain a path separator or query", id)
	}
	return e.WSBase + "/" + id, nil
}

// ParseEndpoint validates a socket base URL and derives the REST base from it.
//
// Accepted schemes are ws/wss, plus http/https which are mapped onto their
// socket equivalents so a user can paste whichever form they have to hand.
// A bare host gets the default port, and a path that is not already the socket
// route gets /ws appended, so "http://host:8000/api" and "ws://host:8000/api/ws"
// both resolve to the same engine.
func ParseEndpoint(raw string) (Endpoint, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return Endpoint{}, fmt.Errorf("endpoint is required")
	}
	if strings.ContainsAny(trimmed, " \t\n") {
		return Endpoint{}, fmt.Errorf("endpoint %q must not contain whitespace", trimmed)
	}

	u, err := url.Parse(trimmed)
	if err != nil {
		return Endpoint{}, fmt.Errorf("endpoint %q is not a valid URL: %w", trimmed, err)
	}

	var wsScheme, httpScheme string
	switch strings.ToLower(u.Scheme) {
	case "ws":
		wsScheme, httpScheme = "ws", "http"
	case "wss":
		wsScheme, httpScheme = "wss", "https"
	case "http":
		wsScheme, httpScheme = "ws", "http"
	case "https":
		wsScheme, httpScheme = "wss", "https"
	case "":
		return Endpoint{}, fmt.Errorf("endpoint %q needs a scheme, e.g. %s", raw, DefaultWSBase)
	default:
		return Endpoint{}, fmt.Errorf("endpoint scheme %q is not supported; use ws, wss, http or https", u.Scheme)
	}

	host := u.Hostname()
	if host == "" {
		return Endpoint{}, fmt.Errorf("endpoint %q has no host", raw)
	}
	port := u.Port()
	if port == "" {
		port = "8000"
	}
	authority := host + ":" + port

	path := strings.TrimRight(u.Path, "/")
	switch {
	case path == "":
		path = "/api" + wsSuffix
	case strings.HasSuffix(path, wsSuffix):
		// already the socket route
	case strings.HasSuffix(path, "/api"):
		path += wsSuffix
	default:
		path += wsSuffix
	}

	restPath := strings.TrimSuffix(path, wsSuffix)
	if restPath == "" {
		restPath = "/"
	}

	return Endpoint{
		WSBase:   wsScheme + "://" + authority + path,
		RESTBase: httpScheme + "://" + authority + restPath,
	}, nil
}
