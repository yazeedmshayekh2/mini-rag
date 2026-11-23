"""
End-to-end lab for the vector store, using REAL embeddings (bge-m3 via Ollama) and Qdrant.

It mimics what the app will do:
  1. Index chunks of several documents for two projects (tenants), Arabic + English.
  2. Prove re-indexing is idempotent.
  3. Ask real questions, including cross-lingual ones (English question -> Arabic chunks).
  4. Show tenant isolation and why a score threshold matters.
  5. Restrict search to specific documents (metadata filter).
  6. Re-ingest one document (delete by asset, then upsert again).
  7. Build an interactive graph: each chunk linked to its nearest neighbours *within its project*.

Run from the project root:
    python -m scripts.try_vectordb             # keeps the collection so you can browse it in the dashboard
    python -m scripts.try_vectordb --cleanup   # deletes the collection at the end
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ollama import ResponseError as OllamaResponseError

from src.helpers.config import get_settings
from src.stores.llm.LLMEnums import DocumentType
from src.stores.llm.LLMProviderFactory import LLMProviderFactory
from src.stores.vectordb.VectorDBEnums import PayloadFieldType
from src.stores.vectordb.VectorDBExceptions import VectorStoreConnectionError
from src.stores.vectordb.VectorDBSchemas import (
    CollectionSpec,
    MetadataFilter,
    RetrievedChunk,
    SearchQuery,
    VectorRecord,
)
from src.stores.vectordb.providers.QdrantProvider import QdrantProvider

OUTPUT_DIR = Path(__file__).parent / "output"
NEIGHBOURS_PER_POINT = 3  # k for the k-NN graph
SCORE_THRESHOLD = 0.5  # bge-m3-specific: calibrate per embedding model, never copy blindly


# ======================================================================================
# Sample corpus: two tenants, several documents each, Arabic + English
# ======================================================================================
CORPUS = {
    "hr-portal": {
        "leave_policy.pdf": [
            "يحق للموظف الحصول على إجازة سنوية مدفوعة الأجر مدتها ثلاثون يوماً بعد إتمام سنة كاملة من الخدمة.",
            "تُمنح الموظفة إجازة أمومة مدتها عشرة أسابيع بأجر كامل، ويجوز تمديدها لمدة شهر دون أجر.",
            "الإجازة المرضية تتطلب تقديم تقرير طبي معتمد خلال ثلاثة أيام من بداية الغياب.",
        ],
        "remote_work.pdf": [
            "Employees may work remotely up to two days per week with their manager's approval.",
            "Company laptops must be connected through the corporate VPN when working outside the office.",
            "Remote work requests are submitted through the HR portal at least one week in advance.",
        ],
        "salaries.pdf": [
            "يتم صرف الرواتب في اليوم الخامس والعشرين من كل شهر ميلادي.",
            "تُضاف بدلات السكن والنقل إلى الراتب الأساسي وفقاً لسلم الدرجات الوظيفية.",
        ],
    },
    "ml-research": {
        "transformers.pdf": [
            "The transformer architecture relies on self-attention to model relationships between all tokens in a sequence.",
            "During inference, the KV cache stores the keys and values of previous tokens to avoid recomputing them.",
            "PagedAttention in vLLM manages the KV cache in fixed-size blocks, reducing memory fragmentation.",
        ],
        "rag_notes.pdf": [
            "يعتمد نظام الاسترجاع المعزز بالتوليد على البحث عن المقاطع الأكثر صلة ثم تمريرها إلى النموذج اللغوي.",
            "تقسيم المستندات إلى مقاطع صغيرة متداخلة يحسن دقة الاسترجاع.",
            "نماذج التضمين متعددة اللغات تسمح بالبحث بسؤال عربي في مستندات إنجليزية.",
        ],
    },
}

QUESTIONS = [
    # (project, question, what it demonstrates)
    ("hr-portal", "How many days of annual leave do I get?", "cross-lingual: English question, Arabic answer"),
    ("hr-portal", "هل يمكنني العمل من المنزل؟", "cross-lingual: Arabic question, English answer"),
    ("hr-portal", "متى يتم صرف الراتب؟", "same language: Arabic -> Arabic"),
    ("ml-research", "How does vLLM reduce KV cache memory?", "same language: English -> English"),
]


def fake_object_id(*parts: str) -> str:
    """Stable 24-hex id, like a Mongo ObjectId. Stable ids are what make upserts idempotent."""
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:24]


@dataclass
class ChunkRow:
    """What the indexing pipeline will read from MongoDB in the real app."""

    chunk_id: str
    project_id: str
    asset_id: str
    asset_name: str
    chunk_order: int
    text: str


def load_chunks() -> list[ChunkRow]:
    rows = []
    for project_id, assets in CORPUS.items():
        for asset_name, texts in assets.items():
            asset_id = fake_object_id(project_id, asset_name)
            for order, text in enumerate(texts, start=1):
                rows.append(
                    ChunkRow(
                        chunk_id=fake_object_id(project_id, asset_name, str(order)),
                        project_id=project_id,
                        asset_id=asset_id,
                        asset_name=asset_name,
                        chunk_order=order,
                        text=text,
                    )
                )
    return rows


def collection_name(model_id: str, size: int) -> str:
    """One collection per embedding space: vectors from different models must never be mixed."""
    safe_model = re.sub(r"[^a-zA-Z0-9]+", "_", model_id).strip("_")
    return f"lab_chunks_{safe_model}_{size}"


def to_records(rows: list[ChunkRow], vectors: list[list[float]]) -> list[VectorRecord]:
    return [
        VectorRecord(
            id=row.chunk_id,
            project_id=row.project_id,
            vector=vector,
            text=row.text,  # ORIGINAL text, not the normalized one used for embedding
            metadata={
                "asset_id": row.asset_id,
                "asset_name": row.asset_name,
                "chunk_order": row.chunk_order,
            },
        )
        for row, vector in zip(rows, vectors, strict=True)
    ]


def section(title: str) -> None:
    print(f"\n{'=' * 90}\n{title}\n{'=' * 90}")


def print_hits(hits: list[RetrievedChunk]) -> None:
    if not hits:
        print("    (no results)")
    for hit in hits:
        name = hit.metadata.get("asset_name", "?")
        print(f"    {hit.score:.3f}  [{name} #{hit.metadata.get('chunk_order')}]  {hit.text[:80]}")


# ======================================================================================
# Visualization: 2-D projection + k-NN graph computed by Qdrant
# ======================================================================================
def pca_2d(vectors: np.ndarray, extra: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Project 1024-D vectors to 2-D with PCA (via SVD). Returns (points, extra_points, explained_ratio)."""
    mean = vectors.mean(axis=0)
    centered = vectors - mean
    _, singular_values, components = np.linalg.svd(centered, full_matrices=False)
    explained = float((singular_values[:2] ** 2).sum() / (singular_values**2).sum())
    return centered @ components[:2].T, (extra - mean) @ components[:2].T, explained


