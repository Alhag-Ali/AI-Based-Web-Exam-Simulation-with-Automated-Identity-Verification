import os
import re
import json

# ── Professor-style prompts (proven quality) ─────────────────────────────────

PROMPT_MCQ_EN = """
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

PROMPT_MCQ_DE = """
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

PROMPT_FLASHCARD_BATCH_DE = """
Du bist ein Universitätsprofessor. Erstelle genau {count} Karteikarten zum Thema "{query}" basierend auf dem Kontext.

Verwende NUR den folgenden Kontext:

{context}

Antworte NUR mit einem JSON-Array:
[{{"question": "...", "answer": "..."}}]
"""

PROMPT_FLASHCARD_BATCH_EN = """
You are a university professor. Create exactly {count} flashcards for the topic "{query}" based on the context.

Use ONLY the following context:

{context}

Return ONLY a JSON array:
[{{"question": "...", "answer": "..."}}]
"""

PROMPT_FLASHCARD_EN = """
You are a university professor. Create ONE flashcard (question + answer) for the topic "{query}" based on the context below.

Use ONLY the following context:

{context}

Return ONLY a JSON object:
{{"question": "...", "answer": "..."}}

The question must test a specific fact from the context. The answer must be concise and taken from the context.
"""

PROMPT_FLASHCARD_DE = """
Du bist ein Universitätsprofessor. Erstelle EINE Karteikarte (Frage + Antwort) zum Thema "{query}" basierend auf dem Kontext.

Verwende NUR den folgenden Kontext:

{context}

Antworte NUR mit einem JSON-Objekt:
{{"question": "...", "answer": "..."}}

Die Frage muss einen konkreten Fakt aus dem Kontext abfragen. Die Antwort muss prägnant sein und aus dem Kontext stammen.
"""

PROMPT_EN = PROMPT_MCQ_EN
PROMPT_DE = PROMPT_MCQ_DE


