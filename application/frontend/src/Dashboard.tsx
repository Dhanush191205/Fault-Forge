import { useEffect, useState } from 'react';
import { ArrowDownRight, ArrowRight, BookOpen, Check, ChevronRight, Clock3, Crosshair, Filter, Layers3, Search, ShieldCheck, Sparkles, TrendingUp } from 'lucide-react';
import { api } from './api';
import MachinePreview from './MachinePreview';
import type { User, Machine, Scenario, DashboardData } from './types';

/** Load the live catalog and learner metrics; render explicit empty/error states without invented progress. */
export default function Dashboard({view, user, navigate}: {view: string; user: User; navigate: (route: string) => void}) {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [selectedMachine, setSelectedMachine] = useState('all');
  const [difficulty, setDifficulty] = useState('all');
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([api<Machine[]>('/machines', undefined, abort.signal), api<Scenario[]>('/scenarios', undefined, abort.signal), api<DashboardData>('/dashboard', undefined, abort.signal)])
      .then(([m, s, d]) => {setMachines(m); setScenarios(s); setDashboard(d);}).catch(e => {if (!abort.signal.aborted) setError(e.message);}).finally(() => setLoading(false));
    return () => abort.abort();
  }, []);
  const filtered = scenarios.filter(s => (selectedMachine === 'all' || s.machine_id === selectedMachine) && (difficulty === 'all' || s.difficulty === difficulty) && `${s.title} ${s.briefing}`.toLowerCase().includes(query.toLowerCase()));
  const start = async (s: Scenario) => {setBusy(s.id); setError(''); try {const attempt = await api<{id: string}>(`/scenarios/${s.id}/start`, {}); navigate(`session/${attempt.id}`);} catch(e) {setError((e as Error).message);} finally {setBusy('');}};
  if (loading) return <div className="loading-panel">Loading your training workspace…</div>;
  const overview = view !== 'library' && view !== 'sessions';
  return <div className="page dashboard-page"><div className="page-heading"><div><span className="eyebrow">{view === 'sessions' ? 'YOUR LEARNING RECORD' : 'MAINTENANCE TRAINING WORKSPACE'}</span><h1>{view === 'library' ? 'Training library' : view === 'sessions' ? 'My sessions' : 'Your next breakthrough starts here.'}</h1><p>{view === 'sessions' ? 'Pick up where you left off, or revisit the reasoning behind a result.' : 'Build diagnostic confidence, one investigation at a time.'}</p></div><span className="date-tag"><span className="live-dot"/> Workspace ready</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {overview && <><section className="hero"><div className="hero-copy"><span className="hero-label"><span/> THE VIRTUAL WORKSHOP</span><h2>Find the evidence.<br/>Forge your expertise.</h2><p>Step inside an industrial training environment.<br/>Investigate the symptoms. Make the diagnosis.</p><button className="button dark" onClick={() => document.getElementById('training-library')?.scrollIntoView({behavior: 'smooth'})}>Explore scenarios <ArrowRight size={17}/></button><div className="hero-caption"><ShieldCheck size={15}/> A safe space for hands-on thinking</div></div><div className="hero-art"><MachineArt variant={1}/><span className="art-tag one"><span/> SIMULATION READY</span><span className="art-tag two"><Crosshair size={14}/> Observe. Question. Diagnose.</span><div className="art-grid"/></div></section>
      <div className="stats-grid"><Metric label="Sessions completed" value={String(dashboard?.completed || 0)} detail="Your recorded learning progress" icon={<Check size={20}/>}/><Metric label="Average score" value={dashboard?.average == null ? '—' : `${dashboard.average}%`} detail="Finalized assessments only" icon={<TrendingUp size={20}/>}/><Metric label="Available machines" value={String(machines.length).padStart(2, '0')} detail="Different systems. Transferable skills." icon={<Layers3 size={20}/>}/><Metric label="Awaiting feedback" value={String(dashboard?.review_pending || 0)} detail="Instructor reasoning reviews" icon={<Clock3 size={20}/>}/></div></>}
    {view !== 'sessions' && <section id="training-library" className="library-section"><div className="section-heading"><div><span className="eyebrow">LEARN BY INVESTIGATING</span><h2>{overview ? 'Choose your next challenge' : 'Find a training scenario'}</h2></div><span className="muted small">{filtered.length} published scenarios</span></div><div className="filter-bar"><div className="filter-tabs"><button onClick={() => setSelectedMachine('all')} className={selectedMachine === 'all' ? 'selected' : ''}>All machines</button>{machines.map(m => <button key={m.id} className={selectedMachine === m.id ? 'selected' : ''} onClick={() => setSelectedMachine(m.id)}>{m.name}</button>)}</div><div className="filter-controls"><label className="search"><Search size={17}/><input aria-label="Search scenarios" placeholder="Search scenarios" value={query} onChange={e => setQuery(e.target.value)}/></label><label className="difficulty-select"><Filter size={15}/><select aria-label="Difficulty" value={difficulty} onChange={e => setDifficulty(e.target.value)}><option value="all">All levels</option>{['Beginner', 'Intern', 'Expert'].map(d => <option key={d}>{d}</option>)}</select></label></div></div>
      {filtered.length === 0 ? <div className="empty-state"><BookOpen size={32}/><h3>{scenarios.length ? 'No scenarios match your filters.' : 'Your workshop is ready for its first scenario.'}</h3><p>{scenarios.length ? 'Try another machine or difficulty.' : user.role === 'instructor' ? 'Review the validated synthetic drafts in Instructor studio and publish a scenario to begin.' : 'An instructor needs to review and publish training scenarios before you can begin.'}</p>{!scenarios.length && user.role === 'instructor' && <button className="button primary" onClick={() => navigate('studio')}>Review scenario drafts<ArrowRight size={17}/></button>}</div> : <div className="scenario-grid">{filtered.map(s => {const mIndex = machines.findIndex(m => m.id === s.machine_id); return <article className="scenario-card" key={s.id}><div className={`card-art tone-${mIndex % 3}`}><span className="machine-type">{machines.find(m => m.id === s.machine_id)?.name || s.machine_id}</span><MachinePreview machine={machines.find(m => m.id === s.machine_id)}/><span className="dimension-label">VIRTUAL TRAINING MODEL</span></div><div className="card-body"><div className="card-tags"><span className={`difficulty ${s.difficulty.toLowerCase()}`}><span/>{s.difficulty}</span><span className="subtle-tag">{s.synthetic ? 'Synthetic fixture' : 'Reviewed source'}</span></div><h3>{s.title}</h3><p>{s.briefing}</p><div className="card-meta"><span><Crosshair size={14}/>5 investigation steps</span><span><BookOpen size={14}/>3 questions</span></div><button className="card-start" disabled={!!busy} onClick={() => start(s)}>{busy === s.id ? 'Opening session…' : 'Enter simulation'}<ArrowRight size={17}/></button></div></article>;})}</div>}
    </section>}
    {view !== 'library' && <section className="recent-section"><div className="section-heading"><div><span className="eyebrow">KEEP THE MOMENTUM</span><h2>{view === 'sessions' ? 'Recorded sessions' : 'Your recent activity'}</h2></div>{overview && <button className="text-button" onClick={() => navigate('sessions')}>View all sessions<ChevronRight size={15}/></button>}</div>{dashboard?.sessions.length ? <div className="session-table"><div className="session-row table-head"><span>SCENARIO</span><span>LEVEL</span><span>STATUS</span><span>RESULT</span><span/></div>{dashboard.sessions.slice(0, view === 'sessions' ? 50 : 4).map(s => <button className="session-row" key={s.id} onClick={() => navigate(`session/${s.id}`)}><strong>{s.title}<small>{machines.find(m => m.id === s.machine_id)?.name}</small></strong><span>{s.difficulty}</span><span className={`status ${s.status}`}>{s.status.replace('_', ' ')}</span><span>{s.score == null ? '—' : `${s.score}%`}</span><ArrowRight size={17}/></button>)}</div> : <div className="activity-empty"><span className="round-icon"><ArrowDownRight size={22}/></span><div><h3>A fresh start. A stronger skill set.</h3><p>Complete a training session to see your progress here.</p></div><Sparkles size={22}/></div>}<p className="caption">{dashboard?.scope}. Scores reflect this simulation, not real-world certification.</p></section>}
  </div>;
}

