#!/usr/bin/env python3
"""
Medical RAG System Setup Script
Builds FAISS index from medical PDF documents
"""

import os
import sys
import argparse
import pickle
from pathlib import Path

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

try:
    from lib.rag_service import MedicalRAGSystem
except ImportError:
    # If the class doesn't exist in rag_service.py, let's define it here
    print("❌ MedicalRAGSystem not found in rag_service.py. Creating standalone setup...")
    
    # Install required packages
    os.system("pip install faiss-cpu sentence-transformers pypdf2 python-dotenv")
    
    # Now define the class directly in this file
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from PyPDF2 import PdfReader
    
    class MedicalRAGSystem:
        def __init__(self, index_dir="faiss_index", embed_model_name="all-MiniLM-L6-v2"):
            self.index_dir = Path(index_dir)
            self.embed_model_name = embed_model_name
            self.embedder = None
            self.index = None
            self.documents = []
            
            # Create index directory if it doesn't exist
            self.index_dir.mkdir(exist_ok=True)
            
        def load_embedder(self):
            """Load the sentence transformer model"""
            if self.embedder is None:
                print("   🔤 Loading embedding model...")
                self.embedder = SentenceTransformer(self.embed_model_name)
            return self.embedder
        
        def extract_text_from_pdf(self, pdf_path):
            """Extract text from PDF file"""
            print("1️⃣ Extracting text from PDF...")
            try:
                reader = PdfReader(pdf_path)
                text = ""
                total_pages = len(reader.pages)
                
                for i, page in enumerate(reader.pages):
                    text += page.extract_text() + "\n"
                    if (i + 1) % 50 == 0:  # Progress update every 50 pages
                        print(f"   📄 Processed {i + 1}/{total_pages} pages...")
                
                print(f"   ✅ Extracted {len(text):,} characters from {total_pages} pages")
                return text
            except Exception as e:
                print(f"   ❌ Error extracting PDF: {str(e)}")
                raise
        
        def chunk_text(self, text, chunk_size=500, chunk_overlap=50):
            """Split text into overlapping chunks"""
            print("2️⃣ Splitting text into chunks...")
            
            chunks = []
            start = 0
            
            while start < len(text):
                end = start + chunk_size
                chunk = text[start:end]
                
                # Try to break at sentence end for cleaner chunks
                if end < len(text):
                    sentence_breaks = ['.', '!', '?', '\n\n']
                    for break_char in sentence_breaks:
                        break_pos = chunk.rfind(break_char)
                        if break_pos > chunk_size * 0.7:  # Only break if reasonable
                            chunk = chunk[:break_pos + 1]
                            end = start + len(chunk)
                            break
                
                if chunk.strip():  # Only add non-empty chunks
                    chunks.append(chunk.strip())
                start = end - chunk_overlap  # Overlap chunks
            
            print(f"   ✅ Created {len(chunks):,} chunks")
            return chunks
        
        def build_embeddings(self, chunks):
            """Create embeddings for text chunks"""
            print("3️⃣ Creating embeddings...")
            embedder = self.load_embedder()
            embeddings = embedder.encode(chunks, show_progress_bar=True)
            print(f"   ✅ Generated embeddings: {embeddings.shape}")
            return embeddings
        
        def build_faiss_index(self, embeddings):
            """Build FAISS index from embeddings"""
            print("4️⃣ Building FAISS index...")
            
            # Create FAISS index
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
            
            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)
            self.index.add(embeddings)
            
            print(f"   ✅ FAISS index built with {self.index.ntotal} vectors")
        
        def save_index(self):
            """Save FAISS index and documents"""
            print("5️⃣ Saving index to disk...")
            
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_dir / "book.index"))
            
            # Save documents
            with open(self.index_dir / "docs.pkl", 'wb') as f:
                pickle.dump(self.documents, f)
            
            print("   ✅ Index saved successfully!")
        
        def load_index(self):
            """Load existing FAISS index and documents"""
            index_path = self.index_dir / "book.index"
            docs_path = self.index_dir / "docs.pkl"
            
            if not index_path.exists() or not docs_path.exists():
                return False
            
            try:
                self.index = faiss.read_index(str(index_path))
                with open(docs_path, 'rb') as f:
                    self.documents = pickle.load(f)
                self.load_embedder()
                return True
            except Exception as e:
                print(f"   ❌ Error loading index: {str(e)}")
                return False
        
        def build_index_from_pdf(self, pdf_path, force_rebuild=False):
            """Main method to build index from PDF"""
            
            # Check if index already exists
            if not force_rebuild and self.load_index():
                print("   📁 Using existing index")
                return
            
            # Build new index
            text = self.extract_text_from_pdf(pdf_path)
            self.documents = self.chunk_text(text)
            embeddings = self.build_embeddings(self.documents)
            self.build_faiss_index(embeddings)
            self.save_index()
        
        def get_document_count(self):
            """Get number of documents in index"""
            if self.index is not None:
                return self.index.ntotal
            return 0

def main():
    parser = argparse.ArgumentParser(description='Build FAISS index for Medical RAG System')
    parser.add_argument('pdf_path', help='Path to the medical PDF file')
    parser.add_argument('--index-dir', default='faiss_index', help='Directory to save FAISS index')
    parser.add_argument('--force-rebuild', action='store_true', help='Force rebuild existing index')
    
    args = parser.parse_args()
    
    # Check if PDF file exists
    if not os.path.exists(args.pdf_path):
        print(f"❌ Error: PDF file '{args.pdf_path}' not found")
        sys.exit(1)
    
    print("🏥 Medical RAG System Setup")
    print("=" * 50)
    print(f"🏗️ Building FAISS index from: {args.pdf_path}")
    print(f"📁 Index will be saved to: {args.index_dir}")
    print()
    
    try:
        # Initialize RAG system
        rag_system = MedicalRAGSystem(index_dir=args.index_dir)
        
        # Build index from PDF
        rag_system.build_index_from_pdf(
            pdf_path=args.pdf_path,
            force_rebuild=args.force_rebuild
        )
        
        print("✅ FAISS index built successfully!")
        print(f"📊 Index contains {rag_system.get_document_count()} documents")
        
    except Exception as e:
        print(f"❌ Error building index: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()