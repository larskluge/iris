package main

import "encoding/json"

// Envelope is the async task shape shared with the Python side (models.py:TaskEnvelope).
type Envelope struct {
	TaskID    string         `json:"task_id"`
	To        string         `json:"to"`
	Skill     string         `json:"skill"`
	Payload   map[string]any `json:"payload"`
	Reply     string         `json:"reply_subject"`
	LocalOnly bool           `json:"local_only"`
}

func DecodeEnvelope(b []byte) (*Envelope, error) {
	var e Envelope
	err := json.Unmarshal(b, &e)
	return &e, err
}
