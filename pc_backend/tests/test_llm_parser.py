"""Quick test for the LLM JSON parser"""
import sys
sys.path.insert(0, '..')
from ai_engine.llm_client import LLMClient

# Standard JSON
r1 = LLMClient._parse_json('{"thought": "hello", "emotion_delta": 0.05, "expression": "happy"}')
print('Standard JSON: thought=%s, delta=%.2f' % (r1['thought'], r1['emotion_delta']))
assert r1['expression'] == 'happy'

# Single quotes (DeepSeek common output)
r2 = LLMClient._parse_json("{'thought': 'hi there', 'emotion_delta': 0.03, 'expression': 'sad'}")
print("Single quotes: thought=%s, delta=%.2f" % (r2['thought'], r2['emotion_delta']))
assert r2['expression'] == 'sad'

# Markdown code block
r3 = LLMClient._parse_json('```json\n{"thought": "nice", "emotion_delta": -0.02, "expression": "focus"}\n```')
print('Markdown block: thought=%s, delta=%.2f' % (r3['thought'], r3['emotion_delta']))
assert r3['expression'] == 'focus'

# Invalid expression fallback
r4 = LLMClient._parse_json('{"thought": "ok", "emotion_delta": 0.5, "expression": "excited"}')
print('Bad expression: expr=%s (clamped delta=%.2f)' % (r4['expression'], r4['emotion_delta']))
assert r4['expression'] == 'normal'
assert r4['emotion_delta'] == 0.1  # clamped

# Corner case: text before/after JSON
r5 = LLMClient._parse_json('Some text {"thought": "wow", "emotion_delta": 0.0, "expression": "surprise"} more text')
print('Mixed text: thought=%s' % r5['thought'])
assert r5['expression'] == 'surprise'

print()
print('ALL PARSER TESTS PASSED!')
