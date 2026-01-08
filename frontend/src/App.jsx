import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
// Use lightweight emoji icons as a fallback to avoid runtime import errors from icon libraries
const Icon = ({ emoji, size = 18, style = {} }) => (
  <span style={{ fontSize: size, lineHeight: 1, display: 'inline-block', ...style }}>{emoji}</span>
);
const Send = (props) => <Icon emoji="➤" {...props} />;
const Upload = (props) => <Icon emoji="📤" {...props} />;
const User = (props) => <Icon emoji="👤" {...props} />;
const Bot = (props) => <Icon emoji="🤖" {...props} />;
const Loader2 = (props) => <Icon emoji="⏳" {...props} />;
const ShieldCheck = (props) => <Icon emoji="🛡️" {...props} />;
const LogOut = (props) => <Icon emoji="🔒" {...props} />;
const LayoutGrid = (props) => <Icon emoji="🔲" {...props} />;
const Building2 = (props) => <Icon emoji="🏢" {...props} />;
const Lock = (props) => <Icon emoji="🔐" {...props} />;
const Copy = (props) => <Icon emoji="📋" {...props} />;
const RefreshCw = (props) => <Icon emoji="🔁" {...props} />;
const ThumbUp = (props) => <Icon emoji="👍" {...props} />;
const ThumbDown = (props) => <Icon emoji="👎" {...props} />;
const Download = (props) => <Icon emoji="⬇️" {...props} />;

const API_BASE = "http://localhost:8000";

// Departments based on your provided file structure
const DEPARTMENTS = [
  { name: "Engineering", icon: "⚙️", color: "#3b82f6" },
  { name: "Marketing", icon: "📢", color: "#ec4899" },
  { name: "Finance", icon: "💰", color: "#10b981" },
  { name: "Legal", icon: "⚖️", color: "#f59e0b" },
  { name: "Sales", icon: "📈", color: "#ef4444" },
  { name: "Customer Support", icon: "🎧", color: "#8b5cf6" },
  { name: "Operations", icon: "🏗️", color: "#6366f1" },
  { name: "Admin", icon: "🏢", color: "#64748b" }
];

