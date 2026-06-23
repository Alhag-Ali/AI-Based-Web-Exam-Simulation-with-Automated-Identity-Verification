import React, { useState, useEffect } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000/api/students";

export default function QuizViewer({ topic, onClose }) {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };

  const [questions, setQuestions] = useState([]);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [showResults, setShowResults] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const fetchQuiz = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/learn/topics/${topic.id}/quiz/`, { headers });
      if (res.data.question_count === 0) {
        await generateQuiz();
      } else {
        setQuestions(res.data.questions);
      }
    } catch {
      await generateQuiz();
    } finally {
      setLoading(false);
    }
  };

  const generateQuiz = async () => {
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/learn/topics/${topic.id}/quiz/generate/`, {}, { headers });
      setQuestions(res.data.questions);
    } catch (err) {
      setQuestions([]);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => { fetchQuiz(); }, [topic.id]);

  const selectAnswer = (option) => {
    setAnswers(prev => ({ ...prev, [index]: option }));
  };

  const score = () => {
    let correct = 0;
    questions.forEach((q, i) => {
      if (answers[i] === q.answer) correct++;
    });
    return { correct, total: questions.length, pct: questions.length ? Math.round((correct / questions.length) * 100) : 0 };
  };

  if (loading || generating) {
    return (
      <div className="fc-overlay">
        <div className="fc-modal">
          <div className="fc-loading">
            <div className="learn-spinner" />
            <p>{generating ? "Generating quiz questions…" : "Loading quiz…"}</p>
          </div>
        </div>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="fc-overlay">
        <div className="fc-modal">
          <div className="fc-header">
            <h3 className="fc-topic-title">{topic.title}</h3>
            <button className="fc-close" onClick={onClose}>✕</button>
          </div>
          <div className="fc-empty">
            <p>No quiz questions available. AI generation requires a GROQ API key on the server.</p>
            <button className="btn secondary" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    );
  }

  if (showResults) {
    const s = score();
    return (
      <div className="fc-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
        <div className="fc-modal" style={{ maxWidth: 640 }}>
          <div className="fc-header">
            <h3 className="fc-topic-title">Quiz Results — {topic.title}</h3>
            <button className="fc-close" onClick={onClose}>✕</button>
          </div>
          <div style={{ textAlign: "center", padding: "24px 0" }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>{s.pct >= 70 ? "🎉" : s.pct >= 50 ? "📚" : "💪"}</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: s.pct >= 70 ? "var(--success)" : "var(--warning)" }}>
              {s.correct} / {s.total} correct ({s.pct}%)
            </div>
          </div>
          <div className="stack" style={{ gap: 10, maxHeight: 300, overflowY: "auto" }}>
            {questions.map((q, i) => {
              const userAns = answers[i];
              const correct = userAns === q.answer;
              return (
                <div key={i} className="card" style={{
                  padding: "12px 16px",
                  borderLeft: `3px solid ${correct ? "var(--success)" : "var(--danger)"}`,
                }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Q{i + 1}: {q.text}</div>
                  {!correct && userAns && (
                    <div className="subtle" style={{ fontSize: 12 }}>Your answer: {userAns}</div>
                  )}
                  {!correct && (
                    <div style={{ fontSize: 12, color: "var(--success)", marginTop: 2 }}>Correct: {q.answer}</div>
                  )}
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            <button className="btn secondary" style={{ flex: 1 }} onClick={() => { setShowResults(false); setIndex(0); setAnswers({}); }}>
              Retry
            </button>
            <button className="btn" style={{ flex: 1 }} onClick={onClose}>Done</button>
          </div>
        </div>
      </div>
    );
  }

  const q = questions[index];
  const isLast = index === questions.length - 1;

  return (
    <div className="fc-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="fc-modal" style={{ maxWidth: 640 }}>
        <div className="fc-header">
          <div>
            <div className="fc-topic-label">Quiz</div>
            <h3 className="fc-topic-title">{topic.title}</h3>
          </div>
          <button className="fc-close" onClick={onClose}>✕</button>
        </div>

        <div className="fc-progress-row">
          <span className="fc-counter">{index + 1} / {questions.length}</span>
          <div className="fc-progress-track">
            <div className="fc-progress-fill" style={{ width: `${((index + 1) / questions.length) * 100}%` }} />
          </div>
        </div>

        <div className="card" style={{ padding: "20px 24px", minHeight: 200 }}>
          <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>{q.text}</div>
          <div className="stack" style={{ gap: 8 }}>
            {q.options.map((opt, i) => {
              const selected = answers[index] === opt;
              return (
                <label
                  key={i}
                  style={{
                    display: "flex", alignItems: "center", padding: "10px 14px",
                    borderRadius: 8, cursor: "pointer",
                    backgroundColor: selected ? "rgba(93,136,255,0.15)" : "transparent",
                    border: selected ? "2px solid var(--primary)" : "1px solid rgba(255,255,255,0.1)",
                  }}
                  onClick={() => selectAnswer(opt)}
                >
                  <input type="radio" checked={selected} readOnly style={{ marginRight: 10 }} />
                  {opt}
                </label>
              );
            })}
          </div>
        </div>

        <div className="fc-actions">
          <button className="btn secondary fc-nav" onClick={() => setIndex(i => Math.max(i - 1, 0))} disabled={index === 0}>
            ← Back
          </button>
          {isLast ? (
            <button className="btn fc-flip-btn" onClick={() => setShowResults(true)}>
              Finish Quiz
            </button>
          ) : (
            <button className="btn fc-flip-btn" onClick={() => setIndex(i => i + 1)}>
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
