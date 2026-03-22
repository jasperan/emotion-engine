package api

import (
	"encoding/json"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// WSEventHandler is a callback invoked for each incoming WebSocket message.
type WSEventHandler func(msg WSMessage)

// WSDisconnectHandler is called when the connection is lost.
type WSDisconnectHandler func()

// WSClient manages a WebSocket connection to the EmotionSim backend.
type WSClient struct {
	serverURL    string
	conn         *websocket.Conn
	mu           sync.Mutex
	connected    bool
	done         chan struct{}
	onDisconnect WSDisconnectHandler
}

// NewWSClient creates a new WebSocket client for the given server URL.
func NewWSClient(serverURL string) *WSClient {
	return &WSClient{
		serverURL: serverURL,
	}
}

// SetDisconnectHandler registers a callback for when the WS connection drops.
func (ws *WSClient) SetDisconnectHandler(h WSDisconnectHandler) {
	ws.mu.Lock()
	ws.onDisconnect = h
	ws.mu.Unlock()
}

// Connect establishes a WebSocket connection for the given run and starts
// reading messages. The handler is called for each incoming WSMessage.
func (ws *WSClient) Connect(runID string, handler WSEventHandler) error {
	// Convert http(s):// to ws(s)://
	wsURL := ws.serverURL
	wsURL = strings.Replace(wsURL, "https://", "wss://", 1)
	wsURL = strings.Replace(wsURL, "http://", "ws://", 1)
	wsURL = wsURL + "/api/ws/" + runID

	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		return err
	}

	ws.mu.Lock()
	ws.conn = conn
	ws.connected = true
	ws.done = make(chan struct{})
	ws.mu.Unlock()

	go ws.readLoop(handler)
	go ws.pingLoop()

	return nil
}

// readLoop continuously reads JSON messages from the WebSocket connection.
func (ws *WSClient) readLoop(handler WSEventHandler) {
	defer func() {
		ws.mu.Lock()
		ws.connected = false
		cb := ws.onDisconnect
		ws.mu.Unlock()
		if cb != nil {
			cb()
		}
	}()

	for {
		select {
		case <-ws.done:
			return
		default:
		}

		ws.mu.Lock()
		conn := ws.conn
		ws.mu.Unlock()
		if conn == nil {
			return
		}

		_, message, err := conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseNormalClosure) {
				log.Printf("websocket read error: %v", err)
			}
			return
		}

		var msg WSMessage
		if err := json.Unmarshal(message, &msg); err != nil {
			log.Printf("websocket unmarshal error: %v", err)
			continue
		}

		handler(msg)
	}
}

// pingLoop sends a WebSocket ping every 15 seconds to keep the connection alive.
func (ws *WSClient) pingLoop() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ws.done:
			return
		case <-ticker.C:
			ws.mu.Lock()
			if ws.conn == nil {
				ws.mu.Unlock()
				return
			}
			pingData, _ := json.Marshal(WSCommand{Type: "ping"})
			err := ws.conn.WriteMessage(websocket.TextMessage, pingData)
			ws.mu.Unlock()
			if err != nil {
				log.Printf("websocket ping error: %v", err)
				return
			}
		}
	}
}

// IsConnected returns whether the WebSocket connection is currently active.
func (ws *WSClient) IsConnected() bool {
	ws.mu.Lock()
	defer ws.mu.Unlock()
	return ws.connected
}

// Close shuts down the WebSocket connection and stops all goroutines.
func (ws *WSClient) Close() {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	if ws.done != nil {
		select {
		case <-ws.done:
			// already closed
		default:
			close(ws.done)
		}
	}

	if ws.conn != nil {
		ws.conn.Close()
		ws.conn = nil
	}
	ws.connected = false
}
