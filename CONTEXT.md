# Posture Guard

Posture Guard helps a Mac user keep an individually calibrated sitting posture by applying a consequence when their current posture drifts away from their reference posture.

## Language

**Reference Posture**:
The user's personally calibrated good posture. It is the baseline that later posture observations are compared against.
_Avoid_: correct posture, absolute good posture

**Posture Deviation**:
A sustained difference between the current posture observation and the **Reference Posture** large enough to count as bad posture for this user.
_Avoid_: bad posture, wrong posture

**Manual Recovery**:
The user intentionally restores connectivity after a **Posture Deviation** consequence. Monitoring resumes only after the user performs this recovery.
_Avoid_: automatic recovery, auto reconnect

## Example Dialogue

Developer: "Should we detect universally bad posture?"
Domain expert: "No. First capture the user's Reference Posture, then treat a large enough sustained difference from it as Posture Deviation."

Developer: "Should the app turn connectivity back on when posture improves?"
Domain expert: "No. The user must perform Manual Recovery, and monitoring resumes after that."
