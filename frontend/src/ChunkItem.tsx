import { useCallback, memo } from "react";
import type { ChunkItemApi } from "./types";

interface ChunkItemProps {
  chunk: ChunkItemApi;
  onClick: (chunkId: string) => void;
  setChunkRef: (chunkId: string, el: HTMLElement | null) => void;
  highlight: string | undefined;
}

function ChunkItemInner({ chunk, onClick, setChunkRef, highlight }: ChunkItemProps) {
  const refCb = useCallback(
    (el: HTMLDivElement | null) => {
      setChunkRef(chunk.chunk_id, el);
    },
    [chunk.chunk_id, setChunkRef]
  );

  return (
    <div
      ref={refCb}
      data-chunk-id={chunk.chunk_id}
      onClick={() => onClick(chunk.chunk_id)}
      className="chunk-item"
      style={
        highlight
          ? {
              backgroundColor: highlight,
              borderRadius: 4,
              padding: "2px 4px",
              outline: `1px solid ${highlight}`,
            }
          : undefined
      }
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick(chunk.chunk_id);
        }
      }}
    >
      {chunk.content}
    </div>
  );
}

export const ChunkItem = memo(ChunkItemInner);
