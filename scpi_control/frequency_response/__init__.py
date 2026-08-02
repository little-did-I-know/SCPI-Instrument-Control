"""Frequency response (Bode) measurement: sweep a source, capture, estimate.

See docs/user-guide/frequency-response.md. Every accuracy claim in this package
is validated against a mock instrument and an analytic RC model, never against
real hardware -- there is no function generator on the development bench.
"""
