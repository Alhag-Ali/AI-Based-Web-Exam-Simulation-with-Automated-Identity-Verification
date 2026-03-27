import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import FlashcardViewer from "./FlashcardViewer";

const API = "http://127.0.0.1:8000/api/students";

function LearningDashboard() {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };

  const [slides, setSlides] = useState([]);
  const [plans, setPlans] = useState([]);
  const [activePlan, setActivePlan] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [uploadMsg, setUploadMsg] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef();

  const fetchData = async () => {
    try {
      const [slidesRes, plansRes] = await Promise.all([
        axios.get(`${API}/learn/slides/`, { headers }),
        axios.get(`${API}/learn/plans/`, { headers }),
      ]);
      setSlides(slidesRes.data);
      setPlans(plansRes.data);
      if (plansRes.data.length > 0 && !activePlan) {
        setActivePlan(plansRes.data[0]);
      }
    } catch {
      setUploadMsg({ type: "error", text: "Fehler beim Laden der Daten." });
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleFile = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
      setUploadMsg({ type: "error", text: "Nur PDF-Dateien werden akzeptiert." });
      return;
    }
    setUploading(true);
    setUploadMsg({ type: "info", text: "Datei wird hochgeladen und analysiert…" });

    const form = new FormData();
    form.append("pdf_file", file);
    try {
      const res = await axios.post(`${API}/learn/upload/`, form, {
        headers: { ...headers, "Content-Type": "multipart/form-data" },
      });
      const slide = res.data;
      setUploadMsg({ type: "success", text: `"${slide.title}" hochgeladen (${slide.page_count} Seiten). Lernplan wird erstellt…` });
      setUploading(false);
      setGeneratingPlan(true);
      const planRes = await axios.post(`${API}/learn/slides/${slide.id}/create-plan/`, {}, { headers });
      setGeneratingPlan(false);
      setActivePlan(planRes.data);
      setUploadMsg({ type: "success", text: `Lernplan mit ${planRes.data.topic_count} Themen erstellt.` });
      fetchData();
    } catch (err) {
      setUploading(false);
      setGeneratingPlan(false);
      setUploadMsg({ type: "error", text: err.response?.data?.error || "Fehler beim Verarbeiten der PDF." });
    }
  };

  const onFileInput = (e) => handleFile(e.target.files[0]);
  const onDrop = (e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); };
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);

  const [flashcardTopic, setFlashcardTopic] = useState(null);

  const topicStatusColor = (s) => s === "completed" ? "var(--success)" : s === "in_progress" ? "var(--warning)" : "rgba(255,255,255,0.2)";
  const topicStatusLabel = (s) => s === "completed" ? "Abgeschlossen" : s === "in_progress" ? "In Bearbeitung" : "Offen";

  const completedCount = activePlan ? activePlan.topics.filter(t => t.status === "completed").length : 0;
  const progress = activePlan && activePlan.topic_count > 0
    ? Math.round((completedCount / activePlan.topic_count) * 100)
    : 0;

  return (
    <div className="stack-lg">

      {flashcardTopic && (
        <FlashcardViewer topic={flashcardTopic} onClose={() => setFlashcardTopic(null)} />
      )}

      <div className="learn-hero">
        <div className="learn-hero-icon">🎓</div>
        <div>
          <h2 className="learn-hero-title">Lernbereich</h2>
          <p className="learn-hero-sub">Lade deine Vorlesungsfolien hoch — das System analysiert den Inhalt und erstellt automatisch einen persönlichen Lernplan mit Themen und Prüfungen.</p>
        </div>
      </div>

      <div
        className={`learn-dropzone${dragOver ? " dragover" : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => fileInputRef.current?.click()}
      >
        <input ref={fileInputRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={onFileInput} />
        {uploading || generatingPlan ? (
          <div className="learn-dropzone-inner">
            <div className="learn-spinner" />
            <p>{uploading ? "PDF wird analysiert…" : "Lernplan wird erstellt…"}</p>
          </div>
        ) : (
          <div className="learn-dropzone-inner">
            <div className="learn-upload-icon">📄</div>
            <p className="learn-dropzone-label">PDF hierher ziehen oder <span className="learn-link">Datei auswählen</span></p>
            <p className="learn-dropzone-hint">Vorlesungsfolien, Skripte, Kapitel — als PDF</p>
          </div>
        )}
      </div>

      {uploadMsg && (
        <div className={`learn-msg learn-msg-${uploadMsg.type}`}>
          {uploadMsg.type === "success" && "✅ "}
          {uploadMsg.type === "error" && "❌ "}
          {uploadMsg.type === "info" && "⏳ "}
          {uploadMsg.text}
        </div>
      )}

      {plans.length > 1 && (
        <div className="learn-plan-selector">
          <p className="subtle" style={{ margin: 0, fontSize: 13 }}>Lernpläne</p>
          <div className="learn-plan-tabs">
            {plans.map(p => (
              <button
                key={p.plan_id}
                className={`learn-plan-tab${activePlan?.plan_id === p.plan_id ? " active" : ""}`}
                onClick={() => setActivePlan(p)}
              >
                {p.slide_title}
              </button>
            ))}
          </div>
        </div>
      )}

      {activePlan && (
        <div className="stack-lg">

          <div className="learn-progress-card card">
            <div className="learn-progress-header">
              <div>
                <div className="learn-progress-title">{activePlan.plan_title}</div>
                <div className="subtle" style={{ fontSize: 13, marginTop: 4 }}>
                  {activePlan.slide_title} · {activePlan.slide_pages} Seiten · {activePlan.topic_count} Themen
                </div>
              </div>
              <div className="learn-progress-badge">{progress}%</div>
            </div>
            <div className="learn-progress-bar-track">
              <div className="learn-progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="learn-progress-stats">
              <span className="learn-stat"><span className="learn-stat-dot" style={{ background: "var(--success)" }} />{completedCount} abgeschlossen</span>
              <span className="learn-stat"><span className="learn-stat-dot" style={{ background: "var(--warning)" }} />{activePlan.topics.filter(t => t.status === "in_progress").length} in Bearbeitung</span>
              <span className="learn-stat"><span className="learn-stat-dot" style={{ background: "rgba(255,255,255,0.25)" }} />{activePlan.topics.filter(t => t.status === "open").length} offen</span>
            </div>
          </div>

          <div>
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700 }}>Themen ({activePlan.topic_count})</h3>
            <div className="learn-topics-grid">
              {activePlan.topics.map((topic, i) => (
                <div key={topic.id} className="learn-topic-card card">
                  <div className="learn-topic-header">
                    <div className="learn-topic-index">{i + 1}</div>
                    <div className="learn-topic-status-dot" style={{ background: topicStatusColor(topic.status) }} title={topicStatusLabel(topic.status)} />
                  </div>
                  <div className="learn-topic-title">{topic.title}</div>
                  {topic.summary && (
                    <p className="learn-topic-summary subtle">{topic.summary.length > 180 ? topic.summary.slice(0, 180) + "…" : topic.summary}</p>
                  )}
                  {Array.isArray(topic.key_concepts) && topic.key_concepts.length > 0 && (
                    <div className="learn-concepts">
                      {topic.key_concepts.slice(0, 5).map((c, ci) => (
                        <span key={ci} className="learn-concept-tag">{c}</span>
                      ))}
                    </div>
                  )}
                  <div className="learn-topic-footer">
                    <span className="learn-topic-status-label" style={{ color: topicStatusColor(topic.status) }}>
                      {topicStatusLabel(topic.status)}
                    </span>
                    <button
                      className="btn secondary"
                      style={{ fontSize: 12, padding: "5px 12px", marginTop: 8 }}
                      onClick={() => setFlashcardTopic(topic)}
                    >
                      🃏 Karteikarten
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}

      {plans.length === 0 && !uploading && !generatingPlan && (
        <div className="card muted-box" style={{ textAlign: "center", padding: "40px 24px" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📚</div>
          <p className="subtle">Noch kein Lernplan vorhanden. Lade deine ersten Vorlesungsfolien hoch.</p>
        </div>
      )}

    </div>
  );
}

export default LearningDashboard;
