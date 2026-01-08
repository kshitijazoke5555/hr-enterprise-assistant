import os
import shutil
import stat
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma 
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.config import settings

# Paths based on project structure
DOCS_DIR = "docs"
VECTOR_DIR = "backend/vectorstore"


def _on_rm_error(func, path, exc_info):
    """Attempt to fix permission issues and retry removal (Windows-friendly)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"⚠️ Could not remove {path}: {e}")

def load_documents():
    documents = []
    if not os.path.exists(DOCS_DIR):
        print(f"❌ Error: {DOCS_DIR} directory not found.")
        return []

    # Optional manifest to explicitly map filenames to metadata.
    manifest = {}
    try:
        import csv
        for manifest_name in ("metadata.csv", "metadata_manifest.csv", "docs_metadata.csv"):
            manifest_path = os.path.join(DOCS_DIR, manifest_name)
            if os.path.exists(manifest_path):
                with open(manifest_path, newline='', encoding='utf-8') as fh:
                    reader = csv.DictReader(fh)
                    if not reader.fieldnames:
                        continue
                    # find a filename-like column
                    key_field = None
                    for h in reader.fieldnames:
                        if h and h.lower() in ('filename', 'file', 'source', 'policy_name'):
                            key_field = h
                            break
                    if not key_field:
                        continue
                    for row in reader:
                        fname = (row.get(key_field) or '').strip()
                        if not fname:
                            continue
                        key = fname.lower()
                        manifest[key] = {
                            'department': (row.get('department') or row.get('dept') or '').strip().lower(),
                            'country': (row.get('country') or '').strip().lower(),
                            'policy_name': (row.get('policy_name') or row.get(key_field) or '').strip()
                        }
                print(f"Loaded metadata manifest: {manifest_path}")
                break
    except Exception:
        manifest = {}

    for file in os.listdir(DOCS_DIR):
        path = os.path.join(DOCS_DIR, file)
        loader = None
        # infer department and country from filename (more robust)
        fn = file.lower()
        inferred_dept = ""
        inferred_country = ""
        # tokenise filename on non-alphanum to find department tokens
        import re
        tokens = re.split(r'[^a-z0-9]+', fn)
        # map common tokens to normalized department names
        dept_map = {
            'hr': 'hr', 'human': 'hr', 'humanresources': 'hr', 'human_resources': 'hr',
            'it': 'it', 'information': 'it', 'informationtechnology': 'it',
            'finance': 'finance', 'payroll': 'finance',
            'product': 'product',
            'engineering': 'engineering', 'eng': 'engineering',
            'common': 'common', 'company': 'common', 'admin': 'admin', 'administration': 'admin'
        }
        for t in tokens:
            if not t:
                continue
            if t in dept_map:
                inferred_dept = dept_map[t]
                break

        # detect country tokens
        if any(t in ('india', 'indian') for t in tokens):
            inferred_country = 'india'
        elif any(t in ('foreign', 'international', 'non_common', 'noncommon', 'non-common') for t in tokens):
            inferred_country = 'foreign'

        # If manifest has an explicit entry for this file (match with or without extension), prefer it
        manifest_entry = None
        if manifest:
            mkey1 = file.lower()
            mkey2 = os.path.splitext(file)[0].lower()
            manifest_entry = manifest.get(mkey1) or manifest.get(mkey2)
            if manifest_entry:
                inferred_dept = manifest_entry.get('department') or inferred_dept
                inferred_country = manifest_entry.get('country') or inferred_country
        try:
            if file.endswith(".pdf"):
                loader = PyPDFLoader(path)
            elif file.endswith(".docx"):
                # Load .docx with several fallbacks to avoid external dependency issues:
                # 1) try python-docx (`docx` module)
                # 2) try langchain's Docx2txtLoader if docx2txt is present
                # 3) fallback to stdlib zip/xml extraction (always available)
                tried = False
                # 1) python-docx
                try:
                    from docx import Document as _DocxDocument
                    from types import SimpleNamespace
                    text = "\n".join([p.text for p in _DocxDocument(path).paragraphs])
                    docs = [SimpleNamespace(page_content=text, metadata={})]
                    for d in docs:
                        meta = d.metadata or {}
                        meta.update({
                            "source": file,
                            "department": (meta.get('department') or inferred_dept or '').strip().lower(),
                            "country": (meta.get('country') or inferred_country or '').strip().lower(),
                            "policy_name": (meta.get('policy_name') or os.path.splitext(file)[0]).strip()
                        })
                        d.metadata = meta
                    documents.extend(docs)
                    continue
                except Exception:
                    pass

                # 2) langchain Docx2txtLoader if available
                try:
                    import importlib
                    if importlib.util.find_spec("docx2txt") is not None:
                        try:
                            Docx2txtLoader = importlib.import_module(
                                "langchain_community.document_loaders"
                            ).Docx2txtLoader
                            loader = Docx2txtLoader(path)
                            tried = True
                        except Exception:
                            tried = False
                except Exception:
                    tried = False

                if tried:
                    # loader will be used below
                    pass
                else:
                    # 3) Stdlib fallback: unzip and parse word/document.xml
                    try:
                        import zipfile
                        import xml.etree.ElementTree as ET
                        with zipfile.ZipFile(path) as z:
                            xml_content = z.read("word/document.xml")
                        root = ET.fromstring(xml_content)
                        # Namespaces handling
                        ns = {k: v for k, v in [node.split('}')[-1].split(':') if ':' in node else (node, '') for node in []]}
                        # Extract all text nodes
                        texts = []
                        for elem in root.iter():
                            if elem.tag.endswith('}t') or elem.tag == 't':
                                if elem.text:
                                    texts.append(elem.text)
                        text = "\n".join(texts)
                        from types import SimpleNamespace
                        docs = [SimpleNamespace(page_content=text, metadata={})]
                        for d in docs:
                            meta = d.metadata or {}
                            meta.update({
                                "source": file,
                                "department": (meta.get('department') or inferred_dept or '').strip().lower(),
                                "country": (meta.get('country') or inferred_country or '').strip().lower(),
                                "policy_name": (meta.get('policy_name') or os.path.splitext(file)[0]).strip()
                            })
                            d.metadata = meta
                        documents.extend(docs)
                        continue
                    except Exception as e:
                        raise ImportError(f"Failed to extract .docx content for {file}: {e}")
            elif file.endswith(".txt"):
                loader = TextLoader(path, encoding="utf-8")
            elif file.endswith(".csv"):
                loader = CSVLoader(path)
            else:
                continue

            if loader:
                # For CSVs, try to read header or first row for explicit department/country
                explicit_headers = {}
                if file.endswith('.csv'):
                    try:
                        import csv
                        with open(path, newline='', encoding='utf-8') as fh:
                            reader = csv.DictReader(fh)
                            # check header fields for department/country
                            hdrs = [h.lower() for h in reader.fieldnames or []]
                            if 'department' in hdrs or 'country' in hdrs:
                                # read first data row to infer values for this file
                                first = next(reader, None)
                                if first:
                                    if 'department' in hdrs and first.get('department'):
                                        explicit_headers['department'] = first.get('department').strip().lower()
                                    if 'country' in hdrs and first.get('country'):
                                        explicit_headers['country'] = first.get('country').strip().lower()
                    except Exception:
                        explicit_headers = {}
                    except Exception:
                        # non-fatal; fallback to filename inference
                        explicit_headers = {}

                docs = loader.load()
                for d in docs:
                    # preserve any existing metadata but add inferred fields
                    meta = d.metadata or {}
                    # treat empty strings as missing: prefer existing non-empty, then explicit headers, then inferred
                    dept_val = (meta.get('department') or explicit_headers.get('department') or inferred_dept or '').strip().lower()
                    country_val = (meta.get('country') or explicit_headers.get('country') or inferred_country or '').strip().lower()
                    policy_name_val = (meta.get('policy_name') or os.path.splitext(file)[0]).strip()
                    meta.update({
                        "source": file,
                        "department": dept_val,
                        "country": country_val,
                        "policy_name": policy_name_val
                    })
                    d.metadata = meta
                documents.extend(docs)
        except Exception as e:
            print(f"⚠️ Error loading {file}: {e}")
    return documents

def ingest():
    # PERMANENT FIX: Remove old vectorstore to prevent 404/database conflicts
    if os.path.exists(VECTOR_DIR):
        print(f"🧹 Clearing existing vector store at {VECTOR_DIR}...")
        try:
            shutil.rmtree(VECTOR_DIR, onerror=_on_rm_error)
        except PermissionError as e:
            print("❌ PermissionError while removing vector store."
                  " Ensure no process (sqlite, server, editor) is using files in backend/vectorstore and try again.")
            print(f"Details: {e}")
            return

    print("🔄 Loading documents from docs/...")
    documents = load_documents()
    
    if not documents:
        print("❌ No documents found.")
        return

    # Splitting text
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(documents)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GEMINI_API_KEY
    )

    print(f"🧠 Creating Vector Store in {VECTOR_DIR}...")
    # Use the new langchain_chroma package logic
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTOR_DIR
    )
    print("✅ Ingestion completed successfully.")

if __name__ == "__main__":
    ingest()