import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DocumentPane } from "./DocumentPane";
import type {
  ChunkItemApi,
  ContentAnnotatedResponse,
  DocumentInfo,
  RelationshipState,
  RelatedChunksResponse,
} from "./types";

const API = "/api";
const PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];

function getDocIdsFromHash(): { left: number | null; right: number | null } {
  const hash = window.location.hash.slice(1) || "";
  const parts = hash.split("/").filter(Boolean);
  if (parts.length >= 2) {
    const left = parseInt(parts[0], 10);
    const right = parseInt(parts[1], 10);
    if (!isNaN(left) && !isNaN(right)) return { left, right };
  }
  return { left: null, right: null };
}

export function ComparePage() {
  const [docIds, setDocIds] = useState<{ left: number | null; right: number | null }>(
    getDocIdsFromHash
  );
  const [leftDoc, setLeftDoc] = useState<DocumentInfo | null>(null);
  const [rightDoc, setRightDoc] = useState<DocumentInfo | null>(null);
  const [leftChunks, setLeftChunks] = useState<ChunkItemApi[]>([]);
  const [rightChunks, setRightChunks] = useState<ChunkItemApi[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [relationships, setRelationships] = useState<RelationshipState[]>([]);
  const [activeSourceChunkId, setActiveSourceChunkId] = useState<string | null>(null);
  const [activeTargetChunkId, setActiveTargetChunkId] = useState<string | null>(null);

  const chunkRefsMap = useRef<Map<string, HTMLElement>>(new Map());

  useEffect(() => {
    const onHash = () => setDocIds(getDocIdsFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const leftId = docIds.left;
  const rightId = docIds.right;

  useEffect(() => {
    let cancelled = false;
    if (leftId == null || rightId == null) {
      setLoading(false);
      setError("Select two documents. Use URL hash: #/leftId/rightId (e.g. #/1/2)");
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`${API}/documents/${leftId}/content-annotated?format=md`).then((r) => r.json()),
      fetch(`${API}/documents/${rightId}/content-annotated?format=md`).then((r) => r.json()),
    ])
      .then(([data1, data2]: [ContentAnnotatedResponse, ContentAnnotatedResponse]) => {
        if (cancelled) return;
        if (data1.document && data2.document) {
          setLeftDoc(data1.document);
          setRightDoc(data2.document);
          setLeftChunks(data1.chunks ?? []);
          setRightChunks(data2.chunks ?? []);
        } else {
          setError("Document not found");
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Failed to load documents");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [leftId, rightId]);

  const setChunkRef = useCallback((chunkId: string, el: HTMLElement | null) => {
    const map = chunkRefsMap.current;
    if (el) map.set(chunkId, el);
    else map.delete(chunkId);
  }, []);

  const highlightMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const r of relationships) {
      map.set(r.sourceChunkId, r.assignedColor);
      for (const tid of r.targetChunkIds) {
        map.set(tid, r.assignedColor);
      }
    }
    return map;
  }, [relationships]);

  const getHighlight = useCallback(
    (chunkId: string) => highlightMap.get(chunkId),
    [highlightMap]
  );

  const onChunkClick = useCallback(
    async (documentId: number, chunkId: string) => {
      const existing = relationships.find(
        (r) => r.sourceChunkId === chunkId && r.sourceDocumentId === documentId
      );
      if (existing) {
        const nextIndex =
          existing.targetChunkIds.length > 0
            ? (existing.currentIndex + 1) % existing.targetChunkIds.length
            : 0;
        const nextTargetId = existing.targetChunkIds[nextIndex] ?? null;
        setRelationships((prev) =>
          prev.map((r) =>
            r === existing ? { ...r, currentIndex: nextIndex } : r
          )
        );
        setActiveTargetChunkId(nextTargetId);
      } else {
        try {
          const res = await fetch(`${API}/chunk/related`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source_document: String(documentId),
              chunk_id: chunkId,
            }),
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            setError(err.detail || err.message || "Failed to load related chunks");
            return;
          }
          const data: RelatedChunksResponse = await res.json();
          const color = PALETTE[relationships.length % PALETTE.length];
          const newRel: RelationshipState = {
            relationshipGroupId: data.relationship_group_id,
            sourceChunkId: chunkId,
            sourceDocumentId: documentId,
            targetDocumentId: data.target_document,
            targetChunkIds: data.related_chunks ?? [],
            currentIndex: 0,
            assignedColor: color,
          };
          setRelationships((prev) => [...prev, newRel]);
          const firstTarget = newRel.targetChunkIds[0] ?? null;
          setActiveTargetChunkId(firstTarget);
        } catch (e) {
          setError((e as Error).message || "Failed to load related chunks");
          return;
        }
      }
      setActiveSourceChunkId(chunkId);
    },
    [relationships]
  );

  useEffect(() => {
    if (!activeSourceChunkId || !activeTargetChunkId || !chunkRefsMap.current) return;
    const srcEl = chunkRefsMap.current.get(activeSourceChunkId);
    const tgtEl = chunkRefsMap.current.get(activeTargetChunkId);
    srcEl?.scrollIntoView({ behavior: "smooth", block: "center" });
    tgtEl?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeSourceChunkId, activeTargetChunkId]);

  const handleLeftChunkClick = useCallback(
    (chunkId: string) => {
      if (leftDoc) onChunkClick(leftDoc.id, chunkId);
    },
    [leftDoc, onChunkClick]
  );
  const handleRightChunkClick = useCallback(
    (chunkId: string) => {
      if (rightDoc) onChunkClick(rightDoc.id, chunkId);
    },
    [rightDoc, onChunkClick]
  );

  if (loading) {
    return (
      <div className="compare-page">
        <p className="compare-loading">Loading documents…</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="compare-page">
        <p className="compare-error">{error}</p>
        <p className="compare-hint">
          Use URL hash to pick documents: <code>#/1/2</code> for document 1 vs 2. Open{" "}
          <a href="/">main app</a> to list documents.
        </p>
      </div>
    );
  }
  if (!leftDoc || !rightDoc) {
    return (
      <div className="compare-page">
        <p className="compare-error">Documents not found.</p>
      </div>
    );
  }

  return (
    <div className="compare-page">
      <header className="compare-header">
        <a href="/" className="compare-back">
          ← RiseApp
        </a>
        <h1 className="compare-title">
          {leftDoc.name} ↔ {rightDoc.name}
        </h1>
      </header>
      <div className="compare-layout">
        <DocumentPane
          documentName={leftDoc.name}
          documentId={leftDoc.id}
          chunks={leftChunks}
          onChunkClick={handleLeftChunkClick}
          setChunkRef={setChunkRef}
          getHighlight={getHighlight}
        />
        <DocumentPane
          documentName={rightDoc.name}
          documentId={rightDoc.id}
          chunks={rightChunks}
          onChunkClick={handleRightChunkClick}
          setChunkRef={setChunkRef}
          getHighlight={getHighlight}
        />
      </div>
    </div>
  );
}
