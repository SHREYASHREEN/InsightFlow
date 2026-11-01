# Known Limitations
- Prototype only: not deployed, no HTTPS, no password-reset email, no account lockout or rate limiting.
- Session state lives in Streamlit's browser session; there is no server-side session expiry.
- SQLite is suitable for a single user or light use, not heavy concurrency.
- SLA uses calendar hours in UTC; no business hours, holidays or time zones. Pending Info time is not paused.
- The sample request history is generated with a fixed random seed, so the numbers are illustrative, not real.
- Changing SLA settings does not recalculate existing deadlines.
- Dependencies are validated as text IDs (comma-separated), not a separate relation table.
- Automated tests cover the logic; the Streamlit UI is only smoke-tested with stub modules. Layout, colours and real clicking
  must be checked manually in a browser.
- Streamlit may show deprecation notices about `use_container_width` in newer releases; behaviour is unaffected.
