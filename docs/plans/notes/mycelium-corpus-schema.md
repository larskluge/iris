# mycelium corpus schema (M1 spike, 2026-06-23)

Read-only introspection of the Mycelium read models. Dev data lives locally in
the `mycelium_postgres` container (db `mycelium_dev`, `postgres/postgres`,
localhost:5433); **prod is `mycelium_prod` on outpost** — point
`CALLIOPE_MYCELIUM_PG_DSN` there (readonly role / SSH tunnel) for the real seed.
The schema is the same.

## Sent emails — table `emails` (~19k rows in dev)
- Content: `body_clean` (cleaned text; fallback `body_text`), `subject`.
- Sender: `from_address`, `from_name`. **Sent-by-Lars = `from_address = ANY(self_emails)`**
  where self_emails ≈ `l@larskluge.com`, `me@aekym.com`, `la@aekym.com`, `andreas@aekym.com`.
- Recipient: `to_addresses` (jsonb). Time: `internal_date`. Soft-delete: `deleted_at`.
- (Gmail SENT label also exists — `gmail_labels.name='SENT'` — but from_address is simpler/robust.)

## Sent messages — table `messages` (~99k rows in dev)
- Content: `body`. Platform: `platform` (whatsapp ~62k, telegram ~36k).
- Sender: `sender_name`, `sender_id`. **Sent-by-Lars = `sender_name = ANY(self_names)`**
  where self_names ≈ `Lars`, `Lars Kluge` (~15.3k rows). Time: `sent_at`. Soft-delete: `deleted_at`.

## Language
Not stored — detected at seed time (langdetect) to split EN/DE sections.

## Normalized shape (`CorpusRecord`)
`{ kind: 'email'|'message', text, recipient?, subject?, platform?, sent_at? }`
