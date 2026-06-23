import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000/api/students";

function StatCard({ icon, value, label, color }) {
  return (
    <div className="card" style={{ textAlign: "center", padding: "18px 12px" }}>
      <div style={{ fontSize: 26 }}>{icon}</div>
      <div style={{ fontSize: 28, fontWeight: 800, margin: "4px 0", color: color || "inherit" }}>{value}</div>
      <div className="subtle" style={{ fontSize: 12 }}>{label}</div>
    </div>
  );
}

function ProgressBar({ pct, color }) {
  return (
    <div className="learn-progress-bar-track" style={{ marginTop: 6 }}>
      <div className="learn-progress-bar-fill" style={{ width: `${pct}%`, background: color || undefined }} />
    </div>
  );
}

export default function StudentDashboard({ onGoLearn, onGoExams }) {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/dashboard/student/`, { headers })
      .then(r => { setData(r.data); setError(null); })
      .catch(e => setError(e.response?.data?.error || "Dashboard konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="card"><p className="subtle">Dashboard wird geladen…</p></div>;
  if (error) return <div className="card" style={{ borderColor: "rgba(239,68,68,.35)" }}><p style={{ color: "#fecaca", margin: 0 }}>{error}</p></div>;
  if (!data) return null;

  const s = data.summary;
  const masteryColor = s.mastery_pct >= 70 ? "var(--success)" : s.mastery_pct >= 40 ? "var(--warning)" : "var(--danger)";

  return (
    <div className="stack-lg">
      <div className="card" style={{ padding: "20px 24px" }}>
        <div style={{ fontWeight: 700, fontSize: 18 }}>Hallo, {data.student.name || data.student.email} 👋</div>
        <p className="subtle" style={{ margin: "6px 0 0", fontSize: 14 }}>
          Dein persönlicher Lernfortschritt und Prüfungsvorbereitung auf einen Blick.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 14 }}>
        <StatCard icon="📚" value={s.plans_count} label="Lernpläne" />
        <StatCard icon="✅" value={`${s.topics_completed}/${s.topics_total}`} label="Topics erledigt" />
        <StatCard icon="🃏" value={`${s.mastery_pct}%`} label="Karteikarten gemeistert" color={masteryColor} />
        <StatCard icon="❓" value={s.quiz_questions} label="Quiz-Fragen" />
        <StatCard icon="📝" value={s.mock_exams} label="Mock Exams" />
        <StatCard icon="🎓" value={s.upcoming_exams} label="Anstehende Prüfungen" />
      </div>

      {s.flashcards_total > 0 && (
        <div className="card" style={{ padding: "18px 22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600 }}>Gesamt-Fortschritt Karteikarten</span>
            <span style={{ fontWeight: 800, color: masteryColor }}>{s.flashcards_known} / {s.flashcards_total}</span>
          </div>
          <ProgressBar pct={s.mastery_pct} color={masteryColor} />
        </div>
      )}

      {data.recommendations?.length > 0 && (
        <div className="card" style={{ padding: "18px 22px" }}>
          <div style={{ fontWeight: 700, marginBottom: 12 }}>💡 Empfehlungen</div>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            {data.recommendations.map((r, i) => <li key={i} className="subtle" style={{ fontSize: 14 }}>{r}</li>)}
          </ul>
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button className="btn" onClick={onGoLearn}>Zum Lernbereich</button>
            {s.upcoming_exams > 0 && (
              <button className="btn secondary" onClick={onGoExams}>Zu den Prüfungen</button>
            )}
          </div>
        </div>
      )}

      {data.knowledge_gaps?.length > 0 && (
        <div>
          <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700 }}>⚠️ Wissenslücken</h3>
          <div className="stack" style={{ gap: 10 }}>
            {data.knowledge_gaps.map((g, i) => (
              <div key={i} className="card" style={{ padding: "14px 18px", borderLeft: "3px solid var(--warning)" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{g.topic_title}</div>
                <div className="subtle" style={{ fontSize: 12, marginTop: 2 }}>{g.plan_title}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
                  <ProgressBar pct={g.mastery_pct} color="var(--warning)" />
                  <span style={{ fontSize: 13, fontWeight: 700, minWidth: 40 }}>{g.mastery_pct}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.plans?.length > 0 && (
        <div>
          <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700 }}>📁 Meine Lernpläne</h3>
          <div className="stack" style={{ gap: 10 }}>
            {data.plans.map(p => (
              <div key={p.plan_id} className="card" style={{ padding: "14px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{p.slide_title}</div>
                    <div className="subtle" style={{ fontSize: 12 }}>{p.topics_completed}/{p.topic_count} Topics · {p.flashcards_known}/{p.flashcards_total} Karten</div>
                  </div>
                  <div style={{ fontWeight: 800, color: "var(--primary)" }}>{p.progress_pct}%</div>
                </div>
                <ProgressBar pct={p.progress_pct} />
              </div>
            ))}
          </div>
        </div>
      )}

      {data.recent_mock_attempts?.length > 0 && (
        <div>
          <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700 }}>📊 Letzte Mock Exams</h3>
          <div className="stack" style={{ gap: 8 }}>
            {data.recent_mock_attempts.map((a, i) => (
              <div key={i} className="card" style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{a.title}</div>
                  <div className="subtle" style={{ fontSize: 12 }}>{new Date(a.completed_at).toLocaleDateString("de-DE")}</div>
                </div>
                <div style={{
                  fontWeight: 800, fontSize: 18,
                  color: a.score_pct >= 70 ? "var(--success)" : a.score_pct >= 50 ? "var(--warning)" : "var(--danger)",
                }}>
                  {a.score_pct}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.upcoming_exams?.length > 0 && (
        <div>
          <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700 }}>📅 Anstehende Prüfungen</h3>
          <div className="stack" style={{ gap: 8 }}>
            {data.upcoming_exams.map(e => (
              <div key={e.exam_id} className="card" style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{e.title}</div>
                  <div className="subtle" style={{ fontSize: 12 }}>{new Date(e.date).toLocaleString("de-DE")}</div>
                </div>
                <button className="btn secondary" style={{ fontSize: 13 }} onClick={onGoExams}>Vorbereiten</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {s.plans_count === 0 && (
        <div className="card" style={{ textAlign: "center", padding: "32px 20px" }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🚀</div>
          <p style={{ fontWeight: 600, margin: "0 0 8px" }}>Starte deine Lernreise</p>
          <p className="subtle" style={{ fontSize: 13, marginBottom: 16 }}>Lade deine Folien hoch und erhalte Karteikarten, Quizzes und Mock Exams.</p>
          <button className="btn" onClick={onGoLearn}>Folien hochladen</button>
        </div>
      )}
    </div>
  );
}