async def build_knn_edges(store, collection: str, records: list[VectorRecord]) -> list[tuple[str, str, float]]:
    """For every chunk, ask Qdrant for its nearest neighbours IN THE SAME PROJECT.
    This is the tenant-aware version of the graph the Qdrant dashboard draws."""
    edges = []
    for record in records:
        hits = await store.search(
            collection,
            SearchQuery(project_id=record.project_id, vector=record.vector, limit=NEIGHBOURS_PER_POINT + 1),
        )
        for hit in hits:
            if hit.id != record.id:  # the closest hit is always the point itself
                edges.append((record.id, hit.id, hit.score))
    return edges


def write_graph_html(
    records: list[VectorRecord],
    edges: list[tuple[str, str, float]],
    queries: list[dict],
    path: Path,
) -> float:
    points, query_points, explained = pca_2d(
        np.array([r.vector for r in records]),
        np.array([q["vector"] for q in queries]),
    )
    coords = {r.id: points[i].tolist() for i, r in enumerate(records)}
    projects = sorted({r.project_id for r in records})
    palette = ["#2563eb", "#dc2626", "#16a34a", "#9333ea"]
    color = {p: palette[i % len(palette)] for i, p in enumerate(projects)}
    symbols = ["circle", "square", "diamond", "triangle-up", "cross"]

    traces = []

    # k-NN edges, one trace per project (None separates line segments)
    for project in projects:
        xs, ys = [], []
        project_ids = {r.id for r in records if r.project_id == project}
        for src, dst, _ in edges:
            if src in project_ids:
                xs += [coords[src][0], coords[dst][0], None]
                ys += [coords[src][1], coords[dst][1], None]
        traces.append({
            "x": xs, "y": ys, "mode": "lines", "type": "scatter", "hoverinfo": "skip",
            "line": {"color": color[project], "width": 1}, "opacity": 0.35,
            "name": f"{project}: k-NN edges", "legendgroup": project,
        })

    # chunks: one trace per (project, asset) so each document gets its own marker shape
    for project in projects:
        assets = sorted({r.metadata["asset_name"] for r in records if r.project_id == project})
        for i, asset in enumerate(assets):
            group = [r for r in records if r.project_id == project and r.metadata["asset_name"] == asset]
            traces.append({
                "x": [coords[r.id][0] for r in group],
                "y": [coords[r.id][1] for r in group],
                "mode": "markers", "type": "scatter",
                "marker": {"size": 13, "color": color[project], "symbol": symbols[i % len(symbols)],
                           "line": {"color": "white", "width": 1}},
                "name": f"{project} / {asset}", "legendgroup": project,
                "text": [f"<b>{asset} #{r.metadata['chunk_order']}</b><br>{r.text}" for r in group],
                "hovertemplate": "%{text}<extra></extra>",
            })

    # queries: star marker + dashed lines to the chunks Qdrant returned
    for i, query in enumerate(queries):
        qx, qy = query_points[i].tolist()
        xs, ys = [], []
        for hit in query["hits"]:
            xs += [qx, coords[hit.id][0], None]
            ys += [qy, coords[hit.id][1], None]
        traces.append({
            "x": xs, "y": ys, "mode": "lines", "type": "scatter", "hoverinfo": "skip",
            "line": {"color": "#f59e0b", "width": 2, "dash": "dot"}, "showlegend": False,
        })
        traces.append({
            "x": [qx], "y": [qy], "mode": "markers", "type": "scatter",
            "marker": {"size": 18, "color": "#f59e0b", "symbol": "star", "line": {"color": "black", "width": 1}},
            "name": f"Q{i + 1} ({query['project']})",
            "text": [f"<b>Q{i + 1}</b> [{query['project']}]<br>{query['question']}"],
            "hovertemplate": "%{text}<extra></extra>",
        })

    layout = {
        "title": {"text": (
            f"Chunks of each project linked to their {NEIGHBOURS_PER_POINT} nearest neighbours (computed by Qdrant in 1024-D)"
            f"<br><sub>2-D PCA projection keeps {explained:.0%} of the variance: positions are approximate, "
            f"edges and query links are exact</sub>")},
        "hovermode": "closest", "height": 800,
        "xaxis": {"title": "PC 1", "zeroline": False}, "yaxis": {"title": "PC 2", "zeroline": False},
        "legend": {"groupclick": "toggleitem"},
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Vector store lab</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{font-family:system-ui,sans-serif;margin:16px}}</style></head>
<body><div id="graph"></div>
<script>
Plotly.newPlot("graph", {json.dumps(traces, ensure_ascii=False)}, {json.dumps(layout, ensure_ascii=False)}, {{responsive: true}});
</script></body></html>""",
        encoding="utf-8",
    )
    return explained


# ======================================================================================
# The lab
# ======================================================================================
async def main(cleanup: bool) -> None:
    settings = get_settings()
    embedder = LLMProviderFactory(settings).create_embedding_client()
    collection = collection_name(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
    api_key = settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None

    async with QdrantProvider(url=settings.QDRANT_URL, api_key=api_key) as store:

        section(f"1. Ensure collection '{collection}' (idempotent: safe to run on every startup)")
        await store.ensure_collection(
            CollectionSpec(
                name=collection,
                vector_size=settings.EMBEDDING_MODEL_SIZE,
                indexed_fields={
                    "asset_id": PayloadFieldType.KEYWORD,
                    "chunk_order": PayloadFieldType.INTEGER,
                },
            )
        )
        print("    ok")

        section("2. Index: embed chunks as DOCUMENT, then upsert")
        rows = load_chunks()
        vectors = await embedder.embed_text([r.text for r in rows], DocumentType.DOCUMENT)
        records = to_records(rows, vectors)
        await store.upsert(collection, records)
        for project in CORPUS:
            print(f"    {project}: {await store.count(collection, project)} chunks")

        section("3. Idempotency: upsert the same chunks again -> counts must NOT change")
        await store.upsert(collection, records)
        for project in CORPUS:
            print(f"    {project}: {await store.count(collection, project)} chunks")

        section("4. Questions: embed as QUERY, search inside the project only")
        query_vectors = await embedder.embed_text([q for _, q, _ in QUESTIONS], DocumentType.QUERY)
        queries = []
        for (project, question, note), vector in zip(QUESTIONS, query_vectors, strict=True):
            hits = await store.search(collection, SearchQuery(project_id=project, vector=vector, limit=3))
            print(f"\n  [{project}] {question}\n  ({note})")
            print_hits(hits)
            queries.append({"project": project, "question": question, "vector": vector, "hits": hits})

        section("5. Tenant isolation + why a score threshold matters")
        ml_question, ml_vector = QUESTIONS[3][1], query_vectors[3]
        print(f"  Asking the ML question in the WRONG project (hr-portal): {ml_question}")
        print("  Without threshold: the store always returns the k 'least bad' chunks, all irrelevant:")
        print_hits(await store.search(collection, SearchQuery(project_id="hr-portal", vector=ml_vector, limit=3)))
        print(f"  With score_threshold={SCORE_THRESHOLD}: irrelevant chunks are dropped, nothing reaches the LLM:")
        print_hits(await store.search(collection, SearchQuery(
            project_id="hr-portal", vector=ml_vector, limit=3, score_threshold=SCORE_THRESHOLD)))

        section("6. Metadata filter: search only inside selected documents")
        remote_id = fake_object_id("hr-portal", "remote_work.pdf")
        salary_id = fake_object_id("hr-portal", "salaries.pdf")
        print("  'annual leave' question, restricted to remote_work.pdf + salaries.pdf (leave_policy.pdf excluded):")
        print_hits(await store.search(collection, SearchQuery(
            project_id="hr-portal", vector=query_vectors[0], limit=3,
            filter=MetadataFilter(any_of={"asset_id": [remote_id, salary_id]}))))

        section("7. Re-ingest one document: delete its chunks by asset_id, then upsert the new version")
        before = await store.count(collection, "hr-portal")
        await store.delete(collection, "hr-portal", MetadataFilter(equals={"asset_id": salary_id}))
        after_delete = await store.count(collection, "hr-portal")
        await store.upsert(collection, [r for r in records if r.metadata["asset_id"] == salary_id])
        after_reindex = await store.count(collection, "hr-portal")
        print(f"    hr-portal chunks: before={before}  after delete={after_delete}  after re-index={after_reindex}")
        print(f"    ml-research untouched: {await store.count(collection, 'ml-research')}")

        section("8. Visualize: k-NN graph per project (edges come from Qdrant searches, tenant-filtered)")
        edges = await build_knn_edges(store, collection, records)
        project_of = {r.id: r.project_id for r in records}
        cross_tenant = sum(1 for src, dst, _ in edges if project_of[src] != project_of[dst])
        html_path = OUTPUT_DIR / "vectordb_graph.html"
        explained = write_graph_html(records, edges, queries, html_path)
        print(f"    {len(edges)} edges, cross-tenant edges: {cross_tenant} (must be 0)")
        print(f"    PCA keeps {explained:.0%} of the variance in 2-D")
        print(f"    graph: {html_path}")
        webbrowser.open(html_path.resolve().as_uri())

        if cleanup:
            await store.delete_collection(collection)
            print(f"\n  Deleted collection '{collection}'")
        else:
            print(f"\n  Collection kept: browse it at {settings.QDRANT_URL}/dashboard  (use --cleanup to delete)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vector store lab with real embeddings")
    parser.add_argument("--cleanup", action="store_true", help="delete the lab collection at the end")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.cleanup))
    except VectorStoreConnectionError as e:
        sys.exit(f"\nQdrant problem: {e}\n-> is the container running? (cd docker; docker compose up -d qdrant)")
    except ConnectionError as e:
        sys.exit(f"\nCannot reach Ollama: {e}\n-> is Ollama running? (ollama serve)")
    except OllamaResponseError as e:
        sys.exit(f"\nOllama error: {e.error}\n-> is the embedding model pulled? (ollama pull bge-m3)")