def detect_language(text: str) -> str:
    sample = text[:2000].lower()
    words = re.findall(r"\b\w+\b", sample)
    if not words:
        return "en"

    de_words = {
        "der", "die", "das", "und", "ist", "mit", "von", "für",
        "auf", "ein", "eine", "einer", "auch", "im", "den", "dem",
        "an", "zu", "sich", "bei", "wie", "als", "des", "werden",
        "durch", "nach", "oder", "nicht", "wird", "sind", "haben",
        "kann", "zum", "zur", "über", "dass",
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
    print(f"[RAG] language detection: de={de_count} en={en_count} -> '{lang}'")
    return lang


def _parse_llm_output(text: str) -> dict | None:
    lines = [re.sub(r"\*+", "", l).strip() for l in text.strip().split("\n")]
    lines = [l for l in lines if l]

    question_lines = []
    options = []
    answer_letter = None

    option_re = re.compile(r"^([A-D])[)\.]\s+(.+)$", re.IGNORECASE)
    answer_re = re.compile(
        r"(?:correct\s+answer|korrekte\s+antwort|richtige\s+antwort)\s*:?\s*([A-D])",
        re.IGNORECASE,
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


def _parse_flashcard_json(text: str) -> dict | None:
    text = text.strip()
    obj_match = re.search(r"\{[\s\S]*?\}", text)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            if isinstance(data, dict):
                q = str(data.get("question", "")).strip()
                a = str(data.get("answer", "")).strip()
                if q and a:
                    return {"question": q, "answer": a}
        except json.JSONDecodeError:
            pass

    arr_match = re.search(r"\[[\s\S]*\]", text)
    if arr_match:
        try:
            data = json.loads(arr_match.group(0))
            if isinstance(data, list) and data:
                item = data[0]
                q = str(item.get("question", "")).strip()
                a = str(item.get("answer", "")).strip()
                if q and a:
                    return {"question": q, "answer": a}
        except json.JSONDecodeError:
            pass
    return None


def _parse_flashcard_list(text: str) -> list:
    text = text.strip()
    arr_match = re.search(r"\[[\s\S]*\]", text)
    if arr_match:
        try:
            data = json.loads(arr_match.group(0))
            if isinstance(data, list):
                cards = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    q = str(item.get("question", "")).strip()
                    a = str(item.get("answer", "")).strip()
                    if q and a:
                        cards.append({"question": q, "answer": a})
                if cards:
                    return cards
        except json.JSONDecodeError:
            pass
    single = _parse_flashcard_json(text)
    return [single] if single else []


def _build_topic_query(title, summary="", key_concepts=None):
    parts = [title.strip()]
    if summary:
        parts.append(summary[:200])
    for c in (key_concepts or [])[:3]:
        parts.append(str(c))
    return " - ".join(parts)


class SlideRAGSession:
    """
    Same pipeline as professor exam generation:
    1. Chunk full PDF text (1000 chars, overlap 50)
    2. Embed with MiniLM
    3. Per topic: similarity search k=10 → CrossEncoder rerank → top 3 chunks
    4. LLM generates one item per call (professor prompt)
    """

    def __init__(self, pdf_text: str, groq_api_key: str = None, language: str = None):
        try:
            import chromadb
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma
            from sentence_transformers import CrossEncoder
            from langchain_groq import ChatGroq
        except ImportError as e:
            raise ImportError(
                f"RAG packages not installed: {e}. "
                "pip install langchain-text-splitters langchain-community "
                "sentence-transformers chromadb langchain-groq"
            )

        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
        if not os.environ.get("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY is not set.")

        self.pdf_text = (pdf_text or "").strip()
        if len(self.pdf_text) < 100:
            raise ValueError("PDF text too short for RAG.")

        self.lang = language if language in ("de", "en") else detect_language(self.pdf_text)
        print(f"[RAG] using prompt language: {self.lang}")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", ""],
        )
        docs = splitter.create_documents([self.pdf_text])

        embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            timeout=90,
            max_retries=2,
        )

        chroma_client = chromadb.EphemeralClient()
        self.vector_db = Chroma.from_documents(
            documents=docs,
            embedding=embedding_model,
            client=chroma_client,
        )

    def retrieve_context(self, query: str, k_retrieve: int = 10, k_top: int = 3) -> str:
        retrieved = self.vector_db.similarity_search_with_score(query=query, k=k_retrieve)

        pairs = [[query, doc.page_content] for doc, _ in retrieved]
        scores = self.cross_encoder.predict(pairs)

        reranked = sorted(
            zip([doc for doc, _ in retrieved], scores),
            key=lambda x: x[1],
            reverse=True,
        )

        top_docs = [doc for doc, _ in reranked[:k_top]]
        return "\n\n".join(
            f"--- Excerpt {i + 1} ---\n{doc.page_content}"
            for i, doc in enumerate(top_docs)
        )

    def generate_mcq(self, query: str) -> dict | None:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        prompt_template = PROMPT_MCQ_DE if self.lang == "de" else PROMPT_MCQ_EN
        context_str = self.retrieve_context(query)
        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm | StrOutputParser()
        llm_output = chain.invoke({"query": query, "context": context_str})
        return _parse_llm_output(llm_output)

    def generate_flashcard(self, query: str) -> dict | None:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        prompt_template = PROMPT_FLASHCARD_DE if self.lang == "de" else PROMPT_FLASHCARD_EN
        context_str = self.retrieve_context(query)
        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm | StrOutputParser()
        llm_output = chain.invoke({"query": query, "context": context_str})
        return _parse_flashcard_json(llm_output)


def generate_questions_rag(
    pdf_text: str,
    topics: list,
    groq_api_key: str = None,
    n_per_topic: int = 1,
    language: str = None,
) -> list:
    """Professor-style RAG — index full PDF, one MCQ per topic per call."""
    session = SlideRAGSession(pdf_text, groq_api_key, language)
    questions = []

    for topic in topics:
        query = topic if isinstance(topic, str) else _build_topic_query(
            topic.get("title", ""),
            topic.get("summary", ""),
            topic.get("key_concepts"),
        )
        for _ in range(n_per_topic):
            try:
                q = session.generate_mcq(query)
                if q:
                    questions.append(q)
            except Exception as e:
                print(f"[RAG] Error for topic '{query}': {e}")

    return questions


