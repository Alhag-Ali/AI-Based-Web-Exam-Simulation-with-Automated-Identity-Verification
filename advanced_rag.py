# pip install langchain-text-splitters langchain-community sentence-transformers chromadb
# pip install pypdf
# pip install -U sentence-transformers
# pip install -U langchain-groq

from pypdf import PdfReader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters import MarkdownHeaderTextSplitter

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from sentence_transformers import CrossEncoder

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os

import getpass
import argparse

def read_file(file_path:str):
    """
    Reads the entire text content from a given file path.
    This function opens a file from the specified path, reads its
    entire content, and returns it as a single string.
    It automatically handles opening and closing the file.
    
    """
    reader = PdfReader(file_path)
    print("Number of pages in this file", len(reader.pages))
    all_pages = "".join(page.extract_text() for page in reader.pages)
    return all_pages

def RAG_System(all_pages:str, query:str, k_retrieval:int=3, k_rerank:int=3):
    # Splitter initialization
    recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=50,
    separators=["\n\n", "\n", " ", ""]
    )

    # text splitten
    chunks = recursive_splitter.create_documents([all_pages])
    print(f"Number of created Chunks: {len(chunks)}")

    # Indexing (Embedding + Vectore Store)
    print("\n Indexing start ...")
    print("\n Load Embedding Model all-MiniLM-L6-v2 ...")

    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"} # cuda for GPU
        )

    # Chroma save the data in the folder.
    persist_directory = "db_chroma_vorlesung"

    print(f"Create vector database in '{persist_directory}'...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory
    )

    vector_db.persist()

    print("\n --- Indexing completed ! -----")

    # Retrieval
    print("--- Retrieval start ---")
    print(f"The query is: {query}")
    print(f" Search after the Top-{k_retrieval} importent Chunks without Duplicates")

    retrieved_chunks = vector_db.similarity_search_with_score(
        query=query,
        k=k_retrieval
    )

    chunks = []
    for i, (chunk, score) in enumerate(retrieved_chunks):
        chunks.append((chunk.page_content, score))
    chunk_without_duplicates = list(set(chunks))

    for i, (chunk, score) in enumerate(chunk_without_duplicates):
        print(f"--- CHUNK {i+1} (Score: {score:.4f}) ---")
        print(chunk)

    print("----------------------------------------------------")
    print("\n Re-Ranking Start ...")

    print("Lade Cross-Encoder-Modell ...")
    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    # Create pairs for the re-ranker [Query, Chunk-text].
    print(f"Create pairs for {len(retrieved_chunks)} Chunks ...")
    pairs = []
    for i, (chunk, score) in enumerate(retrieved_chunks):
        pairs.append([query, chunk.page_content])

    # Calculate the new relevance scores.
    scores = cross_encoder.predict(pairs)

    # Compine chunks and new Scores
    reranked_chunks = []
    for i in range(len(retrieved_chunks)):
        reranked_chunks.append({
            "chunk": retrieved_chunks[i],
            "score": scores[i]
        })

    # Sort the Chunks desc
    reranked_chunks.sort(key=lambda x: x["score"], reverse=True)

    # --- Ausgabe ---
    print("\n--- Schritt 4 (Re-Ranking) Abgeschlossen! ---")

    # Definiere, wie viele Chunks wir an das LLM senden wollen
    print(f"--- Relevanteste Chunks (Top {k_rerank} nach Re-Ranking) ---")
    final_context_chunks = []
    for i, item_dict in enumerate(reranked_chunks[:k_rerank]):
        doc_object = item_dict['chunk'][0] # Access the Document object
        reranked_score = item_dict['score'] # Access the new re-ranked score
        final_context_chunks.append(doc_object)
        print(f"--- CHUNK {i+1} (Neuer Score: {reranked_score:.4f}) ---")
        print(doc_object.page_content)
        print("--------------------------------------------------\n")

    # --- SCHRITT 5: GENERIERUNG ---
    print("\nStarte Schritt 5: Generierung...")

    if "GROQ_API_KEY" not in os.environ:
        raise ValueError("GROQ_API_KEY is not set in the environment.")

    # laod LLM from Groq


    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0.5,
        reasoning_format="parsed",
        timeout=None,
        max_retries=2,
        #top_p=1,
        reasoning_effort="medium",
        #stream=True,
        stop=None
    )
  # 2. Formatiere den Kontext (die 3 Chunks) zu einem String
    context_string = ""
    for i, chunk in enumerate(final_context_chunks):
        context_string += f"--- Relevanter Auszug {i+1} ---\n"
        context_string += chunk.page_content
        context_string += "\n---------------------------------\n\n"

    # 3. Definiere den finalen Prompt (die Anweisung an das LLM)
    prompt_template = """
    DU BIST EIN UNIVERSITÄTSPROFESSOR. DEINE AUFGABE IST ES, EINE PRÜFUNGSFRAGE ZU ERSTELLEN.

    **Regeln:**
    1. Erstelle EINE klare Multiple-Choice-Frage basierend auf dem Thema: "{query}".
    2. Verwende AUSSCHLIESSLICH die Informationen aus dem untenstehenden "Kontext".
    3. Erfinde KEINE Informationen, die nicht im Kontext stehen.
    4. Gib die Frage und die Antwortmöglichkeiten (A, B, C, D) an.
    5. Gib die korrekte Antwort am Ende an (z.B. "Korrekte Antwort: A").

    **Kontext:**
    {context}

    **Prüfungsfrage:**
    """

    # 4. Erstelle die Prompt-Pipeline
    prompt = ChatPromptTemplate.from_template(prompt_template)
    output_parser = StrOutputParser()

    # Verkette (chain) die Komponenten
    chain = prompt | llm | output_parser

    # 5. Führe die Kette aus (Generiere die Frage)
    print("Sende Kontext und Prompt an das LLM...")
    final_question = chain.invoke({
        "query": query,
        "context": context_string
    })

    # --- Ausgabe ---
    print("\n--- Schritt 5 (Generierung) Abgeschlossen! ---")
    print("Die KI-generierte Prüfungsfrage ist:\n")

    return final_question


