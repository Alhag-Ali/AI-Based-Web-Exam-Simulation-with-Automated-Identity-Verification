import React, { useState, useEffect } from "react";
import Login from "./Login";
import JoinExam from "./JoinExam";
import ExamPage from "./ExamPage";
import CreateExam from "./CreateExam";
import axios from "axios";
import "./App.css";

function App() {
  const token = localStorage.getItem("token");
  const [currentExam, setCurrentExam] = useState(null);
  const [isStaff, setIsStaff] = useState(false);
  const [viewMode, setViewMode] = useState("student");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      const savedIsStaff = localStorage.getItem("isStaff");
      if (savedIsStaff === "true") {
        setIsStaff(true);
        setViewMode("staff");
      } else {
        setIsStaff(false);
        setViewMode("student");
      }

      axios
        .get("http://127.0.0.1:8000/api/students/exams/", {
          headers: { Authorization: `Token ${token}` },
        })
        .then(() => {
          setLoading(false);
        })
        .catch(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [token]);

  if (!token) {
    return (
      <div className="app-shell">
        <div className="bg-orb orb-a" />
        <div className="bg-orb orb-b" />
        <div className="bg-orb orb-c" />
        <div className="container">
          <Login />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="app-shell">
        <div className="bg-orb orb-a" />
        <div className="bg-orb orb-b" />
        <div className="bg-orb orb-c" />
        <div className="container">
          <div className="card">Lade...</div>
        </div>
      </div>
    );
  }

  if (currentExam) {
    return (
      <div className="app-shell">
        <div className="bg-orb orb-a" />
        <div className="bg-orb orb-b" />
        <div className="bg-orb orb-c" />
        <TopBar isStaff={isStaff} viewMode={viewMode} onViewModeChange={setViewMode} />
        <div className="container">
          <div className="hero card">
            <div className="hero-title">Pruefungsmodus</div>
            <div className="hero-subtle">Fokussiertes Layout mit Timer, Fragen und Fortschritt.</div>
          </div>
          <ExamPage exam={currentExam} onExit={() => setCurrentExam(null)} />
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="bg-orb orb-a" />
      <div className="bg-orb orb-b" />
      <div className="bg-orb orb-c" />
      <TopBar isStaff={isStaff} viewMode={viewMode} onViewModeChange={setViewMode} />
      <div className="container">
        <div className="hero card">
          <div className="hero-title">{viewMode === "staff" ? "Professor Dashboard" : "Student Dashboard"}</div>
          <div className="hero-subtle">
            {viewMode === "staff"
              ? "Erstelle Pruefungen, lade PDF-Folien hoch und verwalte Fragen zentral."
              : "Waehle eine Pruefung, verifiziere dich und starte direkt mit dem Exam."}
          </div>
        </div>
        {viewMode === "staff" ? (
          <CreateExam onCreated={(exam) => {
            alert(`Prüfung "${exam.title}" erfolgreich erstellt! Du kannst jetzt Fragen hochladen.`);
          }} />
        ) : (
          <JoinExam onJoined={(exam) => setCurrentExam(exam)} />
        )}
      </div>
    </div>
  );
}

export default App;

function TopBar({ isStaff, viewMode, onViewModeChange }) {
  const logout = () => {
    localStorage.removeItem("token");
    window.location.reload();
  };
  return (
    <div className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <div className="logo" />
          <div>AI Exam</div>
        </div>
        <div className="row" style={{ gap: 12, alignItems: "center" }}>
          {isStaff && (
            <div className="mode-switch">
              <button
                className={`mode-btn ${viewMode === "student" ? "active" : ""}`}
                onClick={() => onViewModeChange("student")}
              >
                Student
              </button>
              <button
                className={`mode-btn ${viewMode === "staff" ? "active" : ""}`}
                onClick={() => onViewModeChange("staff")}
              >
                Professor
              </button>
            </div>
          )}
          <span className="badge">{viewMode === "staff" ? "Professor" : "Student"}</span>
          <button className="btn secondary" onClick={logout}>Abmelden</button>
        </div>
      </div>
    </div>
  );
}
