"""
Filesystem MCP Server

All file operations are sandboxed inside ALLOWED_ROOT.
Paths passed to tools can be relative to ALLOWED_ROOT OR absolute system paths 
as long as they reside inside ALLOWED_ROOT.

Examples:
- "" or "." → root
- "projects/report.pdf" → valid
- "/Users/hyeonbinchun/Documents/projects/report.pdf" → valid (absolute)
- "/etc/passwd" → not allowed (will be rejected)
"""

from mcp.server.fastmcp import FastMCP
import os
import fnmatch
from pathlib import Path

# Create an MCP server
mcp = FastMCP("Filesystem MCP")

NOTES_FILE = Path(__file__).resolve().parent.parent / "notes.txt"


def ensure_file():
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("")


# Safety: restrict access to files only within a specific directory
ALLOWED_ROOT = os.path.expanduser("/Users/hyeonbinchun/Documents")

def _safe_path(path: str)->str:
    """Resolve and validate that path stays inside ALLOWED_ROOT."""
    # Expand user first (~ format) so isabs check handles it accurately
    expanded = os.path.expanduser(path)
    
    if not os.path.isabs(expanded):
        expanded = os.path.join(ALLOWED_ROOT, expanded)  # anchor relative paths
        
    resolved = os.path.realpath(expanded)
    root = os.path.realpath(ALLOWED_ROOT)
    
    if os.path.commonpath([resolved, root]) != root:
        raise PermissionError(
            f"Access denied: '{path}' is outside the allowed root '{ALLOWED_ROOT}'"
        )
    return resolved

# ── Filesystem tools ──────────────────────────────────────────────────────────

@mcp.tool()
def list_directory(path: str) -> str:
    """
    List the contents of a directory.

    Args:
        path: Path relative to ALLOWED_ROOT.
        Use "" or "." for root.

    Returns:
        One entry per line, prefixed with 'dir:' or 'file:' and file size.
    """
    safe = _safe_path(path)
    if not os.path.isdir(safe):
        return f"'{path}' is not a directory or cannot be accessed."
    entries = sorted(os.scandir(safe), key=lambda e: (not e.is_dir(), e.name.lower()))
    lines = [safe, ""]
    for e in entries:
        prefix = "dir: " if e.is_dir() else "file:"
        size = f"  ({_human_size(e.stat().st_size)})" if e.is_file() else ""
        lines.append(f"  {prefix}  {e.name}{size}")
    return "\n".join(lines)
 

@mcp.tool()
def read_text_file(path: str, max_chars: int = 8000) -> str:
    """
    Read a plain-text file (.txt, .md, .py, .json, and .csv).
 
    Args:
        path: Path relative to ALLOWED_ROOT.
        max_chars: Maximum characters to return (default 8000).

    Returns:
        The file's text content, truncated with a notice if it exceeds max_chars.
    """
    safe = _safe_path(path)
    if not os.path.isfile(safe):
        return f"File not found or cannot be accessed: '{path}'"
 
    with open(safe, "r", errors="replace") as f:
        content = f.read(max_chars)
 
    truncated = os.path.getsize(safe) > max_chars
    suffix = f"\n\n[… truncated – file is larger than {max_chars} chars]" if truncated else ""
    return content + suffix


@mcp.tool()
def read_pdf(path: str, max_pages: int = 10) -> str:
    """
    Extract text from a PDF file using pypdf or pdfminer.

    Args:
        path: Path relative to ALLOWED_ROOT.
        max_pages: Maximum number of pages to extract (default 10).

    Returns:
        Extracted text, with a page count note if the file exceeds max_pages.
    """
    safe = _safe_path(path)
    if not os.path.isfile(safe):
        return f"File not found or cannot be accessed: '{path}'"
 
    # Try pypdf first (usually installed), fall back to pdfminer
    try:
        from pypdf import PdfReader
        reader = PdfReader(safe)
        pages = reader.pages[:max_pages]
        text = "\n\n".join(p.extract_text() or "" for p in pages)
        total = len(reader.pages)
        note = f"\n\n[Showing {min(max_pages, total)} of {total} pages]" if total > max_pages else ""
        return (text.strip() or "(No extractable text found – PDF may be scanned/image-based.)") + note
    except ImportError:
        pass
 
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(safe, maxpages=max_pages)
        return text.strip() or "(No extractable text found.)"
    except ImportError:
        return (
            "Neither 'pypdf' nor 'pdfminer.six' is installed. "
            "Run: pip install pypdf  or  pip install pdfminer.six"
        )


