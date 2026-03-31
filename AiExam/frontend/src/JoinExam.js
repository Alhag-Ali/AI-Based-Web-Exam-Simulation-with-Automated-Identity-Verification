import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * Shows the list of available exams.
 * onSelectExam(exam) – called when the student clicks "Join" on an exam.
 */
function JoinExam({ onSelectExam }) {
  const [exams, setExams] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const token = localStorage.getItem("token");

  useEffect(() => {
    setLoadError(null);
    axios
      .get("http://127.0.0.1:8000/api/students/exams/", {
        headers: { Authorization: `Token ${token}` },
      })
      .then((res) => setExams(res.data))
      .catch((err) => {
        const msg =
          err?.response?.status === 401
            ? "Unauthorized – please sign in again."
            : "Error loading exams.";
        setLoadError(msg);
      });
  }, [token]);

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">📝</span>
        <h2 style={{ margin: 0 }}>Exams</h2>
      </div>

      {loadError && (
        <div className="card" style={{ borderColor: "rgba(239,68,68,.35)" }}>
          <p style={{ margin: 0, color: "#fecaca" }}>{loadError}</p>
        </div>
      )}

      {!loadError && exams.length === 0 && (
        <div className="card muted-box">
          <p style={{ margin: 0 }} className="subtle">No exams found.</p>
        </div>
      )}

      <ul className="list stack">
        {exams.map((exam) => (
          <li key={exam.id} className="list-item card">
            <div className="stack">
              <div style={{ fontWeight: 700 }}>{exam.title}</div>
              <div className="subtle">{exam.date}</div>
            </div>
            <button
              className="btn secondary"
              onClick={() => onSelectExam(exam)}
            >
              Join
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default JoinExam;
