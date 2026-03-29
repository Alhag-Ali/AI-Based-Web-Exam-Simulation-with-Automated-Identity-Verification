import os
import re

# ── Prompt templates (one per language) ──────────────────────────────────────

PROMPT_EN = """
You are a university professor. Create ONE multiple-choice exam question based on the given topic and context.

Topic: "{query}"

Use ONLY the following context:

{context}

Answer EXACTLY in this format:
**Question:**
[Your question here]

A) [Answer A]
B) [Answer B]
C) [Answer C]
D) [Answer D]

Correct answer: [Letter A, B, C or D]
"""

PROMPT_DE = """
Du bist ein Universitätsprofessor. Erstelle EINE Multiple-Choice-Prüfungsfrage basierend auf dem angegebenen Thema und Kontext.

Thema: "{query}"

Verwende NUR den folgenden Kontext:

{context}

Antworte GENAU in diesem Format:
**Frage:**
[Deine Frage hier]

A) [Antwort A]
B) [Antwort B]
C) [Antwort C]
D) [Antwort D]

Korrekte Antwort: [Buchstabe A, B, C oder D]
"""


def detect_language(text: str) -> str:
    """
    Lightweight language detector – no external package needed.
    Returns 'de' for German, 'en' for English.
    Counts how often very-common stopwords of each language appear in the
    first 2 000 characters (enough to judge the dominant language).
    """
    sample = text[:2000].lower()
    words  = re.findall(r"\b\w+\b", sample)
    if not words:
        return "en"

    de_words = {
        "der", "die", "das", "und", "ist", "mit", "von", "für",
        "auf", "ein", "eine", "einer", "auch", "im", "den", "dem",
        "an", "zu", "sich", "bei", "wie", "als", "des", "werden",
        "durch", "nach", "oder", "nicht", "wird", "sind", "haben",
        "kann", "wird", "zum", "zur", "über", "dass",
    }
    en_words = {
        "the", "and", "of", "is", "in", "to", "for", "with",
        "that", "are", "this", "it", "as", "an", "be", "by",
        "or", "not", "from", "at", "has", "have", "can", "we",
        "on", "its", "which", "their", "will", "all", "one",
    }

    de_count = sum(1 for w in words if w in de_words)
    en_count = sum(1 for w in words if w in en_words)

    lang = "de" if de_count > en_count else "en"
    print(f"[RAG] language detection: de={de_count} en={en_count} → '{lang}'")
    return lang


def _parse_llm_output(text: str) -> dict:
    lines = [re.sub(r"\*+", "", l).strip() for l in text.strip().split("\n")]
    lines = [l for l in lines if l]

    question_lines = []
    options = []
    answer_letter = None

    option_re = re.compile(r"^([A-D])[)\.]\s+(.+)$", re.IGNORECASE)
    answer_re = re.compile(
        r"(?:correct\s+answer|korrekte\s+antwort|richtige\s+antwort)\s*:?\s*([A-D])",
        re.IGNORECASE
    )

    in_frage = False

    for line in lines:
        if re.match(r"^(?:question|frage)\s*:", line, re.IGNORECASE):
            in_frage = True
            rest = re.sub(r"^(?:question|frage)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
            if rest:
                question_lines.append(rest)
            continue

        m = option_re.match(line)
        if m:
            in_frage = False
            options.append(f"{m.group(1).upper()}) {m.group(2).strip()}")
            continue

        ma = answer_re.search(line)
        if ma:
            answer_letter = ma.group(1).upper()
            continue

        if in_frage:
            question_lines.append(line)
        elif not options and not answer_letter:
            question_lines.append(line)

    q_text = " ".join(question_lines).strip()
    if not q_text or len(options) < 4:
        return None

    answer = ""
    if answer_letter:
        for opt in options:
            if opt.startswith(f"{answer_letter})"):
                answer = opt
                break
    if not answer and options:
        answer = options[0]

    return {"text": q_text, "options": options, "answer": answer}


def generate_questions_rag(pdf_text: str, topics: list, groq_api_key: str = None,
                           n_per_topic: int = 1, language: str = None) -> list:
    try:
        import chromadb
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma
        from sentence_transformers import CrossEncoder
        from langchain_groq import ChatGroq
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
    except ImportError as e:
        raise ImportError(
            f"RAG packages not installed: {e}. "
            "Please run: pip install langchain-text-splitters langchain-community "
            "sentence-transformers chromadb langchain-groq"
        )

    if groq_api_key:
        os.environ["GROQ_API_KEY"] = groq_api_key

    if not os.environ.get("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY is not set. Please provide an API key.")

    # Auto-detect language if not explicitly provided
    lang = language if language in ("de", "en") else detect_language(pdf_text)
    prompt_template = PROMPT_DE if lang == "de" else PROMPT_EN
    print(f"[RAG] using prompt language: {lang}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""],
    )
    docs = splitter.create_documents([pdf_text])

    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )

    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.4,
        timeout=90,
        max_retries=2,
    )

    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | StrOutputParser()

    questions = []

    chroma_client = chromadb.EphemeralClient()
    vector_db = Chroma.from_documents(
        documents=docs,
        embedding=embedding_model,
        client=chroma_client,
    )

    for topic in topics:
        for _ in range(n_per_topic):
            try:
                retrieved = vector_db.similarity_search_with_score(query=topic, k=10)

                pairs = [[topic, doc.page_content] for doc, _ in retrieved]
                scores = cross_encoder.predict(pairs)

                reranked = sorted(
                    zip([doc for doc, _ in retrieved], scores),
                    key=lambda x: x[1],
                    reverse=True,
                )

                top_docs = [doc for doc, _ in reranked[:3]]
                context_str = "\n\n".join(
                    f"--- Excerpt {i + 1} ---\n{doc.page_content}"
                    for i, doc in enumerate(top_docs)
                )

                llm_output = chain.invoke({"query": topic, "context": context_str})
                q = _parse_llm_output(llm_output)
                if q:
                    questions.append(q)
            except Exception as e:
                print(f"[RAG] Error for topic '{topic}': {e}")

    return questions