def run_rag_from_pdf(file_path: str, query: str, k_retrieval: int = 10, k_rerank: int = 3):
    text = read_file(file_path)
    return RAG_System(text, query, k_retrieval=k_retrieval, k_rerank=k_rerank)

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="AI_Matrial.pdf")
    parser.add_argument("--query", default="Was ist Deep Learning")
    parser.add_argument("--k_retrieval", type=int, default=10)
    parser.add_argument("--k_rerank", type=int, default=3)
    parser.add_argument("--groq_api_key", default=None)
    args = parser.parse_args()

    if args.groq_api_key:
        os.environ["GROQ_API_KEY"] = args.groq_api_key
    elif "GROQ_API_KEY" not in os.environ:
        os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")

    rag_run = run_rag_from_pdf(
        file_path=args.pdf,
        query=args.query,
        k_retrieval=args.k_retrieval,
        k_rerank=args.k_rerank,
    )
    print(rag_run)
    
    
    # ------ Ausgabe ------ #
    # **Frage:**

    # Was ist Deep Learning (DL)?

    # A) Eine spezielle Form des Bestärkenden Lernens, die ausschließlich auf Belohnungen und Bestrafungen basiert.  
    # B) Eine leistungsfähige Unterart des Maschinellen Lernens, die komplexe, vielschichtige Architekturen nutzt, um Muster in Daten zu erkennen.  
    # C) Ein Verfahren zur Optimierung von Lieferketten und Finanzhandelsstrategien.  
    # D) Ein neuronales Netzwerk, das nur aus einer einzigen Schicht besteht.

    # **Korrekte Antwort: B**