#!/usr/bin/env python3

import os
import argparse
import pickle
from pathlib import Path

import faiss
import numpy as np
import requests
from PyPDF2 import PdfReader

HF_API_KEY = os.getenv("HF_API_KEY")

HF_MODEL_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}


class MedicalRAGSystem:

    def __init__(self, index_dir="faiss_index"):
        self.index_dir = Path(index_dir)
        self.index = None
        self.documents = []
        self.index_dir.mkdir(exist_ok=True)

    def get_embedding(self, text):
        if not HF_API_KEY:
            raise Exception("HF_API_KEY not set")

        response = requests.post(
            HF_MODEL_URL,
            headers=HEADERS,
            json={"inputs": text}
        )

        if response.status_code != 200:
            raise Exception(response.text)

        data = response.json()

        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            return data[0]

        return data

    def extract_text_from_pdf(self, pdf_path):
        reader = PdfReader(pdf_path)
        text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        return text

    def chunk_text(self, text, chunk_size=500, overlap=50):
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk.strip())
            start = end - overlap

        return chunks

    def build_embeddings(self, chunks):
        embeddings = []

        for chunk in chunks:
            emb = self.get_embedding(chunk)
            embeddings.append(emb)

        return np.array(embeddings).astype("float32")

    def build_index(self, embeddings):
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)

        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)

    def save(self):
        faiss.write_index(self.index, str(self.index_dir / "index.faiss"))

        with open(self.index_dir / "docs.pkl", "wb") as f:
            pickle.dump(self.documents, f)

    def run(self, pdf_path):
        text = self.extract_text_from_pdf(pdf_path)
        self.documents = self.chunk_text(text)

        embeddings = self.build_embeddings(self.documents)
        self.build_index(embeddings)
        self.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")

    args = parser.parse_args()

    rag = MedicalRAGSystem()
    rag.run(args.pdf_path)


if __name__ == "__main__":
    main()