@mcp.tool()
def read_docx(path: str) -> str:
    """
    Extract text from a Word (.docx) file.

    Args:
        path: Path relative to ALLOWED_ROOT.

    Returns:
        Paragraphs joined by blank lines, or a message if the document is empty.
    """
    safe = _safe_path(path)
    if not os.path.isfile(safe):
        return f"File not found or cannot be accessed: '{path}'"
 
    try:
        from docx import Document
        doc = Document(safe)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) or "(Document appears to be empty.)"
    except ImportError:
        return "The 'python-docx' package is not installed. Run: pip install python-docx"
 
 
@mcp.tool()
def find_files(name_pattern: str, search_path: str="", max_results: int = 20) -> str:
    """
    Find files by name using a wildcard pattern (e.g. '*.pdf', 'report_*').

    Args:
        name_pattern: Shell glob pattern to match against filenames.
        search_path: Path relative to ALLOWED_ROOT.
        max_results: Maximum number of results to return (default 20).

    Returns:
        Newline-separated list of matching file paths.
    """
    safe = _safe_path(search_path)
    matches = []
 
    for root, dirs, files in os.walk(safe):
        # Skip hidden directories (e.g. .git, .cache)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if fnmatch.fnmatch(filename.lower(), name_pattern.lower()):
                matches.append(os.path.join(root, filename))
                if len(matches) >= max_results:
                    return "\n".join(matches) + f"\n\n[Stopped at {max_results} results]"
 
    return "\n".join(matches) if matches else f"No files matching '{name_pattern}' found in '{search_path}'."
 
 
@mcp.tool()
def grep_files(search_term: str, search_path: str="", file_pattern: str = "*", max_results: int = 20) -> str:
    """
    Search for text inside files (like the grep command).

    Args:
        search_term: Text to search for (case-insensitive).
        search_path: Path relative to ALLOWED_ROOT.
        file_pattern: Only search files matching this glob (e.g. '*.txt', '*.md').
        max_results: Maximum number of matching lines to return (default 20).

    Returns:
        Matching lines in 'filepath:lineno: content' format.
    """
    safe = _safe_path(search_path)
    results = []
 
    for root, dirs, files in os.walk(safe):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if not fnmatch.fnmatch(filename.lower(), file_pattern.lower()):
                continue
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if search_term.lower() in line.lower():
                            results.append(f"{filepath}:{lineno}: {line.rstrip()}")
                            if len(results) >= max_results:
                                return "\n".join(results) + f"\n\n[Stopped at {max_results} results]"
            except (PermissionError, IsADirectoryError):
                continue
 
    return "\n".join(results) if results else f"No matches for '{search_term}' found."
 
 
@mcp.tool()
def get_file_info(path: str) -> str:
    """
    Return metadata about a file or directory.

    Args:
        path: Path relative to ALLOWED_ROOT.

    Returns:
        Path, type, size, modified/created timestamps, and file extension if applicable.
    """
    safe = _safe_path(path)
    if not os.path.exists(safe):
        return f"Path not found or cannot be accessed: '{path}'"
 
    stat = os.stat(safe)
    import datetime
    kind = "Directory" if os.path.isdir(safe) else "File"
    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    created  = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
 
    lines = [
        f"Path      : {safe}",
        f"Type      : {kind}",
        f"Size      : {_human_size(stat.st_size)}",
        f"Modified  : {modified}",
        f"Created   : {created}",
    ]
    if os.path.isfile(safe):
        _, ext = os.path.splitext(safe)
        lines.append(f"Extension : {ext or '(none)'}")
    return "\n".join(lines)
 

@mcp.prompt()
def usage_policy() -> str:
    """Ground rules for using this MCP server."""
    return (
       "You have access to a filesystem MCP server rooted at the user's Documents folder. "
        "ALWAYS use the MCP tools to find and read files — never use bash or Python to access files. "
        "Paths can be relative to the Documents root (e.g. 'projects/report.docx') OR full absolute paths. "
        "When the user asks about a file, first call find_files to locate it, then read it with "
        "the appropriate read tool (read_pdf, read_docx, or read_text_file)."
    )

# ── Helpers ─────────────────────────────────────────────────────────────────── 
def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"