function App() {
  // --- Navigation & Auth State ---
  const [view, setView] = useState('role-select'); // role-select | dept-grid | login | chat
  const [role, setRole] = useState(null); // HR | EMPLOYEE
  const [selectedDept, setSelectedDept] = useState("");
  const [creds, setCreds] = useState({ username: "", password: "" });
  const [countryPolicy, setCountryPolicy] = useState('india'); // 'india' or 'foreign'
  
  // --- Chat & Upload State ---
  const [messages, setMessages] = useState([]);
  const [historyThreads, setHistoryThreads] = useState([]);
  const [input, setInput] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const messagesEndRef = useRef(null);
  const messageListRef = useRef(null);

  // feedback / action helpers
  const handleCopy = async (text) => { try { await navigator.clipboard.writeText(text); } catch { } };
  const handlePrefill = (q) => setInput(q || "");
  const handleDownload = (text, filename = 'answer.txt') => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  };
  const handleFeedback = (index, value) => setMessages(prev => prev.map((m,i)=> i===index?{...m, liked:value}:m));

  useEffect(() => {
    // default behaviour: scroll to bottom on new messages
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    // fetch department history when chat opens
    if (view === 'chat' && selectedDept) {
      fetchHistory();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, selectedDept]);

  // --- Logic Handlers ---

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      // Sending role, department and country to backend; include cookies
      await axios.post(`${API_BASE}/login`, {
        ...creds,
        role: role,
        department: selectedDept || "HR",
        country: countryPolicy
      }, { withCredentials: true });
      setView('chat');
    } catch (err) {
      alert("Invalid Credentials! Please try again.");
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const questionText = input;
    const userMsg = { role: "user", content: questionText };
    setMessages(prev => [...prev, userMsg]);
    setLastQuestion(questionText);
    setInput("");
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE}/query`, {
        question: questionText,
        policy_country: countryPolicy,
        department: (selectedDept || '').toLowerCase()
      }, { withCredentials: true });
      // refresh history after sending
      fetchHistory();
      setMessages(prev => [...prev, {
        role: "assistant",
        content: res.data.answer,
        suggested_follow_ups: res.data.suggested_follow_ups || [],
        next_steps: res.data.next_steps || "",
        confidence: res.data.confidence,
        question: questionText,
        liked: null
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "Error connecting to AI service.", suggested_follow_ups: [], next_steps: "", question: questionText }]);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    if (!selectedDept) return;
    try {
      const dept = selectedDept.toLowerCase();
      const res = await axios.get(`${API_BASE}/history`, { params: { department: dept }, withCredentials: true });
      setHistoryThreads(res.data || []);
    } catch (err) {
      // ignore
    }
  };

  const handleLoadThread = async (message_id) => {
    if (!selectedDept || !message_id) return;
    try {
      const dept = selectedDept.toLowerCase();
      const res = await axios.get(`${API_BASE}/history/thread/${message_id}`, { params: { department: dept }, withCredentials: true });
      if (res.data && Array.isArray(res.data)) {
        setMessages(res.data.map(m => ({ role: m.role, content: m.content })));
      }
    } catch (err) {
      // ignore
    }
  };

  const handleUpload = async () => {
    if (!file) return alert("Please select a PDF file.");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("department", selectedDept || "HR");
    formData.append("role", "EMPLOYEE"); // Target visibility

    try {
      setLoading(true);
      await axios.post(`${API_BASE}/upload`, formData);
      alert("Policy uploaded and indexed successfully!");
      setFile(null);
    } catch (err) {
      alert("Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  // --- Views ---

  // 1. Role Selection Page
  if (view === 'role-select') return (
    <div style={styles.fullPageCenter}>
      <div style={styles.loginCard}>
        <ShieldCheck size={60} color="#2563eb" />
        <h1 style={{ margin: '10px 0' }}>HR AI Portal</h1>
        <p style={{ color: '#64748b', marginBottom: '20px' }}>Select your access level</p>
        <button onClick={() => { setRole('HR'); setSelectedDept('HR'); setView('login'); }} style={styles.primaryBtn}>HR Admin Login</button>
        <button onClick={() => { setRole('EMPLOYEE'); setSelectedDept(''); setView('dept-grid'); }} style={styles.secondaryBtn}>Employee Login</button>
   
      </div>
    </div>
  );

  // 2. Department Selection Grid (For Employees)
  if (view === 'dept-grid') return (
    <div style={styles.container}>
      <h1 style={{ textAlign: 'center', marginTop: '40px' }}>Select Your Department</h1>
      <div style={styles.grid}>
        {DEPARTMENTS.map(dept => (
          <div key={dept.name} onClick={() => { setSelectedDept(dept.name); setView('login'); }} 
               style={{ ...styles.deptCard, borderTop: `6px solid ${dept.color}` }}>
            <span style={{ fontSize: '3rem' }}>{dept.icon}</span>
            <h3>{dept.name}</h3>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Access local policies</p>
          </div>
        ))}
      </div>
      <button onClick={() => setView('role-select')} style={styles.backLink}>← Back to Roles</button>
    </div>
  );

  // 3. Login Authentication Page
  if (view === 'login') return (
    <div style={styles.fullPageCenter}>
      <form onSubmit={handleLogin} style={styles.loginCard}>
        <Lock size={40} color="#64748b" />
        <h2 style={{ marginBottom: 6 }}>{role === 'HR' ? 'HR Admin' : (selectedDept || 'Employee')} Login</h2>

        {/* Policy Region selector (kept) */}
        <div style={{ textAlign: 'left', width: '100%', marginBottom: 12 }}>
          <label style={{ fontSize: '0.85rem', color: '#64748b' }}>Policy Region</label>
          <div style={{ display: 'flex', gap: '10px', marginTop: 8 }}>
            <label style={styles.policyOption}><input type="radio" name="policy" value="india" checked={countryPolicy==='india'} onChange={() => setCountryPolicy('india')} /> India</label>
            <label style={styles.policyOption}><input type="radio" name="policy" value="foreign" checked={countryPolicy==='foreign'} onChange={() => setCountryPolicy('foreign')} /> Foreign</label>
          </div>
        </div>

        {/* Primary email/password login */}
        <input type="email" placeholder="Email address" required style={styles.input}
               onChange={e => setCreds({...creds, username: e.target.value})} />
        <input type="password" placeholder="Password" required style={styles.input}
               onChange={e => setCreds({...creds, password: e.target.value})} />

        <button type="submit" style={{ ...styles.primaryBtn, marginTop: 6 }}>Login</button>

        {/* separator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '14px 0', width: '100%' }}>
          <hr style={{ flex: 1, border: 'none', borderTop: '1px solid #e6eef8' }} />
          <div style={{ color: '#64748b', fontSize: '0.9rem' }}>or</div>
          <hr style={{ flex: 1, border: 'none', borderTop: '1px solid #e6eef8' }} />
        </div>

        {/* Social / External SSO Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%' }}>
          <button type="button" onClick={() => window.open('https://accounts.google.com/signin', '_blank')} style={styles.socialBtn}><span style={{ marginRight: 10 }}>G</span> Sign in with Google</button>
          <button type="button" onClick={() => window.open('https://www.facebook.com/login', '_blank')} style={styles.socialBtn}><span style={{ marginRight: 10 }}>f</span> Sign in with Meta</button>
          <button type="button" onClick={() => window.open(`${API_BASE}/login`, '_self')} style={styles.azureBtn}>Sign in with Azure</button>
        </div>

        <button onClick={() => setView(role === 'HR' ? 'role-select' : 'dept-grid')} style={styles.textBtn}>Go Back</button>
      </form>
    </div>
  );

  // 4. Main Chat Interface
  return (
    <div style={styles.chatLayout}>
      {/* Sidebar */}
      <div style={styles.sidebar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '30px' }}>
          <Building2 size={24} color="#3b82f6" />
          <h2 style={{ fontSize: '1.2rem' }}>{selectedDept} Portal</h2>
        </div>

        {role === 'HR' && (
          <div style={styles.adminBox}>
            <p style={styles.label}>ADMIN: UPLOAD POLICY</p>
            <input type="file" onChange={e => setFile(e.target.files[0])} style={styles.fileInput} />
            <button onClick={handleUpload} disabled={loading} style={styles.uploadBtn}>
              {loading ? 'Processing...' : 'Index PDF'}
            </button>
          </div>
        )}

        {/* Department conversation history */}
        <div style={{ marginTop: 20, overflowY: 'auto', maxHeight: '60vh', paddingRight: 6 }}>
          <p style={{ color: '#94a3b8', fontSize: '0.8rem', marginBottom: 8 }}>Recent Conversations</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {historyThreads.length === 0 && <div style={{ color: '#64748b', fontSize: '0.85rem' }}>No recent conversations</div>}
            {historyThreads.map(h => (
              <button key={h.message_id} onClick={() => handleLoadThread(h.message_id)} style={{ textAlign: 'left', padding: '8px', borderRadius: 8, background: 'transparent', border: '1px solid rgba(255,255,255,0.06)', color: '#fff', cursor: 'pointer' }}>
                <div style={{ fontWeight: '600' }}>{h.session_id}</div>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{h.question}</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 6 }}>{h.timestamp ? new Date(h.timestamp).toLocaleString() : ''}</div>
              </button>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 'auto' }}>
            <div style={styles.userInfo}>
                <div style={styles.avatar}>{role === 'HR' ? 'H' : 'E'}</div>
                <div>
                    <p style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>{creds.username}</p>
                    <p style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{role}</p>
                </div>
            </div>
          <button onClick={() => window.location.reload()} style={styles.logoutBtn}><LogOut size={16} /> Logout</button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div style={styles.chatContainer}>
        <div style={{ position: 'relative' }}>
          <div ref={messageListRef} style={{ ...styles.messageList }}>
          {messages.length === 0 && (
            <div style={styles.emptyState}>
              <Bot size={48} color="#cbd5e1" />
              <p>Welcome to the {selectedDept} AI Assistant. Ask me anything about your department policies.</p>
              
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ ...styles.messageWrapper, justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{ ...styles.bubble, background: m.role === 'user' ? '#2563eb' : '#fff', color: m.role === 'user' ? '#fff' : '#1e293b' }}>
                {/* Render paragraphs; lines with ':' get heading bolded */}
                {m.content && m.content.split(/\n\n+/).map((para, pi) => (
                  <div key={pi} style={{ marginBottom: 8 }}>
                    { /* remove asterisks from assistant answer and split into lines */ }
                    {para.replace(/\*/g, '').split('\n').map((line, li) => {
                      const cleaned = line.trim();
                      const idx = cleaned.indexOf(':');
                      if (idx !== -1) {
                        const head = cleaned.slice(0, idx + 1);
                        const rest = cleaned.slice(idx + 1).trim();
                        return <div key={li}><strong>{head}</strong> {rest}</div>;
                      }
                      return <div key={li}>{cleaned}</div>;
                    })}
                  </div>
                ))}
              </div>

              {m.role !== 'user' && (
                <div style={styles.suggestionsWrapper}>
                  {m.next_steps && <div style={styles.nextSteps}><strong>Next step:</strong> {m.next_steps}</div>}
                  {role === 'HR' && typeof m.confidence !== 'undefined' && (
                    <div style={styles.confidence}><strong>Confidence:</strong> {m.confidence}%</div>
                  )}
                  {m.suggested_follow_ups && m.suggested_follow_ups.length > 0 && (
                    <>
                      <div style={styles.suggestionsTitle}>Suggested follow-up questions</div>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
                        {m.suggested_follow_ups.map((s, idx) => {
                          const text = (s || '').replace(/^\s*[\*\-]+\s*/, '').replace(/\*/g, '');
                          return (
                            <button key={idx} onClick={() => handlePrefill(text)} style={styles.suggestionButton}>{text}</button>
                          );
                        })}
                      </div>
                    </>
                  )}

                  <div style={styles.actionRow}>
                    <button onClick={() => handleCopy(m.content)} style={styles.iconBtn}><Copy size={16} /></button>
                    <button onClick={() => handlePrefill(m.question || lastQuestion)} style={styles.iconBtn}><RefreshCw size={16} /></button>
                    <button onClick={() => handleFeedback(i, true)} style={{ ...styles.iconBtn, color: m.liked === true ? '#10b981' : undefined }}><ThumbUp size={16} /></button>
                    <button onClick={() => handleFeedback(i, false)} style={{ ...styles.iconBtn, color: m.liked === false ? '#ef4444' : undefined }}><ThumbDown size={16} /></button>
                    <button onClick={() => handleDownload(m.content || '', 'answer.txt')} style={styles.iconBtn}><Download size={16} /></button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {loading && <div style={{ padding: '10px' }}><Loader2 className="animate-spin" size={20} /></div>}
          <div ref={messagesEndRef} />
          </div>

         {/* Scroll controls
          <div style={styles.scrollControls}>
            <button onClick={() => { if (messageListRef.current) messageListRef.current.scrollTo({ top: 0, behavior: 'smooth' }); }} style={styles.scrollBtn}>↑ Top</button>
            <button onClick={() => { if (messageListRef.current) messageListRef.current.scrollTo({ top: messageListRef.current.scrollHeight, behavior: 'smooth' }); }} style={styles.scrollBtn}>↓ Bottom</button>
          </div> */}
        </div>

        <form onSubmit={handleSendMessage} style={styles.inputArea}>
          <input value={input} onChange={e => setInput(e.target.value)} 
                 placeholder={`Type your question for ${selectedDept} Assistant...`} style={styles.chatInput} />
          <button type="submit" style={styles.sendBtn}><Send size={20} /></button>
        </form>
      </div>
    </div>
  );
}

// --- Styles ---
const styles = {
  fullPageCenter: { height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1f5f9' },
  loginCard: { background: '#fff', padding: '40px', borderRadius: '20px', boxShadow: '0 10px 25px rgba(0,0,0,0.05)', width: '360px', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '15px' },
  container: { padding: '40px', minHeight: '100vh', backgroundColor: '#f8fafc' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '25px', maxWidth: '1100px', margin: '40px auto' },
  deptCard: { background: '#fff', padding: '30px', borderRadius: '15px', textAlign: 'center', cursor: 'pointer', transition: 'transform 0.2s', boxShadow: '0 4px 6px rgba(0,0,0,0.02)' },
  suggestionsWrapper: { marginTop: '8px', background: '#f8fafc', padding: '10px 12px', borderRadius: '10px', border: '1px solid #e6eef8', maxWidth: '75%' },
  suggestionsTitle: { fontSize: '0.8rem', color: '#64748b', marginBottom: '6px', fontWeight: '600' },
  nextSteps: { marginTop: '8px', fontSize: '0.85rem', color: '#0f172a' },
  suggestionList: { margin: 0, paddingLeft: '18px' },
  suggestionItem: { fontSize: '0.9rem', color: '#475569', marginBottom: '6px' },
  suggestionButton: { background: '#e6f0ff', color: '#0f172a', border: 'none', padding: '6px 10px', borderRadius: 12, cursor: 'pointer', fontSize: '0.9rem' },
  actionRow: { display: 'flex', gap: '8px', marginTop: '8px' },
  iconBtn: { background: 'transparent', border: 'none', cursor: 'pointer', padding: '6px', borderRadius: '6px' },
  primaryBtn: { background: '#2563eb', color: '#fff', padding: '14px', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: 'bold' },
  secondaryBtn: { background: '#fff', color: '#2563eb', padding: '14px', border: '2px solid #2563eb', borderRadius: '10px', cursor: 'pointer', fontWeight: 'bold' },
  input: { padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0', outline: 'none' },
  chatLayout: { display: 'flex', height: '100vh', overflow: 'hidden' },
  sidebar: { width: '280px', background: '#0f172a', color: '#fff', padding: '25px', display: 'flex', flexDirection: 'column' },
  adminBox: { background: '#1e293b', padding: '15px', borderRadius: '12px', marginTop: '10px' },
  label: { fontSize: '0.7rem', color: '#94a3b8', fontWeight: 'bold', letterSpacing: '1px' },
  fileInput: { fontSize: '0.7rem', margin: '10px 0', width: '100%' },
  uploadBtn: { background: '#3b82f6', color: '#fff', border: 'none', width: '100%', padding: '8px', borderRadius: '6px', cursor: 'pointer' },
  chatContainer: { flex: 1, display: 'flex', flexDirection: 'column', background: '#f8fafc' },
  messageList: { flex: 1, overflowY: 'auto', padding: '40px', display: 'flex', flexDirection: 'column', gap: '20px' },
  messageWrapper: { display: 'flex', width: '100%' },
  bubble: { padding: '14px 20px', borderRadius: '18px', maxWidth: '75%', boxShadow: '0 2px 4px rgba(0,0,0,0.05)', lineHeight: '1.5' },
  inputArea: { padding: '25px 40px', background: '#fff', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '15px' },
  chatInput: { flex: 1, padding: '15px 25px', borderRadius: '30px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '1rem' },
  sendBtn: { background: '#10b981', color: '#fff', border: 'none', borderRadius: '50%', width: '50px', height: '50px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  logoutBtn: { width: '100%', background: 'transparent', border: '1px solid #334155', color: '#fff', padding: '10px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center' },
  textBtn: { background: 'none', border: 'none', color: '#64748b', textDecoration: 'underline', cursor: 'pointer' },
  backLink: { display: 'block', margin: '20px auto', background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontWeight: 'bold' },
  emptyState: { textAlign: 'center', marginTop: '100px', color: '#94a3b8', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' },
  userInfo: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px', padding: '10px', background: '#1e293b', borderRadius: '10px' },
  avatar: { width: '35px', height: '35px', borderRadius: '50%', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }
};

// scroll controls styles
styles.scrollControls = {
  position: 'absolute', right: 24, bottom: 100, display: 'flex', flexDirection: 'column', gap: 8
};
styles.scrollBtn = { background: '#fff', border: '1px solid #e2e8f0', padding: '8px 10px', borderRadius: 8, cursor: 'pointer', boxShadow: '0 4px 10px rgba(2,6,23,0.06)' };

// small style additions
styles.policyOption = { fontSize: '0.9rem', color: '#0f172a' };
styles.ssoBtn = { background: '#111827', color: '#fff', border: 'none', padding: '10px 12px', borderRadius: '8px', cursor: 'pointer' };
styles.socialBtn = { background: '#fff', color: '#0f172a', border: '1px solid #e6eef8', padding: '10px 12px', borderRadius: '8px', cursor: 'pointer', textAlign: 'left', fontWeight: '600' };
styles.azureBtn = { background: '#2563eb', color: '#fff', border: 'none', padding: '10px 12px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600' };

export default App;