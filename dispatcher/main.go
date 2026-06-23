// The Calliope dispatcher: a durable NATS JetStream pull-worker that drains
// iris.tasks.<node>, runs each task in a fresh hermetic agent container
// (podman run, §7.6), and publishes the result. Offline durability falls out
// of JetStream: tasks published while this is down wait in the stream and are
// drained on restart.
package main

import (
	"encoding/json"
	"log"
	"os"
	"os/exec"
	"time"

	"github.com/nats-io/nats.go"
)

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func runAgent(image string, envelope []byte) ([]byte, error) {
	host := "host.containers.internal"
	args := []string{
		"run", "--rm",
		"--add-host", host + ":host-gateway",
		"-e", "CALLIOPE_OLLAMA_BASE_URL=http://" + host + ":11434",
		"-e", "CALLIOPE_LETTA_BASE_URL=http://" + host + ":8283",
		"-e", "CALLIOPE_PG_DSN=postgresql://calliope:calliope@" + host + ":5434/calliope",
		"-e", "CALLIOPE_MYCELIUM_PG_DSN=postgresql://postgres:postgres@" + host + ":5433/mycelium_dev",
		image, "serve-task", string(envelope),
	}
	return exec.Command("podman", args...).Output()
}

func handle(nc *nats.Conn, image string, m *nats.Msg) {
	e, err := DecodeEnvelope(m.Data)
	if err != nil {
		log.Printf("bad envelope, terminating: %v", err)
		_ = m.Term()
		return
	}
	result, err := runAgent(image, m.Data)
	if err != nil {
		log.Printf("agent run failed for %s: %v", e.TaskID, err)
		_ = m.Nak()
		return
	}
	reply := e.Reply
	if reply == "" {
		reply = "iris.results." + e.TaskID
	}
	_ = nc.Publish(reply, result)
	_ = nc.Flush()
	_ = m.Ack()
	log.Printf("done %s -> %s", e.TaskID, reply)
}

func main() {
	url := env("NATS_URL", nats.DefaultURL)
	image := env("CALLIOPE_IMAGE", "calliope-agent:latest")
	node := env("IRIS_NODE", "calliope")

	nc, err := nats.Connect(url, nats.MaxReconnects(-1))
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()
	js, err := nc.JetStream()
	if err != nil {
		log.Fatal(err)
	}

	// Durable work-queue stream over iris.tasks.* — retains tasks for offline nodes.
	if _, err := js.AddStream(&nats.StreamConfig{
		Name:      "IRIS_TASKS",
		Subjects:  []string{"iris.tasks.*"},
		Retention: nats.WorkQueuePolicy,
	}); err != nil {
		log.Printf("AddStream (ok if exists): %v", err)
	}

	subject := "iris.tasks." + node
	sub, err := js.PullSubscribe(subject, "dispatcher-"+node, nats.AckExplicit())
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("dispatcher up: draining %s via image %s", subject, image)

	if jb, _ := json.Marshal(map[string]string{"subject": subject, "image": image}); jb != nil {
		log.Printf("config: %s", jb)
	}

	for {
		msgs, err := sub.Fetch(1, nats.MaxWait(2*time.Second))
		if err != nil {
			continue // timeout: no messages, keep polling
		}
		for _, m := range msgs {
			handle(nc, image, m)
		}
	}
}
