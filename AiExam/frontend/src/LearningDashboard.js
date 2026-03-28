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
      setMsg({ type: "error", text: "Fehler beim Laden." });
    }
  };

  useEffect(() => { fetchPlans(); }, []);

  const handleFile = async (file) => {
    if (!file?.name?.toLowerCase().endsWith(".pdf")) {
      setMsg({ type: "error", text: "Nur PDF-Dateien werden akzeptiert." });
      return;
    }
    setMsg({ type: "info", text: "PDF wird analysiert…" });
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
      setMsg({ type: "info", text: `"${slide.title}" hochgeladen. Lernplan wird erstellt…` });
      const planRes = await axios.post(`${API}/learn/slides/${slide.id}/create-plan/`, {}, { headers });
      setCreatingPlan(false);
      setActivePlan(planRes.data);
      setMsg({ type: "success", text: `Fertig! ${planRes.data.topic_count} Themen erkannt.` });
      fetchPlans();
    } catch (err) {
      setUploading(false);
      setCreatingPlan(false);
      setMsg({ type: "error", text: err.response?.data?.error || "Fehler beim Verarbeiten." });
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
            <p className="learn-dropzone-label">{uploading ? "PDF wird analysiert…" : "Lernplan + Karteikarten werden erstellt…"}</p>
            <p className="learn-dropzone-hint">Das kann einige Sekunden dauern.</p>
          </div>
        ) : (
          <div className="learn-dropzone-inner">
            <div style={{ fontSize: 40, marginBottom: 8 }}>📄</div>
            <p className="learn-dropzone-label">
              PDF hierher ziehen oder <span className="learn-link">Datei auswählen</span>
            </p>
            <p className="learn-dropzone-hint">Vorlesungsfolien, Skripte oder Kapitel als PDF hochladen</p>
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
          <p className="subtle" style={{ margin: "0 0 8px", fontSize: 13 }}>Meine Lernpläne</p>
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
                  {activePlan.slide_title} · {activePlan.slide_pages} Seiten · {activePlan.topic_count} Themen
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
                {completedCount} abgeschlossen
              </span>
              <span className="learn-stat">
                <span className="learn-stat-dot" style={{ background: "rgba(255,255,255,0.25)" }} />
                {activePlan.topics.filter(t => t.status === "open").length} offen
              </span>
            </div>
          </div>

          <div>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, opacity: 0.8 }}>
              🃏 Themen &amp; Karteikarten
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
                      🃏 Karteikarten lernen
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
          <p style={{ fontWeight: 600, margin: "0 0 6px" }}>Noch keine Folien hochgeladen</p>
          <p className="subtle" style={{ fontSize: 13 }}>
            Lade oben eine PDF-Datei hoch — das System erstellt automatisch Themen und Karteikarten.
          </p>
        </div>
      )}

    </div>
  );
}
