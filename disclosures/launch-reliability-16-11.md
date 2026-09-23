# Launch reliability and verification

Migrated: 2026-09-23 16:11 (Asia/Almaty, UTC+05:00). This records the migration time; the original work times were not recorded.

- Codex clarified reviewer terminal-lifetime/readiness instructions and added regression tests that launch the real shell entry point, check repeated HTTP requests, stop/restart the server and verify missing-input/occupied-port failures. These bounded checks do not establish indefinite uptime or replace a second-machine rehearsal.
