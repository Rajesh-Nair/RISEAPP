import { ChunkItem } from "./ChunkItem";
import type { ChunkItemApi } from "./types";

interface ChunkListProps {
  chunks: ChunkItemApi[];
  onChunkClick: (chunkId: string) => void;
  setChunkRef: (chunkId: string, el: HTMLElement | null) => void;
  getHighlight: (chunkId: string) => string | undefined;
}

export function ChunkList({ chunks, onChunkClick, setChunkRef, getHighlight }: ChunkListProps) {
  const sorted = [...chunks].sort((a, b) => a.chunk_index - b.chunk_index);
  return (
    <div className="chunk-list">
      {sorted.map((chunk) => (
        <ChunkItem
          key={chunk.chunk_id}
          chunk={chunk}
          onClick={onChunkClick}
          setChunkRef={setChunkRef}
          highlight={getHighlight(chunk.chunk_id)}
        />
      ))}
    </div>
  );
}
