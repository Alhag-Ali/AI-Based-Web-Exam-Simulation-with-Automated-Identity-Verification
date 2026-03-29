import React, { useState, useEffect } from "react";
import Login from "./Login";
import JoinExam from "./JoinExam";
import ExamPage from "./ExamPage";
import CreateExam from "./CreateExam";
import LearningDashboard from "./LearningDashboard";
import ProfessorDashboard from "./ProfessorDashboard";
import axios from "axios";
import "./App.css";

function App() {
  const token = localStorage.getItem("token");
  const [currentExam, setCurrentExam] = useState(null);
  const [isStaff, setIsStaff] = useState(false);
  const [studentTab, setStudentTab] = useState("exams");
  const [profTab, setProfTab] = useState("dashboard");
  const [loading, setLoading] = useState(true);

  const viewMode = isStaff ? "staff" : "student";

  useEffect(() => {
    if (token) {
      const savedIsStaff = localStorage.getItem("isStaff");
      setIsStaff(savedIsStaff === "true");

      axios
        .get("http://127.0.0.1:8000/api/students/exams/", {
          headers: { Authorization: `Token ${token}` },
        })
        .then(() => setLoading(false))
        .catch(() => setLoading(false));
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
          <div className="card">Loading...</div>
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
        <TopBar isStaff={isStaff} viewMode={viewMode} />
        <div className="container">
          <div className="hero card">
            <div className="hero-title">Exam Mode</div>
            <div className="hero-subtle">Focused layout with timer, questions and progress.</div>
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
      <TopBar
        isStaff={isStaff} viewMode={viewMode}
        studentTab={studentTab} onStudentTabChange={setStudentTab}
        profTab={profTab} onProfTabChange={setProfTab}
      />
      <div className="container">
        <div className="hero card">
          <div className="hero-title">
            {viewMode === "staff"
              ? (profTab === "dashboard" ? "Professor Dashboard" : "Create New Exam")
              : studentTab === "learn" ? "Learning Area" : "Student Dashboard"}
          </div>
          <div className="hero-subtle">
            {viewMode === "staff"
              ? (profTab === "dashboard"
                  ? "Overview of all exams, participants and statistics."
                  : "Create an exam and generate questions with AI-RAG.")
              : studentTab === "learn"
              ? "Upload lecture slides — get a study plan and flashcards."
              : "Select an exam, verify your identity and start immediately."}
          </div>
        </div>

        {viewMode === "staff" ? (
          profTab === "dashboard" ? (
            <ProfessorDashboard onCreateExam={() => setProfTab("create")} />
          ) : (
            <CreateExam onCreated={() => setProfTab("dashboard")} />
          )
        ) : studentTab === "learn" ? (
          <LearningDashboard />
        ) : (
          <JoinExam onJoined={(exam) => setCurrentExam(exam)} />
        )}
      </div>
    </div>
  );
}

export default App;

function TopBar({ isStaff, viewMode, studentTab, onStudentTabChange, profTab, onProfTabChange }) {
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
          {viewMode === "student" && (
            <div className="mode-switch">
              <button className={`mode-btn ${studentTab === "exams" ? "active" : ""}`} onClick={() => onStudentTabChange("exams")}>
                Exams
              </button>
              <button className={`mode-btn ${studentTab === "learn" ? "active" : ""}`} onClick={() => onStudentTabChange("learn")}>
                Learn
              </button>
            </div>
          )}
          {viewMode === "staff" && (
            <div className="mode-switch">
              <button className={`mode-btn ${profTab === "dashboard" ? "active" : ""}`} onClick={() => onProfTabChange("dashboard")}>
                📊 Dashboard
              </button>
              <button className={`mode-btn ${profTab === "create" ? "active" : ""}`} onClick={() => onProfTabChange("create")}>
                ➕ New Exam
              </button>
            </div>
          )}
          <span className="badge">{isStaff ? "Professor" : "Student"}</span>
          <button className="btn secondary" onClick={logout}>Sign Out</button>
        </div>
      </div>
    </div>
  );
}
