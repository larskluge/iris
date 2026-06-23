package main

import "testing"

func TestDecodeEnvelope(t *testing.T) {
	j := []byte(`{"task_id":"t1","to":"calliope","skill":"draft","payload":{"brief":"hi"},"reply_subject":"iris.results.t1","local_only":true}`)
	e, err := DecodeEnvelope(j)
	if err != nil {
		t.Fatal(err)
	}
	if e.To != "calliope" || e.Skill != "draft" || !e.LocalOnly {
		t.Fatalf("bad envelope: %+v", e)
	}
	if e.Payload["brief"] != "hi" {
		t.Fatalf("bad payload: %+v", e.Payload)
	}
}
