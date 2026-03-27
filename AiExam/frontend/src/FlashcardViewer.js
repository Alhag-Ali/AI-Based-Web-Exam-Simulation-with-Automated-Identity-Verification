import React, { useState, useEffect } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000/api/students";

function cleanText(text) {
  if (!text) return "";
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
    .join(" ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function FlashcardViewer({ topic, onClose }) {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };

  const [cards, setCards] = useState([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const knownCount = cards.filter(c => c.known).length;
  const progress = cards.length > 0 ? Math.round((knownCount / cards.length) * 100) : 0;

  const fetchCards = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/learn/topics/${topic.id}/flashcards/`, { headers });
      if (res.data.flashcard_count === 0) {
        await generateCards();
      } else {
        setCards(res.data.flashcards);
      }
    } catch {
      await generateCards();
    } finally {
      setLoading(false);
    }
  };

  const generateCards = async () => {
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/learn/topics/${topic.id}/flashcards/generate/`, {}, { headers });
      setCards(res.data.flashcards);
    } catch {
      setCards([]);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => { fetchCards(); }, [topic.id]);

  const markKnown = async (known) => {
    const card = cards[index];
    try {
      await axios.patch(`${API}/learn/flashcards/${card.id}/mark/`, { known }, { headers });
      setCards(prev => prev.map(c => c.id === card.id ? { ...c, known } : c));
    } catch {}
    next();
  };

  const next = () => {
    setFlipped(false);
    setTimeout(() => setIndex(i => Math.min(i + 1, cards.length - 1)), 120);
  };

  const prev = () => {
    setFlipped(false);
    setTimeout(() => setIndex(i => Math.max(i - 1, 0)), 120);
  };

  const restart = () => {
    setIndex(0);
    setFlipped(false);
    setCards(prev => prev.map(c => ({ ...c, known: false })));
  };

  if (loading || generating) {
    return (
      <div className="fc-overlay">
        <div className="fc-modal">
          <div className="fc-loading">
            <div className="learn-spinner" />
            <p>{generating ? "Karteikarten werden erstellt…" : "Lade Karten…"}</p>
          </div>
        </div>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div className="fc-overlay">
        <div className="fc-modal">
          <div className="fc-header">
            <h3 className="fc-topic-title">{topic.title}</h3>
            <button className="fc-close" onClick={onClose}>✕</button>
          </div>
          <div className="fc-empty">
            <p>Keine Karteikarten für dieses Thema generierbar.</p>
            <button className="btn secondary" onClick={onClose}>Schließen</button>
          </div>
        </div>
      </div>
    );
  }

  const allDone = index >= cards.length - 1 && cards[index]?.known !== undefined;
  const card = cards[index];

  return (
    <div className="fc-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="fc-modal">

        <div className="fc-header">
          <div>
            <div className="fc-topic-label">Thema</div>
            <h3 className="fc-topic-title">{topic.title}</h3>
          </div>
          <button className="fc-close" onClick={onClose} title="Schließen">✕</button>
        </div>

        <div className="fc-progress-row">
          <span className="fc-counter">{index + 1} / {cards.length}</span>
          <div className="fc-progress-track">
            <div className="fc-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="fc-known-count">{knownCount} gewusst</span>
        </div>

        <div className="fc-scene" onClick={() => setFlipped(f => !f)}>
          <div className={`fc-card${flipped ? " flipped" : ""}`}>
            <div className="fc-face fc-front">
              <div className="fc-face-label">Frage</div>
              <div className="fc-face-text">{cleanText(card.question)}</div>
              <div className="fc-hint">Klicken zum Umdrehen</div>
            </div>
            <div className="fc-face fc-back">
              <div className="fc-face-label">Antwort</div>
              <div className="fc-face-text">{cleanText(card.answer)}</div>
            </div>
          </div>
        </div>

        <div className="fc-actions">
          <button className="btn secondary fc-nav" onClick={prev} disabled={index === 0}>← Zurück</button>

          {flipped ? (
            <div className="fc-rating">
              <button className="btn danger fc-rating-btn" onClick={() => markKnown(false)}>
                ✗ Noch nicht
              </button>
              <button className="btn success fc-rating-btn" onClick={() => markKnown(true)}>
                ✓ Gewusst
              </button>
            </div>
          ) : (
            <button className="btn fc-flip-btn" onClick={() => setFlipped(true)}>
              Antwort zeigen
            </button>
          )}

          <button className="btn secondary fc-nav" onClick={next} disabled={index === cards.length - 1}>Weiter →</button>
        </div>

        {knownCount === cards.length && cards.length > 0 && (
          <div className="fc-complete">
            <span className="fc-complete-icon">🎉</span>
            <span>Alle Karten gewusst!</span>
            <button className="btn secondary" style={{ padding: "6px 14px", fontSize: 13 }} onClick={restart}>
              Wiederholen
            </button>
          </div>
        )}

        <div className="fc-dots">
          {cards.map((c, i) => (
            <button
              key={c.id}
              className={`fc-dot${i === index ? " active" : ""}${c.known ? " known" : ""}`}
              onClick={() => { setFlipped(false); setIndex(i); }}
              title={`Karte ${i + 1}`}
            />
          ))}
        </div>

      </div>
    </div>
  );
}

export default FlashcardViewer;
