export interface DocumentInfo {
  id: number;
  name: string;
  doc_type: string;
  relative_path?: string;
  has_pdf?: boolean;
  has_html?: boolean;
  has_md?: boolean;
}

export interface ChunkItemApi {
  chunk_id: string;
  chunk_index: number;
  content: string;
  content_preview?: string;
  start_offset?: number;
  end_offset?: number;
  linked_chunk_ids?: string[];
}

export interface ContentAnnotatedResponse {
  document: DocumentInfo;
  content: string;
  format: string;
  chunks: ChunkItemApi[];
}

export interface RelationshipState {
  relationshipGroupId: string;
  sourceChunkId: string;
  sourceDocumentId: number;
  targetDocumentId: string;
  targetChunkIds: string[];
  currentIndex: number;
  assignedColor: string;
}

export interface RelatedChunksResponse {
  relationship_group_id: string;
  target_document: string;
  related_chunks: string[];
}
