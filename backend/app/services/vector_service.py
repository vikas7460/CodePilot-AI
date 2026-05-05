import os
import uuid
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer

load_dotenv()

QDRANT_PATH = os.getenv("QDRANT_PATH", "./qdrant_db")

qdrant_client = QdrantClient(path=QDRANT_PATH)

COLLECTION_NAME = "code_chunks"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_SIZE = 384

model = SentenceTransformer(EMBEDDING_MODEL)


def create_embedding(text: str):
    vector = model.encode(text)
    return vector.tolist()


def ensure_collection():
    collections = qdrant_client.get_collections().collections
    collection_names = [c.name for c in collections]

    if COLLECTION_NAME not in collection_names:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_SIZE,
                distance=Distance.COSINE,
            ),
        )


def index_chunks(repo_id: str, chunks: list):
    ensure_collection()

    points = []

    for item in chunks:
        text = item["chunk"]
        vector = create_embedding(text)

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "repo_id": repo_id,
                    "path": item["path"],
                    "content": text,
                },
            )
        )

    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )

    return {
        "repo_id": repo_id,
        "indexed_chunks": len(points),
    }


def search_chunks(repo_id: str, query: str, limit: int = 10):
    query_vector = create_embedding(query)

    results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="repo_id",
                    match=MatchValue(value=repo_id),
                )
            ]
        ),
    )

    clean_results = []

    for result in results.points:
        path = result.payload["path"]
        lower_path = path.lower()

        # Remove noisy documentation/history files
        if lower_path.endswith("history.md"):
            continue

        if lower_path.startswith("docs"):
            continue

        clean_results.append(
            {
                "path": path,
                "content": result.payload["content"],
                "score": result.score,
            }
        )

    return clean_results[:5]