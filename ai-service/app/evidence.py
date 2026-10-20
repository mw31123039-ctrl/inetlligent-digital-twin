import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup

@dataclass(frozen=True)
class Document:
    id: str
    title: str
    url: str
    text: str
    retrieved_at: str

# A curated retrieval corpus, not a diagnostic knowledge base. URLs never come
# from user/model input. New entries require source and clinical review.
CATALOG = {
    'eyes': [('dry-eyes', 'Dry eyes', 'https://www.nhs.uk/conditions/dry-eyes/'), ('conjunctivitis', 'Conjunctivitis', 'https://www.nhs.uk/conditions/conjunctivitis/')],
    'head': [('tension-headache', 'Tension headaches', 'https://www.nhs.uk/conditions/tension-headaches/'), ('migraine', 'Migraine', 'https://www.nhs.uk/conditions/migraine/')],
    'chest': [('costochondritis', 'Costochondritis', 'https://www.nhs.uk/conditions/costochondritis/'), ('acid-reflux', 'Heartburn and acid reflux', 'https://www.nhs.uk/conditions/heartburn-and-acid-reflux/')],
    'abdomen': [('indigestion', 'Indigestion', 'https://www.nhs.uk/conditions/indigestion/'), ('constipation', 'Constipation', 'https://www.nhs.uk/conditions/constipation/')],
    'arms': [('strain', 'Sprains and strains', 'https://www.nhs.uk/conditions/sprains-and-strains/'), ('carpal-tunnel', 'Carpal tunnel syndrome', 'https://www.nhs.uk/conditions/carpal-tunnel-syndrome/')],
    'legs': [('strain', 'Sprains and strains', 'https://www.nhs.uk/conditions/sprains-and-strains/'), ('leg-cramps', 'Leg cramps', 'https://www.nhs.uk/conditions/leg-cramps/')],
}

def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()

class EvidenceRetriever:
    def __init__(self, timeout=4):
        self.timeout = timeout
        self.cache = {} # Public medical text only. No user terms/history are cached.

    async def _fetch(self, client, item):
        id, title, url = item
        cached = self.cache.get(url)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            # Redirects are resolved manually and remain on the exact allowlisted host.
            current = url
            for _ in range(3):
                async with client.stream('GET', current) as response:
                    if response.is_redirect:
                        next_url = str(response.url.join(response.headers['location']))
                        parsed = httpx.URL(next_url)
                        if parsed.scheme != 'https' or parsed.host != 'www.nhs.uk':
                            return None
                        current = next_url
                        continue
                    response.raise_for_status()
                    if 'text/html' not in response.headers.get('content-type', ''):
                        return None
                    chunks, length = [], 0
                    async for chunk in response.aiter_bytes():
                        length += len(chunk)
                        if length > 1_000_000:
                            return None
                        chunks.append(chunk)
                    html = b''.join(chunks)
                soup = BeautifulSoup(html, 'html.parser')
                main = soup.find('main')
                if not main:
                    return None
                for node in main.select('script,style,nav,form,footer'):
                    node.decompose()
                text = normalized(main.get_text(' ', strip=True))[:18000]
                if len(text) < 150:
                    return None
                document = Document(id, title, current, text, datetime.now(timezone.utc).isoformat())
                self.cache[url] = (time.monotonic() + 3600, document)
                return document
        except (httpx.HTTPError, ValueError, KeyError):
            return None
        return None

    async def retrieve(self, region):
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, headers={'User-Agent': 'HumanTwin-ReferenceRetriever/0.1'}) as client:
            results = await asyncio.gather(*(self._fetch(client, item) for item in CATALOG[region]))
        return [result for result in results if result]
