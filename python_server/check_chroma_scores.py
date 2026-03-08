from core.state import raw_engine
from vector_store import SmartSearchEngine
import chromadb
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

if __name__ == "__main__":
    engine = SmartSearchEngine("../db.sqlite3", base_dir="..")
    # Instead of full initialize which uses a thread, we can just do text queries
    # since ChromaDB is already initialized from earlier runs in ml_store/chroma
    
    # We'll just directly instantiate model and query the collection
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path="../ml_store/chroma")
    
    try:
        col = client.get_collection("product")
        
        print("\n--- Testing Exact Match (Lays Classic) ---")
        q_emb = model.encode(["Lays Classic"]).tolist()
        res = col.query(query_embeddings=q_emb, n_results=3, include=["metadatas", "distances"])
        
        for m, d in zip(res["metadatas"][0], res["distances"][0]):
            sim = round((1 - d) * 100, 1)
            print(f"Match: {m['product_name']} {m['variant_name']} - Distance: {d:.4f} - Similarity: {sim}%")
            
        print("\n--- Testing Partial Match (Laays Masala) ---")
        q_emb = model.encode(["Laays Masala"]).tolist()
        res = col.query(query_embeddings=q_emb, n_results=3, include=["metadatas", "distances"])
        
        for m, d in zip(res["metadatas"][0], res["distances"][0]):
            sim = round((1 - d) * 100, 1)
            print(f"Match: {m['product_name']} {m['variant_name']} - Distance: {d:.4f} - Similarity: {sim}%")
            
        print("\n--- Testing Concept (Potato Chips) ---")
        q_emb = model.encode(["Potato Chips"]).tolist()
        res = col.query(query_embeddings=q_emb, n_results=3, include=["metadatas", "distances"])
        
        for m, d in zip(res["metadatas"][0], res["distances"][0]):
            sim = round((1 - d) * 100, 1)
            print(f"Match: {m['product_name']} {m['variant_name']} - Distance: {d:.4f} - Similarity: {sim}%")
            
    except Exception as e:
        print(f"Error querying chroma: {e}")
