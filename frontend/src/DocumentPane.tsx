import { ChunkList } from "./ChunkList";
import type { ChunkItemApi } from "./types";

interface DocumentPaneProps {
  documentName: string;
  documentId: number;
  chunks: ChunkItemApi[];
  onChunkClick: (chunkId: string) => void;
  setChunkRef: (chunkId: string, el: HTMLElement | null) => void;
  getHighlight: (chunkId: string) => string | undefined;
}

export function DocumentPane({
  documentName,
  documentId: _documentId,
  chunks,
  onChunkClick,
  setChunkRef,
  getHighlight,
}: DocumentPaneProps) {
  const handleClick = (chunkId: string) => {
    onChunkClick(chunkId);
  };

  return (
    <div className="document-pane">
      <h3 className="document-pane-title">{documentName}</h3>
      <div className="document-pane-scroll" style={{ overflowY: "auto" }}>
        <ChunkList
          chunks={chunks}
          onChunkClick={handleClick}
          setChunkRef={setChunkRef}
          getHighlight={getHighlight}
        />
      </div>
    </div>
  );
}