/** Display one database-derived metric with descriptive text; accepts no untrusted markup. */
function Metric({label, value, detail, icon}: {label: string; value: string; detail: string; icon: React.ReactNode}) {
  return <div className="metric"><div><span>{label}</span><div className="metric-value">{value}</div><small>{detail}</small></div><span className="metric-icon">{icon}</span></div>;
}

/** Render decorative vector workshop artwork; it conveys no machine condition or physical measurements. */
function MachineArt({variant}: {variant: number}) {
  return <svg className="machine-art" viewBox="0 0 430 300" fill="none" aria-hidden="true"><ellipse cx="224" cy="254" rx="145" ry="24" fill="#1a2634" opacity=".08"/>
    <path d="M83 202L226 144L365 203L220 269Z" fill="#a3afb0"/><path d="M83 202V216L220 283V269Z" fill="#7a898f"/><path d="M220 269L365 203V217L220 283Z" fill="#647882"/>
    <path d="M115 78L226 31L333 78L220 127Z" fill="#eff2eb"/><path d="M115 78V196L220 249V127Z" fill="#c2ccca"/><path d="M220 127L333 78V199L220 249Z" fill="#95a9aa"/>
    <path d="M133 105L203 139V216L133 181Z" fill="#253f47"/><path d="M144 119L191 142V194L144 172Z" fill="#38585e"/><path d="M232 141L318 104V180L232 218Z" fill="#38515a"/>
    <path d="M246 150L303 126V168L246 192Z" fill="#708a8b"/><path d="M253 156L295 138V159L253 177Z" fill="#b9daab"/>
    <path d="M158 137L172 144V174L158 167Z" fill="#d9e4dc"/><path d="M161 172L169 176V190L161 186Z" fill="#caed9f"/>
    <path d="M139 191L163 181L198 198L176 210Z" fill="#bac7c9"/><path d="M139 191V200L176 219V210Z" fill="#7a9095"/>
    <path d="M277 56L321 75L285 91L241 72Z" fill="#d2e5cd"/><path d="M277 56V39L321 58V75Z" fill="#a6c0a2"/>
    <path d="M345 155L375 168V216L345 204Z" fill="#3b535b"/><path d="M352 169L368 176V190L352 183Z" fill="#bde998"/>
    {variant % 2 === 0 && <><path d="M80 185L111 197V240L80 228Z" fill="#d5ddd9"/><path d="M80 185L99 177L130 190L111 197Z" fill="#edf1e7"/><path d="M111 197L130 190V232L111 240Z" fill="#9caead"/></>}
    <path d="M190 60L224 45L253 58L219 73Z" fill="#c5e5ad"/><path d="M219 73V91L253 76V58Z" fill="#98b782"/>
    <path d="M223 247V261M104 211L113 216M327 217L345 209" stroke="#edf4e3" strokeWidth="3"/></svg>;
}
