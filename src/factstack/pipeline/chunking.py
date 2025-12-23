"""Document chunking for FactStack."""

import re
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from factstack.utils.text import generate_chunk_id, extract_title_from_markdown


@dataclass
class Chunk:
    """A chunk of document text with metadata."""
    chunk_id: str
    text: str
    source_path: str
    title: Optional[str] = None
    chunk_index: int = 0
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DocumentChunker:
    """Chunks documents into smaller pieces for indexing."""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """Initialize chunker.
        
        Args:
            chunk_size: Maximum characters per chunk
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str, source_path: str) -> List[Chunk]:
        """Split text into chunks with overlap.
        
        Args:
            text: The text to chunk
            source_path: Path to the source document
        
        Returns:
            List of Chunk objects
        """
        # Extract title from markdown
        title = extract_title_from_markdown(text)
        
        # Clean text while preserving paragraph structure
        paragraphs = self._split_into_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If paragraph fits in current chunk, add it
            if len(current_chunk) + len(para) + 1 <= self.chunk_size:
                current_chunk = current_chunk + "\n" + para if current_chunk else para
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunk_id = generate_chunk_id(source_path, chunk_index)
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        text=current_chunk.strip(),
                        source_path=source_path,
                        title=title,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1
                
                # Start new chunk
                # If paragraph is too long, split it
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(para, source_path, chunk_index)
                    chunks.extend(sub_chunks)
                    chunk_index += len(sub_chunks)
                    current_chunk = ""
                else:
                    # Include overlap from previous chunk
                    if chunks and self.chunk_overlap > 0:
                        overlap_text = chunks[-1].text[-self.chunk_overlap:]
                        current_chunk = overlap_text + "\n" + para
                    else:
                        current_chunk = para
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunk_id = generate_chunk_id(source_path, chunk_index)
            chunks.append(Chunk(
                chunk_id=chunk_id,
                text=current_chunk.strip(),
                source_path=source_path,
                title=title,
                chunk_index=chunk_index
            ))
        
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines or markdown headers
        paragraphs = re.split(r'\n\n+|(?=^#{1,6}\s)', text, flags=re.MULTILINE)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _split_long_paragraph(
        self, 
        para: str, 
        source_path: str, 
        start_index: int
    ) -> List[Chunk]:
        """Split a long paragraph into smaller chunks."""
        chunks = []
        title = extract_title_from_markdown(para)
        
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', para)
        current = ""
        idx = start_index
        
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= self.chunk_size:
                current = current + " " + sentence if current else sentence
            else:
                if current:
                    chunk_id = generate_chunk_id(source_path, idx)
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        text=current.strip(),
                        source_path=source_path,
                        title=title,
                        chunk_index=idx
                    ))
                    idx += 1
                
                # If single sentence is too long, force split
                if len(sentence) > self.chunk_size:
                    for i in range(0, len(sentence), self.chunk_size):
                        chunk_id = generate_chunk_id(source_path, idx)
                        chunks.append(Chunk(
                            chunk_id=chunk_id,
                            text=sentence[i:i+self.chunk_size].strip(),
                            source_path=source_path,
                            title=title,
                            chunk_index=idx
                        ))
                        idx += 1
                    current = ""
                else:
                    current = sentence
        
        if current.strip():
            chunk_id = generate_chunk_id(source_path, idx)
            chunks.append(Chunk(
                chunk_id=chunk_id,
                text=current.strip(),
                source_path=source_path,
                title=title,
                chunk_index=idx
            ))
        
        return chunks
    
    def chunk_file(self, file_path: Path) -> List[Chunk]:
        """Chunk a single file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of Chunk objects
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.chunk_text(content, str(file_path))
    
    def chunk_directory(self, dir_path: Path) -> List[Chunk]:
        """Chunk all markdown and text files in a directory.
        
        Args:
            dir_path: Path to the directory
        
        Returns:
            List of Chunk objects from all files
        """
        chunks = []
        extensions = {'.md', '.txt', '.markdown'}
        
        for file_path in dir_path.rglob('*'):
            if file_path.suffix.lower() in extensions:
                file_chunks = self.chunk_file(file_path)
                chunks.extend(file_chunks)
        
        return chunks
