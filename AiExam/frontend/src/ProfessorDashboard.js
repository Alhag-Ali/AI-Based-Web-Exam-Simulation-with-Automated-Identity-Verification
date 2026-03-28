import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000/api/students";

function ProfessorDashboard({ onCreateExam }) {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [enrollTab, setEnrollTab] = useState({}); // examId -> "list" | "add"
  const [enrollData, setEnrollData] = useState({}); // examId -> [{matriculation_number, note, added_at}]
  const [enrollLoading, setEnrollLoading] = useState({});
  const [addInput, setAddInput] = useState({}); // examId -> text (bulk, comma/newline)
  const [addNote, setAddNote] = useState({});
  const [addMsg, setAddMsg] = useState({});
  const [editRow, setEditRow] = useState(null); // { examId, matrikel, newMatrikel, newNote }

  const load = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/professor/dashboard/`, { headers })
      .then(r => { setData(r.data); setError(null); })
      .catch(e => setError(e.response?.data?.error || "Fehler beim Laden."))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const loadEnrollments = useCallback((examId) => {
    setEnrollLoading(p => ({ ...p, [examId]: true }));
    axios.get(`${API}/exams/${examId}/enrollments/`, { headers })
      .then(r => setEnrollData(p => ({ ...p, [examId]: r.data.enrollments })))
      .catch(() => {})
      .finally(() => setEnrollLoading(p => ({ ...p, [examId]: false })));
  }, []); // eslint-disable-line

  const toggleExpand = (id) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    setEnrollTab(p => ({ ...p, [id]: p[id] || "list" }));
    loadEnrollments(id);
  };

  const handleAddEnrollments = async (examId) => {
    const raw = (addInput[examId] || "").trim();
    if (!raw) return;
    const numbers = raw.split(/[\n,;]+/).map(s => s.trim()).filter(Boolean);
    if (!numbers.length) return;
    setAddMsg(p => ({ ...p, [examId]: "Wird gespeichert..." }));
    try {
      const r = await axios.post(
        `${API}/exams/${examId}/enrollments/`,
        { matriculation_numbers: numbers, note: addNote[examId] || "" },
        { headers }
      );
      const { added = [], skipped = [] } = r.data;
      let msg = "";
      if (added.length) msg += `✅ ${added.length} hinzugefügt. `;
      if (skipped.length) msg += `⚠️ ${skipped.length} bereits vorhanden.`;
      setAddMsg(p => ({ ...p, [examId]: msg || "OK" }));
      setAddInput(p => ({ ...p, [examId]: "" }));
      loadEnrollments(examId);
    } catch (e) {
      setAddMsg(p => ({ ...p, [examId]: e.response?.data?.error || "Fehler." }));
    }
  };

  const handleDelete = async (examId, matrikel) => {
    if (!window.confirm(`Matrikelnummer ${matrikel} entfernen?`)) return;
    try {
      await axios.delete(`${API}/exams/${examId}/enrollments/${encodeURIComponent(matrikel)}/`, { headers });
      loadEnrollments(examId);
    } catch (e) {
      alert(e.response?.data?.error || "Fehler beim Löschen.");
    }
  };

  const startEdit = (examId, entry) => {
    setEditRow({ examId, matrikel: entry.matriculation_number, newMatrikel: entry.matriculation_number, newNote: entry.note });
  };

  const handleSaveEdit = async () => {
    const { examId, matrikel, newMatrikel, newNote } = editRow;
    try {
      await axios.put(
        `${API}/exams/${examId}/enrollments/${encodeURIComponent(matrikel)}/`,
        { matriculation_number: newMatrikel, note: newNote },
        { headers }
      );
      setEditRow(null);
      loadEnrollments(examId);
    } catch (e) {
      alert(e.response?.data?.error || "Fehler beim Speichern.");
    }
  };

  if (loading) return <div className="card"><p className="subtle">Lade Dashboard …</p></div>;
  if (error) return <div className="card" style={{ borderColor: "rgba(239,68,68,.35)" }}><p style={{ color: "#fecaca", margin: 0 }}>{error}</p></div>;
  if (!data) return null;

  const now = new Date();
  const pastExams = data.exams.filter(e => e.is_past).length;
  const upcomingExams = data.exams.filter(e => !e.is_past).length;

  return (
    <div className="stack-lg">
      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16 }}>
        {[
          { label: "Prüfungen gesamt", value: data.total_exams, icon: "📋" },
          { label: "Teilnehmer gesamt", value: data.total_participants, icon: "👥" },
          { label: "Vergangene", value: pastExams, icon: "✅" },
          { label: "Bevorstehende", value: upcomingExams, icon: "📅" },
        ].map(s => (
          <div key={s.label} className="card" style={{ textAlign: "center", padding: "20px 12px" }}>
            <div style={{ fontSize: 28 }}>{s.icon}</div>
            <div style={{ fontSize: 32, fontWeight: 800, margin: "6px 0 4px" }}>{s.value}</div>
            <div className="subtle" style={{ fontSize: 13 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Exam list */}
      <div className="stack">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Meine Prüfungen</h3>
          <button className="btn" onClick={onCreateExam}>➕ Neue Prüfung</button>
        </div>

        {data.exams.length === 0 && (
          <div className="card muted-box"><p className="subtle" style={{ margin: 0 }}>Noch keine Prüfungen erstellt.</p></div>
        )}

        {data.exams.map(exam => {
          const isExpanded = expandedId === exam.id;
          const tab = enrollTab[exam.id] || "list";
          const enrollments = enrollData[exam.id] || [];
          const examDate = new Date(exam.date);

          return (
            <div key={exam.id} className="card stack" style={{ gap: 0, padding: 0, overflow: "hidden" }}>
              {/* Header row */}
              <div
                style={{ padding: "16px 20px", cursor: "pointer", display: "flex", alignItems: "center", gap: 16 }}
                onClick={() => toggleExpand(exam.id)}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 700, fontSize: 16 }}>{exam.title}</span>
                    <span style={{
                      padding: "2px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600,
                      background: exam.is_past ? "rgba(100,116,139,.2)" : "rgba(34,197,94,.15)",
                      color: exam.is_past ? "#94a3b8" : "#22c55e",
                      border: exam.is_past ? "1px solid rgba(100,116,139,.3)" : "1px solid rgba(34,197,94,.3)",
                    }}>
                      {exam.is_past ? "Abgeschlossen" : "Bevorstehend"}
                    </span>
                  </div>
                  <div className="subtle" style={{ fontSize: 13, marginTop: 4 }}>
                    📅 {examDate.toLocaleDateString("de-DE", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                    &nbsp;·&nbsp; ⏱ {exam.duration_minutes} Min.
                    &nbsp;·&nbsp; ❓ {exam.question_count} Fragen
                    &nbsp;·&nbsp; 👥 {exam.participant_count} Teilnehmer
                  </div>
                </div>
                <span style={{ fontSize: 18, color: "var(--muted)" }}>{isExpanded ? "▲" : "▼"}</span>
              </div>

              {/* Expanded panel */}
              {isExpanded && (
                <div style={{ borderTop: "1px solid rgba(255,255,255,.08)", padding: "0 20px 20px" }}>

                  {/* Tabs */}
                  <div style={{ display: "flex", gap: 8, marginTop: 16, marginBottom: 16 }}>
                    {[
                      { key: "list", label: "👥 Teilnehmer" },
                      { key: "enrollments", label: "📋 Zulassungsliste" },
                    ].map(t => (
                      <button
                        key={t.key}
                        className={`mode-btn ${tab === t.key ? "active" : ""}`}
                        onClick={(e) => { e.stopPropagation(); setEnrollTab(p => ({ ...p, [exam.id]: t.key })); }}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>

                  {/* Participants tab */}
                  {tab === "list" && (
                    <div className="stack">
                      {exam.students.length === 0 ? (
                        <p className="subtle" style={{ margin: 0 }}>Noch keine Teilnehmer.</p>
                      ) : (
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid rgba(255,255,255,.1)" }}>
                              {["Name", "E-Mail", "Beigetreten am"].map(h => (
                                <th key={h} style={{ textAlign: "left", padding: "6px 10px", color: "var(--muted)", fontWeight: 600 }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {exam.students.map((s, i) => (
                              <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,.06)" }}>
                                <td style={{ padding: "8px 10px" }}>{s.name || "—"}</td>
                                <td style={{ padding: "8px 10px" }}>{s.email}</td>
                                <td style={{ padding: "8px 10px", color: "var(--muted)" }}>
                                  {new Date(s.joined_at).toLocaleDateString("de-DE")}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  )}

                  {/* Enrollments tab */}
                  {tab === "enrollments" && (
                    <div className="stack">
                      <p className="subtle" style={{ margin: 0, fontSize: 13 }}>
                        Nur Studierende mit Matrikelnummer in dieser Liste dürfen die Prüfung betreten.
                        Ist die Liste leer, ist der Beitritt für alle offen.
                      </p>

                      {/* Add section */}
                      <div className="card" style={{ background: "rgba(255,255,255,.04)", padding: 16 }}>
                        <div style={{ fontWeight: 600, marginBottom: 10 }}>Matrikelnummern hinzufügen</div>
                        <textarea
                          rows={4}
                          style={{
                            width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,.06)",
                            border: "1px solid rgba(255,255,255,.15)", borderRadius: 8, padding: 10,
                            color: "#e2e8f0", fontFamily: "inherit", fontSize: 14, resize: "vertical",
                          }}
                          placeholder={"Eine pro Zeile oder kommagetrennt:\n12345678\n23456789, 34567890"}
                          value={addInput[exam.id] || ""}
                          onChange={e => setAddInput(p => ({ ...p, [exam.id]: e.target.value }))}
                        />
                        <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center", flexWrap: "wrap" }}>
                          <input
                            type="text"
                            placeholder="Notiz (optional)"
                            style={{
                              flex: 1, minWidth: 140, background: "rgba(255,255,255,.06)",
                              border: "1px solid rgba(255,255,255,.15)", borderRadius: 8, padding: "8px 12px",
                              color: "#e2e8f0", fontSize: 14,
                            }}
                            value={addNote[exam.id] || ""}
                            onChange={e => setAddNote(p => ({ ...p, [exam.id]: e.target.value }))}
                          />
                          <button className="btn" onClick={() => handleAddEnrollments(exam.id)}>
                            ➕ Hinzufügen
                          </button>
                        </div>
                        {addMsg[exam.id] && (
                          <p style={{ margin: "8px 0 0", fontSize: 13, color: "#86efac" }}>{addMsg[exam.id]}</p>
                        )}
                      </div>

                      {/* Table */}
                      {enrollLoading[exam.id] ? (
                        <p className="subtle">Lade …</p>
                      ) : enrollments.length === 0 ? (
                        <p className="subtle" style={{ margin: 0 }}>Keine Einträge — alle Studierenden dürfen beitreten.</p>
                      ) : (
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                            <thead>
                              <tr style={{ borderBottom: "1px solid rgba(255,255,255,.1)" }}>
                                {["Matrikelnummer", "Notiz", "Hinzugefügt", "Aktionen"].map(h => (
                                  <th key={h} style={{ textAlign: "left", padding: "6px 10px", color: "var(--muted)", fontWeight: 600 }}>{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {enrollments.map((entry) => {
                                const isEditing = editRow && editRow.examId === exam.id && editRow.matrikel === entry.matriculation_number;
                                return (
                                  <tr key={entry.matriculation_number} style={{ borderBottom: "1px solid rgba(255,255,255,.06)" }}>
                                    <td style={{ padding: "8px 10px" }}>
                                      {isEditing ? (
                                        <input
                                          style={{ background: "rgba(255,255,255,.08)", border: "1px solid rgba(255,255,255,.2)", borderRadius: 6, padding: "4px 8px", color: "#e2e8f0", width: 130 }}
                                          value={editRow.newMatrikel}
                                          onChange={e => setEditRow(r => ({ ...r, newMatrikel: e.target.value }))}
                                        />
                                      ) : (
                                        <span style={{ fontFamily: "monospace", fontWeight: 600 }}>{entry.matriculation_number}</span>
                                      )}
                                    </td>
                                    <td style={{ padding: "8px 10px", color: "var(--muted)" }}>
                                      {isEditing ? (
                                        <input
                                          style={{ background: "rgba(255,255,255,.08)", border: "1px solid rgba(255,255,255,.2)", borderRadius: 6, padding: "4px 8px", color: "#e2e8f0", width: 160 }}
                                          value={editRow.newNote}
                                          onChange={e => setEditRow(r => ({ ...r, newNote: e.target.value }))}
                                        />
                                      ) : (
                                        entry.note || <span style={{ opacity: 0.4 }}>—</span>
                                      )}
                                    </td>
                                    <td style={{ padding: "8px 10px", color: "var(--muted)", fontSize: 12 }}>
                                      {new Date(entry.added_at).toLocaleDateString("de-DE")}
                                    </td>
                                    <td style={{ padding: "8px 10px" }}>
                                      <div style={{ display: "flex", gap: 8 }}>
                                        {isEditing ? (
                                          <>
                                            <button className="btn" style={{ padding: "4px 12px", fontSize: 13 }} onClick={handleSaveEdit}>✔ Speichern</button>
                                            <button className="btn secondary" style={{ padding: "4px 12px", fontSize: 13 }} onClick={() => setEditRow(null)}>Abbrechen</button>
                                          </>
                                        ) : (
                                          <>
                                            <button className="btn secondary" style={{ padding: "4px 10px", fontSize: 13 }} onClick={() => startEdit(exam.id, entry)}>✏️</button>
                                            <button className="btn" style={{ padding: "4px 10px", fontSize: 13, background: "rgba(239,68,68,.18)", borderColor: "rgba(239,68,68,.3)" }} onClick={() => handleDelete(exam.id, entry.matriculation_number)}>🗑</button>
                                          </>
                                        )}
                                      </div>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ProfessorDashboard;
