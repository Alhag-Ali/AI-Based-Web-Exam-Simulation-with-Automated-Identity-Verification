import React, { useEffect, useState } from "react";
import axios from "axios";

function ExamPage({ exam, onExit }) {
  const [questions, setQuestions] = useState(null);
  const token = localStorage.getItem("token");

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/api/students/exams/${exam.id}/questions/`, {
          headers: { Authorization: `Token ${token}` }
        });
        // Backend returns { questions: [...] }
        setQuestions(res.data.questions || res.data || []);
      } catch (err) {
        console.error("Error loading questions:", err);
        if (err.response?.status === 403) {
          setQuestions([]);
          alert("Bitte trete zuerst der Prüfung bei!");
        } else {
          setQuestions([]);
        }
      }
    };
    if (exam?.id) {
      fetchQuestions();
    }
  }, [exam?.id, token]);

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">📝</span>
        <h2 style={{ margin: 0 }}>{exam.title}</h2>
      </div>
      <p className="subtle" style={{ marginTop: -8 }}>{exam.description}</p>

      {questions === null && <div className="card"><p style={{ margin: 0 }}>Lade Fragen …</p></div>}

      {Array.isArray(questions) && questions.length === 0 && (
        <div className="card muted-box">
          Für diese Prüfung ist noch kein Fragen-Endpunkt implementiert.
          Wir zeigen hier die Oberfläche; die Anbindung kann später ergänzt werden.
        </div>
      )}

      {Array.isArray(questions) && questions.length > 0 && (
        <ol className="stack">
          {questions.map((q, idx) => (
            <li key={idx} className="card">
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{q.text || q.question || `Frage ${idx + 1}`}</div>
              {Array.isArray(q.options) && q.options.length > 0 && (
                <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                  {q.options.map((opt, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>{opt}</li>
                  ))}
                </ul>
              )}
              {q.answer && (
                <div className="subtle" style={{ marginTop: 8, fontStyle: "italic" }}>
                  Antwort: {q.answer}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      <button className="btn secondary" onClick={onExit} style={{ marginTop: 4 }}>Zurück zu den Prüfungen</button>
    </div>
  );
}

export default ExamPage;


