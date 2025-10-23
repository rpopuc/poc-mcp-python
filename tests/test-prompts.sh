#!/bin/bash
SID=$(http --headers POST http://localhost:8030/mcp \
  Accept:'application/json, text/event-stream' \
  Content-Type:application/json <<< '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": { "name": "httpie", "version": "3.x" }
    }
  }' | grep -i mcp-session-id | awk '{print $2}' | tr -d '\r')

http POST :8030/mcp \
  Accept:'application/json, text/event-stream' \
  mcp-session-id:$SID \
  Content-Type:application/json \
  <<< '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "prompts/list",
    "params": {}
  }'

http POST :8030/mcp \
  Accept:'application/json, text/event-stream' \
  mcp-session-id:$SID \
  Content-Type:application/json <<< '{
    "jsonrpc": "2.0",
    "id": 101,
    "method": "prompts/get",
    "params": {
      "name": "prompt-name",
      "arguments": {}
    }
  }'
