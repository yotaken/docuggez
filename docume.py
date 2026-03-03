import os
from sqlalchemy import create_engine, text
from openai import OpenAI
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_RETRIEVAL = os.getenv("MODEL_RETRIEVAL")
OPENAI_BASE_URL_RETRIEVE = os.getenv("OPENAI_BASE_URL_RETRIEVE")
MODEL_LLM = os.getenv("MODEL_LLM")
OPENAI_BASE_URL_LLM = os.getenv("OPENAI_BASE_URL_LLM")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OUTPUT_DIR = f"/app/docs/{datetime.today()}"

clientEmbeddingRetrieval = OpenAI(
    base_url=OPENAI_BASE_URL_RETRIEVE,
    api_key=OPENAI_API_KEY
)

client = OpenAI(
    base_url=OPENAI_BASE_URL_LLM,
    api_key=OPENAI_API_KEY
)

engine = create_engine(DATABASE_URL)

def embed_query(query):
    response = clientEmbeddingRetrieval.embeddings.create(
        model=MODEL_RETRIEVAL,
        input=query
    )
    return response.data[0].embedding

def get_modules():
    with engine.connect() as conn:
        result = conn.execute(text("""
                                   SELECT DISTINCT module FROM code_chunks
                                   """))
        return [r[0] for r in result]

def retrieve_by_module_and_layer(module, layer, limit=20):
    with engine.connect() as conn:
        result = conn.execute(text("""
                                   SELECT content
                                   FROM code_chunks
                                   WHERE module = :module
                                     AND layer = :layer
                                       LIMIT :limit
                                   """), {
                                  "module": module,
                                  "layer": layer,
                                  "limit": limit
                              })
        return [r[0] for r in result]

def generate_section(prompt):
    response = client.chat.completions.create(
        model=MODEL_LLM,
        messages=[
            {"role": "system", "content": "Eres un arquitecto de software experto en JAVA EE, DDD, CQRS, JPA y RabbitMQ."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

def write_md(filename, content):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content + "\n\n")

def generate_module_documentation(module):
    filename = f"{module}.md"

    write_md(filename, f"# Documentación del Módulo: {module}")
    write_md(filename, f"_Generado: {datetime.now()}_\n")

    layers = ["interface", "application", "domain", "infrastructure", "test"]

    for layer in layers:
        print(f"Generando documentación {module} - {layer}")

        chunks = retrieve_by_module_and_layer(module, layer, limit=25)

        if not chunks:
            continue

        context = "\n\n".join(chunks)

        prompt = f"""
        Analiza el siguiente código perteneciente al módulo {module}
        en la capa {layer}.

        {context}

        Genera:

        - Responsabilidad de la capa
        - Componentes principales
        - Clases relevantes
        - Flujos de ejecución
        - Eventos RabbitMQ si existen
        - Uso de JPA si aplica
        - Observaciones arquitectónicas
        """

        section = generate_section(prompt)

        write_md(filename, f"## Capa: {layer}")
        write_md(filename, section)

def generate_global_architecture():
    filename = "00_arquitectura_general.md"

    write_md(filename, "# Arquitectura General del Sistema")
    write_md(filename, f"_Generado: {datetime.now()}_\n")

    with engine.connect() as conn:
        result = conn.execute(text("""
                                   SELECT content FROM code_chunks LIMIT 50
                                   """))
        chunks = [r[0] for r in result]

    context = "\n\n".join(chunks)

    prompt = f"""
    Analiza el siguiente sistema DDD con CQRS.

    {context}

    Genera:

    1. Descripción general
    2. Bounded contexts detectados
    3. Patrón CQRS aplicado
    4. Uso de JPA
    5. Integraciones RabbitMQ
    6. Posible arquitectura C4
    """

    section = generate_section(prompt)
    write_md(filename, section)


if __name__ == "__main__":
    print("Generando arquitectura global...")
    generate_global_architecture()

    modules = get_modules()

    for module in modules:
        print(f"Generando módulo: {module}")
        generate_module_documentation(module)

    print(f"Documentación generada en {OUTPUT_DIR}")