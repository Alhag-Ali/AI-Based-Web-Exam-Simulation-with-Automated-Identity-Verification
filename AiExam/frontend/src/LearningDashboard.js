import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import FlashcardViewer from "./FlashcardViewer";

const API = "http://127.0.0.1:8000/api/students";

export default function LearningDashboard() {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };

  const [plans, setPlans]               = useState([]);
  const [activePlan, setActivePlan]     = useState(null);
  const [flashcardTopic, setFlashcardTopic] = useState(null);

  const [uploading, setUploading]       = useState(false);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [msg, setMsg]                   = useState(null);
  const [dragOver, setDragOver]         = useState(false);
  const fileRef = useRef();

  const fetchPlans = async () => {
    try {
      const res = await axios.get(`${API}/learn/plans/`, { headers });
      setPlans(res.data);
      if (res.data.length > 0 && !activePlan) setActivePlan(res.data[0]);
    } catch {
      setMsg({ type: "error", text: "Error loading." });
    }
  };

  useEffect(() => { fetchPlans(); }, []);

  const handleFile = async (file) => {
    if (!file?.name?.toLowerCase().endsWith(".pdf")) {
      setMsg({ type: "error", text: "Only PDF files are accepted." });
      return;
    }
    setMsg({ type: "info", text: "Analysing PDF…" });
    setUploading(true);
    const form = new FormData();
    form.append("pdf_file", file);
    try {
      const uploadRes = await axios.post(`${API}/learn/upload/`, form, {
        headers: { ...headers, "Content-Type": "multipart/form-data" },
      });
      const slide = uploadRes.data;
      setUploading(false);
      setCreatingPlan(true);
      setMsg({ type: "info", text: `"${slide.title}" uploaded. Creating study plan…` });
      const planRes = await axios.post(`${API}/learn/slides/${slide.id}/create-plan/`, {}, { headers });
      setCreatingPlan(false);
      setActivePlan(planRes.data);
      setMsg({ type: "success", text: `Done! ${planRes.data.topic_count} topics detected.` });
      fetchPlans();
    } catch (err) {
      setUploading(false);
      setCreatingPlan(false);
      setMsg({ type: "error", text: err.response?.data?.error || "Error processing file." });
    }
  };

  const onDrop = (e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); };
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };

  const completedCount = activePlan ? activePlan.topics.filter(t => t.status === "completed").length : 0;
  const progress = activePlan?.topic_count > 0 ? Math.round((completedCount / activePlan.topic_count) * 100) : 0;

  const busy = uploading || creatingPlan;

  return (
    <div className="stack-lg">

      {flashcardTopic && (
        <FlashcardViewer topic={flashcardTopic} onClose={() => setFlashcardTopic(null)} />
      )}

      <div
        className={`learn-dropzone${dragOver ? " dragover" : ""}${busy ? " busy" : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setDragOver(false)}
        onClick={() => !busy && fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={(e) => handleFile(e.target.files[0])} />
        {busy ? (
          <div className="learn-dropzone-inner">
            <div className="learn-spinner" />
            <p className="learn-dropzone-label">{uploading ? "Analysing PDF…" : "Creating study plan + flashcards…"}</p>
            <p className="learn-dropzone-hint">This may take a few seconds.</p>
          </div>
        ) : (
          <div className="learn-dropzone-inner">
            <div style={{ fontSize: 40, marginBottom: 8 }}>📄</div>
            <p className="learn-dropzone-label">
              Drag PDF here or <span className="learn-link">select file</span>
            </p>
            <p className="learn-dropzone-hint">Upload lecture slides, scripts or chapters as PDF</p>
          </div>
        )}
      </div>

      {msg && (
        <div className={`learn-msg learn-msg-${msg.type}`}>
          {msg.type === "success" && "✅ "}
          {msg.type === "error"   && "❌ "}
          {msg.type === "info"    && "⏳ "}
          {msg.text}
        </div>
      )}

      {plans.length > 1 && (
        <div className="learn-plan-selector">
          <p className="subtle" style={{ margin: "0 0 8px", fontSize: 13 }}>My Study Plans</p>
          <div className="learn-plan-tabs">
            {plans.map(p => (
              <button
                key={p.plan_id}
                className={`learn-plan-tab${activePlan?.plan_id === p.plan_id ? " active" : ""}`}
                onClick={() => setActivePlan(p)}
              >
                📁 {p.slide_title}
              </button>
            ))}
          </div>
        </div>
      )}

      {activePlan && (
        <div className="stack-lg">

          <div className="card" style={{ padding: "20px 24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>{activePlan.plan_title}</div>
                <div className="subtle" style={{ fontSize: 13, marginTop: 3 }}>
                  {activePlan.slide_title} · {activePlan.slide_pages} pages · {activePlan.topic_count} topics
                </div>
              </div>
              <div style={{
                fontSize: 22, fontWeight: 800,
                color: progress === 100 ? "var(--success)" : "var(--primary)",
                minWidth: 52, textAlign: "right"
              }}>
                {progress}%
              </div>
            </div>
            <div className="learn-progress-bar-track">
              <div className="learn-progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="learn-progress-stats" style={{ marginTop: 10 }}>
              <span className="learn-stat">
                <span className="learn-stat-dot" style={{ background: "var(--success)" }} />
                {completedCount} completed
              </span>
              <span className="learn-stat">
                <span className="learn-stat-dot" style={{ background: "rgba(255,255,255,0.25)" }} />
                {activePlan.topics.filter(t => t.status === "open").length} open
              </span>
            </div>
          </div>

          <div>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, opacity: 0.8 }}>
              🃏 Topics &amp; Flashcards
            </h3>
            <div className="learn-topics-grid">
              {activePlan.topics.map((topic, i) => {
                const done = topic.status === "completed";
                return (
                  <div
                    key={topic.id}
                    className="learn-topic-card card"
                    style={{ cursor: "pointer", border: done ? "1px solid var(--success)" : undefined }}
                    onClick={() => setFlashcardTopic(topic)}
                  >
                    <div className="learn-topic-header">
                      <div className="learn-topic-index">{i + 1}</div>
                      {done && <span style={{ fontSize: 16 }}>✅</span>}
                    </div>

                    <div className="learn-topic-title">{topic.title}</div>

                    {topic.summary && (
                      <p className="learn-topic-summary subtle">
                        {topic.summary.length > 140 ? topic.summary.slice(0, 140) + "…" : topic.summary}
                      </p>
                    )}

                    {Array.isArray(topic.key_concepts) && topic.key_concepts.length > 0 && (
                      <div className="learn-concepts">
                        {topic.key_concepts.slice(0, 4).map((c, ci) => (
                          <span key={ci} className="learn-concept-tag">{c}</span>
                        ))}
                      </div>
                    )}

                    <button
                      className="btn"
                      style={{ marginTop: 12, width: "100%", fontSize: 13 }}
                      onClick={(e) => { e.stopPropagation(); setFlashcardTopic(topic); }}
                    >
                      🃏 Study Flashcards
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      )}

      {plans.length === 0 && !busy && (
        <div className="card" style={{ textAlign: "center", padding: "48px 24px", opacity: 0.7 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📚</div>
          <p style={{ fontWeight: 600, margin: "0 0 6px" }}>No slides uploaded yet</p>
          <p className="subtle" style={{ fontSize: 13 }}>
            Upload a PDF file above — the system automatically creates topics and flashcards.
          </p>
        </div>
      )}

    </div>
  );
}
