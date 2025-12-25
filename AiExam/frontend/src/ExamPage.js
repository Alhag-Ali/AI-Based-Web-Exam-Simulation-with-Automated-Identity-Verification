import React, { useEffect, useState } from "react";
import axios from "axios";

function ExamPage({ exam, onExit }) {
  const [questions, setQuestions] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [showResults, setShowResults] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [examStarted, setExamStarted] = useState(false);
  const token = localStorage.getItem("token");

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/api/students/exams/${exam.id}/questions/`, {
          headers: { Authorization: `Token ${token}` }
        });
        setQuestions(res.data.questions || res.data || []);
        const initialAnswers = {};
        (res.data.questions || res.data || []).forEach((q, idx) => {
          initialAnswers[idx] = null;
        });
        setAnswers(initialAnswers);
        
        const durationMinutes = exam.duration_minutes || 60;
        const durationSeconds = durationMinutes * 60;
        setTimeRemaining(durationSeconds);
        setExamStarted(true);
      } catch (err) {
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
  }, [exam?.id, token, exam.duration_minutes]);

  useEffect(() => {
    if (!examStarted || timeRemaining === null || showResults) return;

    if (timeRemaining <= 0) {
      handleFinish();
      return;
    }

    const timer = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 1) {
          handleFinish();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [examStarted, timeRemaining, showResults]);

  const handleAnswerSelect = (questionIndex, selectedAnswer) => {
    setAnswers(prev => ({
      ...prev,
      [questionIndex]: selectedAnswer
    }));
  };

  const handleNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  const handleFinish = () => {
    setShowResults(true);
  };

  const calculateScore = () => {
    if (!questions || questions.length === 0) return { correct: 0, total: 0, percentage: 0 };
    
    let correct = 0;
    questions.forEach((q, idx) => {
      if (answers[idx] === q.answer) {
        correct++;
      }
    });
    
    return {
      correct,
      total: questions.length,
      percentage: Math.round((correct / questions.length) * 100)
    };
  };

  if (questions === null) {
    return (
      <div className="stack-lg">
        <div className="card"><p style={{ margin: 0 }}>Lade Fragen …</p></div>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="stack-lg">
        <div className="card muted-box">
          Für diese Prüfung sind noch keine Fragen verfügbar.
        </div>
        <button className="btn secondary" onClick={onExit}>Zurück zu den Prüfungen</button>
      </div>
    );
  }

  if (showResults) {
    const score = calculateScore();
    return (
      <div className="stack-lg">
        <div className="section-title">
          <span className="emoji">📊</span>
          <h2 style={{ margin: 0 }}>Ergebnis</h2>
        </div>
        
        <div className="card" style={{ textAlign: "center", padding: "32px" }}>
          <div style={{ fontSize: "48px", marginBottom: "16px" }}>
            {score.percentage >= 70 ? "✅" : score.percentage >= 50 ? "⚠️" : "❌"}
          </div>
          <h3 style={{ margin: "0 0 8px 0", fontSize: "24px" }}>
            {score.correct} von {score.total} Fragen richtig
          </h3>
          <div style={{ fontSize: "32px", fontWeight: 700, color: score.percentage >= 70 ? "var(--success)" : score.percentage >= 50 ? "var(--warning)" : "var(--danger)" }}>
            {score.percentage}%
          </div>
        </div>

        <div className="stack">
          <h3 style={{ margin: "16px 0 8px 0" }}>Detaillierte Auswertung:</h3>
          {questions.map((q, idx) => {
            const userAnswer = answers[idx];
            const isCorrect = userAnswer === q.answer;
            return (
              <div key={idx} className="card" style={{ borderLeft: `4px solid ${isCorrect ? "var(--success)" : "var(--danger)"}` }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>
                  Frage {idx + 1}: {q.text || q.question}
                </div>
                {Array.isArray(q.options) && q.options.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {q.options.map((opt, i) => {
                      const isSelected = userAnswer === opt;
                      const isCorrectAnswer = opt === q.answer;
                      return (
                        <div
                          key={i}
                          style={{
                            padding: "8px 12px",
                            marginBottom: 4,
                            borderRadius: 6,
                            backgroundColor: isCorrectAnswer ? "rgba(34, 197, 94, 0.15)" : isSelected && !isCorrect ? "rgba(239, 68, 68, 0.15)" : "transparent",
                            border: isCorrectAnswer ? "1px solid var(--success)" : isSelected && !isCorrect ? "1px solid var(--danger)" : "1px solid transparent"
                          }}
                        >
                          {opt}
                          {isCorrectAnswer && <span style={{ marginLeft: 8, color: "var(--success)" }}>✓ Richtig</span>}
                          {isSelected && !isCorrect && <span style={{ marginLeft: 8, color: "var(--danger)" }}>✗ Deine Antwort</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
                {!isCorrect && userAnswer && (
                  <div style={{ marginTop: 8, color: "var(--danger)" }}>
                    Deine Antwort: {userAnswer}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
          <button className="btn secondary" onClick={onExit} style={{ flex: 1 }}>
            Zurück zu den Prüfungen
          </button>
        </div>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIndex];
  const isLastQuestion = currentQuestionIndex === questions.length - 1;
  const isFirstQuestion = currentQuestionIndex === 0;
  const hasAnswer = answers[currentQuestionIndex] !== null;

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getTimeColor = () => {
    if (timeRemaining === null) return "var(--text)";
    const durationSeconds = (exam.duration_minutes || 60) * 60;
    const percentage = (timeRemaining / durationSeconds) * 100;
    if (percentage <= 10) return "var(--danger)";
    if (percentage <= 25) return "var(--warning)";
    return "var(--success)";
  };

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">📝</span>
        <h2 style={{ margin: 0 }}>{exam.title}</h2>
      </div>
      <p className="subtle" style={{ marginTop: -8 }}>{exam.description}</p>

      {timeRemaining !== null && (
        <div className="card" style={{
          backgroundColor: timeRemaining <= 60 ? "rgba(239, 68, 68, 0.15)" : "rgba(79, 124, 255, 0.15)",
          border: `2px solid ${getTimeColor()}`,
          textAlign: "center",
          padding: "12px 16px",
          marginBottom: 16
        }}>
          <div style={{ fontSize: "12px", marginBottom: 4, opacity: 0.8 }}>Verbleibende Zeit</div>
          <div style={{ fontSize: "32px", fontWeight: 700, color: getTimeColor(), fontFamily: "monospace" }}>
            {formatTime(timeRemaining)}
          </div>
          {timeRemaining <= 60 && (
            <div style={{ fontSize: "12px", marginTop: 4, color: "var(--danger)" }}>
              ⚠️ Weniger als eine Minute verbleibend!
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div className="subtle">
          Frage {currentQuestionIndex + 1} von {questions.length}
        </div>
        <div className="subtle">
          {Object.values(answers).filter(a => a !== null).length} von {questions.length} beantwortet
        </div>
      </div>

      <div className="card" style={{ minHeight: "300px" }}>
        <div style={{ fontWeight: 700, fontSize: "18px", marginBottom: 16 }}>
          {currentQuestion.text || currentQuestion.question || `Frage ${currentQuestionIndex + 1}`}
        </div>
        
        {Array.isArray(currentQuestion.options) && currentQuestion.options.length > 0 ? (
          <div className="stack" style={{ gap: 8 }}>
            {currentQuestion.options.map((option, i) => {
              const isSelected = answers[currentQuestionIndex] === option;
              return (
                <label
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "12px 16px",
                    borderRadius: 8,
                    cursor: "pointer",
                    backgroundColor: isSelected ? "rgba(79, 124, 255, 0.15)" : "transparent",
                    border: isSelected ? "2px solid var(--primary)" : "1px solid rgba(255,255,255,0.1)",
                    transition: "all 0.2s"
                  }}
                  onClick={() => handleAnswerSelect(currentQuestionIndex, option)}
                >
                  <input
                    type="radio"
                    name={`question-${currentQuestionIndex}`}
                    value={option}
                    checked={isSelected}
                    onChange={() => handleAnswerSelect(currentQuestionIndex, option)}
                    style={{ marginRight: 12, cursor: "pointer" }}
                  />
                  <span>{option}</span>
                </label>
              );
            })}
          </div>
        ) : (
          <div className="subtle">Keine Optionen verfügbar</div>
        )}
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
        <button
          className="btn secondary"
          onClick={handlePrevious}
          disabled={isFirstQuestion}
          style={{ opacity: isFirstQuestion ? 0.5 : 1, cursor: isFirstQuestion ? "not-allowed" : "pointer" }}
        >
          ← Zurück
        </button>
        
        {isLastQuestion ? (
          <button
            className="btn"
            onClick={handleFinish}
            disabled={!hasAnswer}
            style={{ opacity: !hasAnswer ? 0.5 : 1, cursor: !hasAnswer ? "not-allowed" : "pointer" }}
          >
            Prüfung abschließen
          </button>
        ) : (
          <button
            className="btn"
            onClick={handleNext}
            style={{ marginLeft: "auto" }}
          >
            Nächste →
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
        {questions.map((_, idx) => (
          <button
            key={idx}
            onClick={() => setCurrentQuestionIndex(idx)}
            style={{
              width: "40px",
              height: "40px",
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.2)",
              backgroundColor: idx === currentQuestionIndex ? "var(--primary)" : answers[idx] !== null ? "rgba(34, 197, 94, 0.2)" : "transparent",
              color: "var(--text)",
              cursor: "pointer",
              fontSize: "14px",
              fontWeight: idx === currentQuestionIndex ? 700 : 400
            }}
          >
            {idx + 1}
          </button>
        ))}
      </div>

      <button className="btn secondary" onClick={onExit} style={{ marginTop: 16 }}>
        Prüfung abbrechen
      </button>
    </div>
  );
}

export default ExamPage;


