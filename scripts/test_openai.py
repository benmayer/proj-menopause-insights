"""Test the OpenAI key alone: one embedding call + one tiny chat call."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import _env  # noqa: F401
from openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY
emb = client.embeddings.create(model="text-embedding-3-small", input="cycle length variability")
print("embedding OK, dims =", len(emb.data[0].embedding))

chat = client.chat.completions.create(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    max_tokens=5,
)
print("chat OK:", chat.choices[0].message.content.strip())
