"""Module 5A playground. Run one lesson at a time:
   uv run python -m shoppilot.playground.llm_basics basic|stream|tokens|temperature|system|json|embed
"""
import math
import sys
import time
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from shoppilot.config import get_settings
from shoppilot.llm import client
from shoppilot.llm import client, embed as embed_texts


S = get_settings()


def basic():
    r = client().models.generate_content(
        model=S.llm_model,
        contents="In one sentence: why do e-commerce companies have return policies?",
    )
    print(r.text)
    u = r.usage_metadata
    print(f"\n📊 tokens  input={u.prompt_token_count}  output={u.candidates_token_count}  "
          f"thinking={u.thoughts_token_count}  total={u.total_token_count}")


def stream():
    start, first = time.perf_counter(), None
    for chunk in client().models.generate_content_stream(
        model=S.llm_model,
        contents="Write a 150-word apology email to a customer whose order is 5 days late.",
    ):
        if first is None:
            first = time.perf_counter() - start
            print(f"⚡ first token after {first:.2f}s\n")
        print(chunk.text or "", end="", flush=True)
    print(f"\n\n⏱️ total {time.perf_counter() - start:.2f}s")


def tokens():
    samples = {
        "english": "Where is my order? It has not arrived yet.",
        "hindi": "मेरा ऑर्डर कहाँ है? यह अभी तक नहीं आया है।",
        "telugu": "నా ఆర్డర్ ఎక్కడ ఉంది? ఇది ఇంకా రాలేదు.",
        "hinglish": "Mera order kahan hai? Abhi tak nahi aaya.",
    }
    for lang, text in samples.items():
        n = client().models.count_tokens(model=S.llm_model, contents=text).total_tokens
        print(f"{lang:10} {n:3} tokens   {text}")


def temperature():
    prompt = "Suggest ONE creative name for an AI shopping assistant. Reply with the name only."
    for temp in (0.0, 1.5):
        names = [
            client().models.generate_content(
                model=S.llm_model, contents=prompt,
                config=types.GenerateContentConfig(temperature=temp),
            ).text.strip()
            for _ in range(3)
        ]
        print(f"temperature={temp}: {names}")


def system():
    rules = ("You are ShopPilot's support assistant. Answer in at most 2 sentences. "
             "Never promise a refund; say a human agent will review the request.")
    for sys_instr in (None, rules):
        r = client().models.generate_content(
            model=S.llm_model,
            contents="I want my money back RIGHT NOW, the product is garbage!",
            config=types.GenerateContentConfig(system_instruction=sys_instr),
        )
        print(f"--- system instruction: {'YES' if sys_instr else 'NO'} ---\n{r.text}\n")


class Order(BaseModel):
    order_id: str | None = Field(description="Order number if mentioned")
    items: list[str]
    issue: Literal["damaged", "late", "wrong_item", "other"]
    wants_refund: bool


def json_output():
    r = client().models.generate_content(
        model=S.llm_model,
        contents="Hi, order 48213 came today. The blue kettle is cracked and the toaster is missing. "
                 "I'd like my money back please.",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Order,  # the model MUST answer in this shape
            temperature=0,
        ),
    )
    print("raw text :", r.text)
    order: Order = r.parsed  # already a validated Pydantic object
    print("parsed   :", order)
    print("use it   : refund?", order.wants_refund, "| items:", order.items)


def embed():
    texts = [
        "How do I return a damaged item?",
        "Can I send back a broken product?",
        "Refunds are issued within 5-7 business days.",
        "Express shipping costs 199 rupees.",
    ]
    r = client().models.embed_content(
        model=S.embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=768, task_type="SEMANTIC_SIMILARITY"),
    )
    vecs = embed_texts(texts)
    print(f"each text -> vector of {len(vecs[0])} numbers, e.g. {[round(x, 3) for x in vecs[0][:5]]} ...\n")

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))

    print("similarity to:", texts[0])
    for t, v in zip(texts[1:], vecs[1:]):
        print(f"  {cosine(vecs[0], v):.3f}  {t}")


LESSONS = {"basic": basic, "stream": stream, "tokens": tokens, "temperature": temperature,
           "system": system, "json": json_output, "embed": embed}

if __name__ == "__main__":
    LESSONS[sys.argv[1] if len(sys.argv) > 1 else "basic"]()
