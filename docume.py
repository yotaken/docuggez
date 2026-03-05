import os
from datetime import datetime
from openai import OpenAI
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_RETRIEVAL = os.getenv("MODEL_RETRIEVAL")
OPENAI_BASE_URL_RETRIEVE = os.getenv("OPENAI_BASE_URL_RETRIEVE")
MODEL_LLM = os.getenv("MODEL_LLM")
OPENAI_BASE_URL_LLM = os.getenv("OPENAI_BASE_URL_LLM")
SCOPES = os.getenv("SCOPES")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OUTPUT_DIR = f"/app/docs/{datetime.today()}"

client = OpenAI(
    base_url=OPENAI_BASE_URL_LLM,
    api_key=OPENAI_API_KEY
)

engine = create_engine(DATABASE_URL)


def get_modules():
    with engine.connect() as conn:
        result = conn.execute(text("""
                                   SELECT DISTINCT module
                                   FROM code_chunks
                                   """))
        return [r[0] for r in result]


def retrieve_endpoint_by_scope(scope, limit=20, offset=0):
    with engine.connect() as conn:
        result = conn.execute(text("""
                                   SELECT content
                                   FROM code_chunks
                                   WHERE scope = :scope
                                     AND type = 'class'
                                     AND entity IS NOT NULL
                                     AND annotations LIKE '%Path%'
                                     AND class_name LIKE '%Server%'
                                   LIMIT :limit OFFSET :offset
                                   """), {
                                  "scope": scope,
                                  "limit": limit,
                                  "offset": offset
                              })
        return [r[0] for r in result]

def generate_section(prompt):
    response = client.chat.completions.create(
        model=MODEL_LLM,
        messages=[
            {"role": "system",
             "content": "Actúa como un arquitecto de software senior con amplios conocimientos en DDD (Domain Driven Design), JAVA EE, DDD, CQRS, etc. Además eres excelente analista técnico motivado por el movimiento Software Craftsmanship."},
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


def generate_scope_documentation(scope):
    filename = f"{scope}.md"

    write_md(filename, f"# Documentación del Scope: {scope}")
    write_md(filename, f"_Generado: {datetime.now()}_\n")
    chunks = 'true'
    offset = 0
    while chunks:
        chunks = retrieve_endpoint_by_scope(scope, limit=25, offset=offset)
        offset += 25
        if chunks is None or len(chunks) == 0:
            print(f"Finalizando {scope}...")
            break
        context = "\n\n".join(chunks)
        prompt = f"""
        Analiza el siguiente código perteneciente al scope {scope}.
    
        {context}
    
        Genera:            
        - Resumen de casos de Uso
        - Responsabilidades
        - Para bloque del scope:
            - Nombre del caso de uso: Descripción clara del objetivo
            - Funcionalidad detallada            
            - Endpoint (notación @Path): Endpoints o métodos expuestos (GET, POST, PUT, DELETE, etc.)
            - Descripción de la funcionalidad
        - Observaciones arquitectónicas
        """

        section = generate_section(prompt)
        print(f"Seguimos en {scope}...")
        write_md(filename, f"## Scope: {scope}")
        write_md(filename, section)


def generate_global_architecture():
    filename = "00_arquitectura_general.md"

    write_md(filename, "# Arquitectura General del Sistema")
    write_md(filename, f"_Generado: {datetime.now()}_\n")

    with engine.connect() as conn:
        result = conn.execute(text("""
                                   SELECT content
                                   FROM code_chunks
                                   WHERE class_name NOT IN ('Builder', 'InstanceFactory')
                                     and layer IN ('domain', 'infrastructure', 'application')
                                     AND type = 'class'
                                     AND scope IS NOT NULL
                                   LIMIT 50
                                   """))
        chunks = [r[0] for r in result]

    context = "\n\n".join(chunks)

    prompt = f"""
    Analiza el siguiente sistema Java EE con DDD.

    {context}

    Genera:

    1. Descripción general
    2. Arquitectura del Proyecto
    3. Describe el patrón de arquitectura utilizado
    4. Explica la estructura de capas y cómo se comunican entre sí
    """

    section = generate_section(prompt)
    write_md(filename, section)


def reranking():
    prompt = f"""
    Analiza el siguiente documento.

    Devuelve únicamente una lista estructurada de:
    
    - Secciones duplicadas
    - Párrafos redundantes
    - Explicaciones repetidas
    - Clases descritas múltiples veces
    
    NO reescribas el documento.
    Solo identifica duplicados.
    """
    LISTA_DUPLICADOS = ""

    prompt_secondo = f"""
    Basándote en el siguiente documento y en esta lista de duplicados detectados:

    {LISTA_DUPLICADOS}
    
    Reescribe el documento eliminando únicamente las redundancias indicadas.
    
    Reglas:
    - No elimines información técnica única.
    - No simplifiques en exceso.
    - Mantén estructura y nivel de detalle.
    - No añadas información nueva.
    - Trabaja únicamente con el contenido proporcionado.
    
    Reglas adicionales:
    - Si dos secciones describen el mismo concepto, mantén la versión más detallada y elimina la más superficial.   
    """
    pass


if __name__ == "__main__":
    print("Generando arquitectura global...")
    generate_global_architecture()

    modules = get_modules()
    # generate_module_documentation(layer)
    for project_scope in SCOPES:
        print(f"Generando documentación sobre el scope: {project_scope}")
        generate_scope_documentation(project_scope)

    print(f"Documentación generada en {OUTPUT_DIR}")

    reranking()