def generate_flashcards_for_topic_rag(
    pdf_text: str,
    topic_title: str,
    summary: str = "",
    key_concepts: list = None,
    count: int = 8,
    groq_api_key: str = None,
    language: str = None,
    session: SlideRAGSession = None,
) -> list:
    """Professor-style retrieval + batch flashcard generation."""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    own_session = session is None
    if own_session:
        session = SlideRAGSession(pdf_text, groq_api_key, language)

    query = _build_topic_query(topic_title, summary, key_concepts)
    context_str = session.retrieve_context(query)

    prompt_template = (
        PROMPT_FLASHCARD_BATCH_DE if session.lang == "de" else PROMPT_FLASHCARD_BATCH_EN
    )
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | session.llm | StrOutputParser()

    try:
        llm_output = chain.invoke({"query": query, "context": context_str, "count": count})
        cards = _parse_flashcard_list(llm_output)
        if cards:
            print(f"[RAG] flashcards for '{topic_title}': {len(cards)} cards (batch)")
            return cards[:count]
    except Exception as e:
        print(f"[RAG] batch flashcards failed for '{topic_title}': {e}")

    cards = []
    seen = set()
    sub_queries = [query] + [f"{topic_title} {c}" for c in (key_concepts or [])[:count]]
    for i in range(min(count, 5)):
        try:
            sub_q = sub_queries[i % len(sub_queries)]
            card = session.generate_flashcard(sub_q)
            if card and card["question"] not in seen:
                cards.append(card)
                seen.add(card["question"])
        except Exception as e:
            print(f"[RAG] single flashcard error: {e}")

    print(f"[RAG] flashcards for '{topic_title}': {len(cards)} cards")
    return cards[:count]


def generate_questions_for_topic_rag(
    pdf_text: str,
    topic_title: str,
    summary: str = "",
    key_concepts: list = None,
    n: int = 2,
    groq_api_key: str = None,
    language: str = None,
    existing_questions: list = None,
    session: SlideRAGSession = None,
) -> list:
    own_session = session is None
    if own_session:
        session = SlideRAGSession(pdf_text, groq_api_key, language)

    query = _build_topic_query(topic_title, summary, key_concepts)
    questions = []
    existing_texts = {q.get("text", "") for q in (existing_questions or [])}

    sub_queries = [query]
    for c in (key_concepts or [])[:n]:
        sub_queries.append(f"{topic_title} {c}")

    for i in range(n):
        sub_q = sub_queries[i % len(sub_queries)]
        try:
            q = session.generate_mcq(sub_q)
            if q and q["text"] not in existing_texts:
                questions.append(q)
                existing_texts.add(q["text"])
        except Exception as e:
            print(f"[RAG] MCQ error for '{sub_q}': {e}")

    print(f"[RAG] quiz for '{topic_title}': {len(questions)} questions")
    return questions


def generate_mock_exam_rag(
    pdf_text: str,
    topics: list,
    groq_api_key: str = None,
    questions_per_topic: int = 2,
    max_questions: int = 20,
    language: str = None,
) -> list:
    """Mock exam using one shared SlideRAGSession on full PDF."""
    session = SlideRAGSession(pdf_text, groq_api_key, language)
    all_questions = []

    for topic in topics:
        title = topic.get("title", "") if isinstance(topic, dict) else str(topic)
        if not title:
            continue
        qs = generate_questions_for_topic_rag(
            pdf_text=pdf_text,
            topic_title=title,
            summary=topic.get("summary", "") if isinstance(topic, dict) else "",
            key_concepts=topic.get("key_concepts") if isinstance(topic, dict) else None,
            n=questions_per_topic,
            groq_api_key=groq_api_key,
            language=language,
            existing_questions=all_questions,
            session=session,
        )
        all_questions.extend(qs)
        if len(all_questions) >= max_questions:
            break

    print(f"[RAG] mock exam: {len(all_questions)} total questions")
    return all_questions[:max_questions]


def generate_flashcards_rag(pdf_text, topic, count=8, groq_api_key=None, language=None):
    return generate_flashcards_for_topic_rag(
        pdf_text=pdf_text,
        topic_title=topic,
        count=count,
        groq_api_key=groq_api_key,
        language=language,
    )
