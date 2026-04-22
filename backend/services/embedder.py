import requests
import os

# Get API key from environment
HF_API_KEY = os.getenv("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")

MODEL_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}


def get_embedding(text: str):
    if not HF_API_KEY:
        raise Exception("HF_API_KEY not set in environment")

    response = requests.post(
        MODEL_URL,
        headers=HEADERS,
        json={"inputs": text}
    )

    if response.status_code != 200:
        raise Exception(f"HuggingFace API error: {response.text}")

    data = response.json()

    # HF returns nested list → flatten it
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
        return data[0]

    return data


# Example usage
if __name__ == "__main__":
    text = "This is a test sentence"
    embedding = get_embedding(text)
    print(f"Embedding length: {len(embedding)}")