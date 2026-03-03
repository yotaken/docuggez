import os
import glob
import javalang
from sqlalchemy import create_engine, text
from openai import OpenAI
from tqdm import tqdm
import re


DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL_CLASSIF")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("MODEL_CLASSIFICATION")

client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)

engine = create_engine(DATABASE_URL)

def detect_layer(file_path, annotations):
    if "domain" in file_path:
        return "domain"
    if "application" in file_path:
        return "application"
    if "infrastructure" in file_path:
        return "infrastructure"
    if "interfaces" in file_path:
        return "interface"
    if "test" in file_path:
        return "test"

    if "@RestController" in annotations:
        return "interface"
    if "@Repository" in annotations:
        return "infrastructure"
    if "@Entity" in annotations:
        return "domain"
    if "@Service" in annotations:
        return "application"
    if "@Test" in annotations:
        return "test"

    return "unknown"

def embed(text):
    response = client.embeddings.create(
        model=MODEL,
        input=text
    )
    return response.data[0].embedding


KNOWN_TYPES = [
    "CommandInvocation",
    "QueryInvocation",
    "Command",
    "Query",
    "Server",
    "Repository",
    "Entity",
    "Service"
]

def extract_semantic_metadata(class_name):

    type_detected = None
    for t in KNOWN_TYPES:
        if class_name.endswith(t):
            type_detected = t
            base = class_name.replace(t, "")
            break

    if not type_detected:
        return None, None, None

    # Separar palabras por mayúsculas
    parts = re.findall(r'[A-Z][a-z]*', base)

    if len(parts) < 2:
        return None, None, None

    scope = parts[0].lower()
    entity = parts[1].lower()

    # El resto sería el caso de uso
    action = "".join(parts[2:]).lower() if len(parts) > 2 else None

    return scope, entity, action

def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS code_chunks (
                                                                     id SERIAL PRIMARY KEY,
                                                                     module TEXT,
                                                                     layer TEXT,
                                                                     type TEXT,
                                                                     scope TEXT,
                                                                     entity TEXT,
                                                                     class_name TEXT,
                                                                     method_name TEXT,
                                                                     annotations TEXT,
                                                                     file_path TEXT,
                                                                     content TEXT,
                                                                     embedding vector(1024)
                              );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS code_chunks_embedding_idx ON code_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS code_chunks_module_idx ON code_chunks (module);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS code_chunks_layer_idx ON code_chunks (layer);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS code_chunks_scope_idx ON code_chunks (scope);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS code_chunks_entity_idx ON code_chunks (entity);"))

def extract_java_structure(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    try:
        tree = javalang.parse.parse(content)
    except:
        return []

    chunks = []

    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        class_name = node.name
        annotations = [a.name for a in node.annotations]
        layer = detect_layer(file_path, str(annotations))
        scope, entity, action = extract_semantic_metadata(class_name)

        class_code = content  # podrías extraer solo el bloque

        chunks.append({
            "type": "class",
            "class_name": class_name,
            "method_name": None,
            "annotations": str(annotations),
            "layer": layer,
            "scope": scope,
            "entity": entity,
            "content": class_code
        })

        for method in node.methods:
            method_code = content
            chunks.append({
                "type": "method",
                "class_name": class_name,
                "method_name": method.name,
                "annotations": str([a.name for a in method.annotations]),
                "layer": layer,
                "scope": scope,
                "entity": entity,
                "content": method_code
            })

    return chunks

def ingest_codebase(root="/codebase"):
    files = glob.glob(f"{root}/**/*.java", recursive=True)

    with engine.begin() as conn:
        for file in tqdm(files):
            module = file.split("/")[2]  # ajusta a tu estructura
            chunks = extract_java_structure(file)

            for chunk in chunks:
                emb = embed(chunk["content"])

                conn.execute(text("""
                                  INSERT INTO code_chunks
                                  (module, layer, type, scope, entity, class_name, method_name,
                                   annotations, file_path, content, embedding)
                                  VALUES
                                      (:module, :layer, :type, :scope, :entity, :class_name, :method_name,
                                       :annotations, :file_path, :content, :embedding)
                                  """), {
                                 **chunk,
                                 "module": module,
                                 "file_path": file,
                                 "embedding": emb
                             })

if __name__ == "__main__":
    init_db()
    ingest_codebase()