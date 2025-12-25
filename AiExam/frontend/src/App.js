import React, { useState } from "react";
import Login from "./Login";
import JoinExam from "./JoinExam";
import ExamPage from "./ExamPage";
import "./App.css";

function App() {
  const token = localStorage.getItem("token");
  const [currentExam, setCurrentExam] = useState(null);

  if (!token) {
    return <div className="container"><Login /></div>;
  }

  if (currentExam) {
    return (
      <div>
        <TopBar />
        <div className="container">
          <ExamPage exam={currentExam} onExit={() => setCurrentExam(null)} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <TopBar />
      <div className="container">
        <JoinExam onJoined={(exam) => setCurrentExam(exam)} />
      </div>
    </div>
  );
}

export default App;

function TopBar() {
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
        <div className="row">
          <span className="badge">Student</span>
          <button className="btn secondary" onClick={logout}>Abmelden</button>
        </div>
      </div>
    </div>
  );
}
