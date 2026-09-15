package sim

import "testing"

func TestParseEndpoint(t *testing.T) {
	cases := []struct {
		name     string
		raw      string
		wantWS   string
		wantREST string
	}{
		{"the documented default", DefaultWSBase, "ws://localhost:8000/api/ws", "http://localhost:8000/api"},
		{"bare host gets the default port and route", "ws://localhost", "ws://localhost:8000/api/ws", "http://localhost:8000/api"},
		{"http api form is mapped onto the socket", "http://localhost:8000/api", "ws://localhost:8000/api/ws", "http://localhost:8000/api"},
		{"https implies wss", "https://engine.example.com/api", "wss://engine.example.com:8000/api/ws", "https://engine.example.com:8000/api"},
		{"explicit port is kept", "ws://10.0.0.4:9000/api/ws", "ws://10.0.0.4:9000/api/ws", "http://10.0.0.4:9000/api"},
		{"trailing slash is tolerated", "ws://localhost:8000/api/ws/", "ws://localhost:8000/api/ws", "http://localhost:8000/api"},
		{"root path falls back to the api route", "ws://localhost:8000", "ws://localhost:8000/api/ws", "http://localhost:8000/api"},
		{"a custom prefix keeps its own rest base", "ws://localhost:8000/engine/ws", "ws://localhost:8000/engine/ws", "http://localhost:8000/engine"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseEndpoint(tc.raw)
			if err != nil {
				t.Fatalf("ParseEndpoint(%q) returned error: %v", tc.raw, err)
			}
			if got.WSBase != tc.wantWS {
				t.Errorf("WSBase = %q, want %q", got.WSBase, tc.wantWS)
			}
			if got.RESTBase != tc.wantREST {
				t.Errorf("RESTBase = %q, want %q", got.RESTBase, tc.wantREST)
			}
		})
	}
}

func TestParseEndpointRejectsBadInput(t *testing.T) {
	for _, raw := range []string{
		"",
		"   ",
		"localhost:8000",
		"ftp://localhost:8000/api",
		"ws://",
		"ws://host with space:8000/api",
	} {
		if _, err := ParseEndpoint(raw); err == nil {
			t.Errorf("ParseEndpoint(%q) returned no error, want a rejection", raw)
		}
	}
}

func TestEndpointRunURL(t *testing.T) {
	ep, err := ParseEndpoint(DefaultWSBase)
	if err != nil {
		t.Fatalf("ParseEndpoint: %v", err)
	}
	got, err := ep.RunURL("abc123")
	if err != nil {
		t.Fatalf("RunURL: %v", err)
	}
	if want := "ws://localhost:8000/api/ws/abc123"; got != want {
		t.Errorf("RunURL = %q, want %q", got, want)
	}
}

func TestEndpointRunURLRejectsBadIDs(t *testing.T) {
	ep, _ := ParseEndpoint(DefaultWSBase)
	for _, id := range []string{"", "  ", "a/b", "a?b", "a#b"} {
		if _, err := ep.RunURL(id); err == nil {
			t.Errorf("RunURL(%q) returned no error, want a rejection", id)
		}
	}
}
