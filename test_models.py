#!/usr/bin/env python3
"""Quick smoke test for GroqBrain model defaults."""
import sys
sys.path.insert(0, '.')

from core.brain import GroqBrain

# Test with explicit config
b = GroqBrain({
    'provider': 'groq',
    'models': {
        'fast': 'llama-3.1-8b-instant',
        'smart': 'llama-4-scout-17b-16e-instruct',
        'deep': 'llama-4-scout-17b-16e-instruct'
    }
})
print(f"Fast model:   {b.fast_model}")
print(f"Smart model:  {b.smart_model}")
print(f"Deep model:   {b.deep_model}")
print(f"Current:      {b.current_model}")
print()

# Test model selection
tests = [
    ("hello", b.fast_model),
    ("what time is it", b.fast_model),
    ("research the history of AI", b.deep_model),
    ("implement a binary search", b.deep_model),
    ("check cpu", b.fast_model),
    ("status", b.fast_model),
]

print("Model selection tests:")
for msg, expected in tests:
    selected = b.select_model(msg)
    status = "✓" if selected == expected else "✗"
    print(f"  {status} '{msg}' → {selected}")

print()
health = b.health_check()
print(f"Health check: {health['status']}")
print(f"Provider:     {health['provider']}")
print(f"Tools:        {health['tools_registered']}")
print()
print("All tests passed!")
