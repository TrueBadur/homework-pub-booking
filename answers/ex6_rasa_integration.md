# Ex6 — Rasa structured half

## Your answer

The RasaStructuredHalf subclass overrides run() to send a booking intent to Rasa’s REST webhook and process the
response.

### Dataflow & Execution

1. Payload Pipeline: The loop half generates raw booking data $\rightarrow$ StructuredHalf
runs normalise_booking_payload (via validator.py) to convert it into a canonical, Rasa-compatible message $\rightarrow$
sent via urllib POST $\rightarrow$ response parsed for custom {action: committed} or {action: rejected} slots.
2. Offline Testing: A standard library http.server thread mimics the Rasa webhook. For basic unit tests, it always returns a
confirmation. To test rejections, Exercise 7 uses specific loop half arguments to trigger a rejected response.
### Key DesignChoices
- Exception Handling: ValidationFailed is raised in normalise_booking_payload and caught directly within run() to
satisfy the StructuredHalf contract, which requires returning a HalfResult.
- Network Failures: Connection errors return
success=False along with an SA_EXT_SERVICE_UNAVAILABLE status, leaving retry logic to the caller.
- Session Consistency:
The sender_id is a stable hash of (venue+date+time), ensuring the Rasa tracker remains consistent across retries in a
single session.

## Citations

- starter/rasa_half/validator.py — normalise_booking_payload + helpers
- starter/rasa_half/structured_half.py — RasaStructuredHalf.run + mock server
