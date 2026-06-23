import React, { useEffect, useState } from "react";

function MockExamPage({ mockExam, onExit }) {
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [showResults, setShowResults] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [examStarted, setExamStarted] = useState(false);

  useEffect(() => {
    if (mockExam?.questions) {
      const qs = mockExam.questions;
      setQuestions(qs);
      const initial = {};
      qs.forEach((_, idx) => { initial[idx] = null; });
      setAnswers(initial);
      setTimeRemaining((mockExam.duration_minutes || 30) * 60);
      setExamStarted(true);
    }
  }, [mockExam]);

  useEffect(() => {
    if (!examStarted || timeRemaining === null || showResults) return;
    if (timeRemaining <= 0) { setShowResults(true); return; }
    const timer = setInterval(() => setTimeRemaining(prev => prev <= 1 ? 0 : prev - 1), 1000);
    return () => clearInterval(timer);
  }, [examStarted, timeRemaining, showResults]);

  const calculateScore = () => {
    let correct = 0;
    questions.forEach((q, idx) => { if (answers[idx] === q.answer) correct++; });
    return { correct, total: questions.length, percentage: questions.length ? Math.round((correct / questions.length) * 100) : 0 };
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  if (!questions.length) {
    return (
      <div className="stack-lg">
        <div className="card muted-box">No questions in this mock exam.</div>
        <button className="btn secondary" onClick={onExit}>Back</button>
      </div>
    );
  }

  if (showResults) {
    const score = calculateScore();
    return (
      <div className="stack-lg">
        <div className="section-title">
          <span className="emoji">📊</span>
          <h2 style={{ margin: 0 }}>Mock Exam Results</h2>
        </div>
        <div className="card" style={{ textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>
            {score.percentage >= 70 ? "✅" : score.percentage >= 50 ? "⚠️" : "❌"}
          </div>
          <h3 style={{ margin: "0 0 8px", fontSize: 24 }}>
            {score.correct} of {score.total} correct
          </h3>
          <div style={{
            fontSize: 32, fontWeight: 700,
            color: score.percentage >= 70 ? "var(--success)" : score.percentage >= 50 ? "var(--warning)" : "var(--danger)",
          }}>
            {score.percentage}%
          </div>
        </div>
        <div className="stack">
          {questions.map((q, idx) => {
            const userAnswer = answers[idx];
            const isCorrect = userAnswer === q.answer;
            return (
              <div key={idx} className="card" style={{ borderLeft: `4px solid ${isCorrect ? "var(--success)" : "var(--danger)"}` }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Q{idx + 1}: {q.text}</div>
                {Array.isArray(q.options) && q.options.map((opt, i) => {
                  const isSelected = userAnswer === opt;
                  const isCorrectAnswer = opt === q.answer;
                  return (
                    <div key={i} style={{
                      padding: "6px 10px", marginBottom: 3, borderRadius: 6,
                      backgroundColor: isCorrectAnswer ? "rgba(34,197,94,0.15)" : isSelected ? "rgba(239,68,68,0.15)" : "transparent",
                    }}>
                      {opt}
                      {isCorrectAnswer && <span style={{ marginLeft: 8, color: "var(--success)" }}>✓</span>}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        <button className="btn secondary" onClick={onExit}>Back to Learning</button>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIndex];
  const durationSeconds = (mockExam.duration_minutes || 30) * 60;
  const timeColor = timeRemaining <= durationSeconds * 0.1 ? "var(--danger)" : timeRemaining <= durationSeconds * 0.25 ? "var(--warning)" : "var(--success)";

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">📝</span>
        <h2 style={{ margin: 0 }}>{mockExam.title}</h2>
      </div>
      <p className="subtle" style={{ marginTop: -8 }}>Practice mode — no identity verification required</p>

      {timeRemaining !== null && (
        <div className="card" style={{ textAlign: "center", padding: "12px 16px", border: `2px solid ${timeColor}` }}>
          <div style={{ fontSize: 12, opacity: 0.8 }}>Time Remaining</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: timeColor, fontFamily: "monospace" }}>
            {formatTime(timeRemaining)}
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="subtle">Question {currentQuestionIndex + 1} of {questions.length}</span>
        <span className="subtle">{Object.values(answers).filter(a => a).length} answered</span>
      </div>

      <div className="card" style={{ minHeight: 260, padding: "20px 24px" }}>
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 16 }}>{currentQuestion.text}</div>
        <div className="stack" style={{ gap: 8 }}>
          {currentQuestion.options?.map((option, i) => {
            const isSelected = answers[currentQuestionIndex] === option;
            return (
              <label key={i} style={{
                display: "flex", alignItems: "center", padding: "12px 16px", borderRadius: 8, cursor: "pointer",
                backgroundColor: isSelected ? "rgba(93,136,255,0.15)" : "transparent",
                border: isSelected ? "2px solid var(--primary)" : "1px solid rgba(255,255,255,0.1)",
              }} onClick={() => setAnswers(prev => ({ ...prev, [currentQuestionIndex]: option }))}>
                <input type="radio" checked={isSelected} readOnly style={{ marginRight: 12 }} />
                {option}
              </label>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
        <button className="btn secondary" onClick={() => setCurrentQuestionIndex(i => Math.max(i - 1, 0))} disabled={currentQuestionIndex === 0}>
          ← Back
        </button>
        {currentQuestionIndex === questions.length - 1 ? (
          <button className="btn" onClick={() => setShowResults(true)}>Finish Exam</button>
        ) : (
          <button className="btn" onClick={() => setCurrentQuestionIndex(i => i + 1)}>Next →</button>
        )}
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {questions.map((_, idx) => (
          <button key={idx} onClick={() => setCurrentQuestionIndex(idx)} style={{
            width: 36, height: 36, borderRadius: 8, border: "1px solid rgba(255,255,255,0.2)",
            backgroundColor: idx === currentQuestionIndex ? "var(--primary)" : answers[idx] ? "rgba(34,197,94,0.2)" : "transparent",
            color: "var(--text)", cursor: "pointer", fontSize: 13,
          }}>
            {idx + 1}
          </button>
        ))}
      </div>

      <button className="btn secondary" onClick={onExit}>Cancel</button>
    </div>
  );
}

export default MockExamPage;
