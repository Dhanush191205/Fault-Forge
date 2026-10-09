import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, BookOpen, CheckCircle2, FileCheck2, FileUp, FlaskConical, Plus, ShieldCheck, Sparkles, X } from 'lucide-react';
import { api, requestKey } from './api';
import type { Machine, Source, Draft, Review, Difficulty } from './types';

/** Instructor authoring, source review and assessment review; mutations require explicit review of exact hashes. */
export default function Studio() {
  const [tab, setTab] = useState('scenarios');
  const [machines, setMachines] = useState<Machine[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selected, setSelected] = useState<Draft | null>(null);
  const [approved, setApproved] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [machine, setMachine] = useState('');
  const [difficulty, setDifficulty] = useState<Difficulty>('Beginner');
  const [brief, setBrief] = useState('Create a source-grounded diagnostic exercise using the selected case and manual.');
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [job, setJob] = useState<{id: string; status: string; error_code?: string}>();
  const load = useCallback(async () => {
    const [m, s, d, r] = await Promise.all([api<Machine[]>('/machines'), api<Source[]>('/instructor/sources'), api<Draft[]>('/instructor/scenarios'), api<Review[]>('/instructor/attempts')]);
    setMachines(m); setSources(s); setDrafts(d); setReviews(r); setMachine(old => old || m[0]?.id || '');
  }, []);
  useEffect(() => {load().catch(e => setError(e.message));}, [load]);
  useEffect(() => {setSourceIds(sources.filter(s => s.machine_id === machine && s.approved).map(s => s.id));}, [machine, sources]);
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await api<{id: string; status: string; error_code?: string}>(`/jobs/${job.id}`, undefined, controller.signal);
        setJob(value);
        if (value.status === 'succeeded') {await load(); setNotice('The scenario passed automatic checks and is ready for your review.');}
        else if (value.status === 'failed') setError(`Generation stopped: ${value.error_code?.replaceAll('_', ' ')}. No scenario was published.`);
        else timer = setTimeout(poll, 2000);
      } catch(e) {if (!controller.signal.aborted) setError((e as Error).message);}
    };
    timer = setTimeout(poll, 1000);
    return () => {controller.abort(); clearTimeout(timer);};
  }, [job?.id, job?.status, load]);
  const action = async (work: () => Promise<unknown>, success: string) => {setBusy(true); setError(''); try {await work(); await load(); setNotice(success);} catch(e) {setError((e as Error).message);} finally {setBusy(false);}};
  const generate = (event: FormEvent) => {event.preventDefault(); action(async () => {setJob(await api('/scenarios/generate', {machine_id: machine, difficulty, source_ids: sourceIds, brief, request_key: requestKey()})); setGenerateOpen(false);}, 'Generation queued. Keep this page open to follow its progress.');};
  return <div className="page"><div className="page-heading"><div><span className="eyebrow">CURATE WITH CONFIDENCE</span><h1>Instructor studio</h1><p>Ground the content. Review the evidence. Shape better diagnosis.</p></div><button className="button primary" onClick={() => {setGenerateOpen(!generateOpen); setSelected(null);}}><Plus size={17}/>Generate scenario</button></div>
    <div className="studio-principle"><ShieldCheck size={22}/><div><strong>Every scenario earns its place in the library.</strong><span>Generation → automatic validation → instructor review → publication. All versions retain their history.</span></div><span className="pill">RAG FIRST</span></div>
    {error && <div role="alert" className="error">{error}</div>}{notice && <div className="notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss notification">×</button></div>}
    {job && <div className="job-status"><FlaskConical size={18}/><strong>Latest generation</strong><span className={`status ${job.status}`}>{job.status}</span><span className="caption">{job.id.slice(0, 8)}</span></div>}
    {generateOpen && <form className="generation-form panel" onSubmit={generate}><div className="section-heading"><h2>A new investigation</h2><button type="button" className="icon-button" aria-label="Close generation form" onClick={() => setGenerateOpen(false)}><X size={19}/></button></div><div className="form-columns"><label>Machine<select value={machine} onChange={e => setMachine(e.target.value)}>{machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label><label>Difficulty<select value={difficulty} onChange={e => setDifficulty(e.target.value as Difficulty)}>{['Beginner', 'Intern', 'Expert'].map(d => <option key={d}>{d}</option>)}</select></label></div><label>Training focus<textarea maxLength={500} required value={brief} onChange={e => setBrief(e.target.value)}/></label><fieldset><legend>Approved grounding sources</legend>{sources.filter(s => s.machine_id === machine && s.approved).map(s => <label key={s.id} className="check-row"><input type="checkbox" checked={sourceIds.includes(s.id)} onChange={e => setSourceIds(ids => e.target.checked ? [...ids, s.id] : ids.filter(id => id !== s.id))}/><span><strong>{s.title}</strong><small>{s.kind} · {s.locator}</small></span></label>)}</fieldset><p className="caption">At least one failure case and its manual are required. Expert hides hints and requires an instructor-reviewed explanation.</p><button className="button primary" disabled={busy || sourceIds.length < 2 || ['queued', 'running'].includes(job?.status || '')}><Sparkles size={16}/>{busy ? 'Submitting…' : 'Generate validated draft'}</button></form>}
    <div className="studio-tabs">{[['scenarios', 'Scenario review', drafts.filter(x => x.status === 'draft').length], ['sources', 'Knowledge sources', sources.length], ['assessments', 'Reasoning review', reviews.length]].map(([id, label, count]) => <button key={id} className={tab === id ? 'selected' : ''} onClick={() => {setTab(String(id)); setSelected(null);}}>{label}<span>{count}</span></button>)}</div>
    {tab === 'scenarios' && <div className={selected ? 'studio-layout reviewing' : 'studio-layout'}><div className="draft-list">{drafts.map(d => <button className={`draft-row ${selected?.id === d.id ? 'chosen' : ''}`} key={d.id} onClick={() => {setSelected(d); setApproved(false);}}><div className="draft-icon"><FileCheck2 size={21}/></div><div><strong>{d.payload.title}</strong><small>{machines.find(m => m.id === d.machine_id)?.name} · {d.difficulty}</small></div><span className={`status ${d.status}`}>{d.status}</span><ArrowRight size={16}/></button>)}{!drafts.length && <div className="empty-state"><BookOpen/><h3>No drafts yet</h3><p>Import and approve a curriculum pack, then generate a scenario.</p></div>}</div>{selected && <aside className="review-panel panel"><div className="section-heading"><span className="eyebrow">CONTENT REVIEW</span><button className="icon-button" aria-label="Close scenario review" onClick={() => setSelected(null)}><X size={18}/></button></div><h2>{selected.payload.title}</h2><span className="pill">{selected.difficulty} · {selected.payload.synthetic ? 'Synthetic fixture' : 'Equipment source'}</span><h3>Trainee briefing</h3><p>{selected.payload.briefing}</p><h3>Investigation and safety</h3><ol className="review-steps">{selected.payload.steps.map((s, i) => <li key={i}>{s}</li>)}</ol><h3>Private reference reasoning</h3><p>{selected.payload.explanation}</p><details><summary>Review sensors and quiz keys</summary><pre>{JSON.stringify(selected.payload.readings, null, 2)}</pre>{selected.payload.quiz.map(q => <div className="review-question" key={q.id}><strong>{q.text}</strong><ul>{q.options.map(o => <li key={o.id}>{o.text}{q.correct_id === o.id ? ' ✓' : ''}</li>)}</ul><p>{q.explanation}</p></div>)}</details><h3>Traceable sources</h3>{selected.sources.map(s => <p className="source-citation" key={s.id}><BookOpen size={14}/><span>{s.title}<small>{s.locator}</small></span></p>)}<div className="validation-pills">{selected.validations.filter(v => v.stage === 'automatic' && v.passed).flatMap(v => Object.keys(v.checks)).map(c => <span key={c}><CheckCircle2 size={12}/>{c.replaceAll('_', ' ')}</span>)}</div><p className="caption mono">{selected.generator_version}<br/>Hash {selected.content_hash.slice(0, 20)}…</p>{selected.status === 'draft' && <><label className="check-row approval"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)}/><span>I reviewed the safety framing, source support, sensor state and scoring keys for this exact draft.</span></label><button className="button primary wide" disabled={!approved || busy} onClick={() => action(async () => {await api(`/instructor/scenarios/${selected.id}/publish`, {content_hash: selected.content_hash, safety_reviewed: true, grounding_reviewed: true}); setSelected(null);}, 'Scenario published to the training library.')}><ShieldCheck size={16}/>Approve and publish</button></>}{selected.status === 'published' && <button className="button secondary wide" disabled={busy} onClick={() => action(async () => {await api(`/instructor/scenarios/${selected.id}/retire`, {}); setSelected(null);}, 'Scenario retired. Existing sessions and history are preserved.')}>Retire this version</button>}</aside>}</div>}
    {tab === 'sources' && <section><div className="source-import panel"><div><h3>Add a machine or source revision</h3><p>Import a curriculum JSON pack containing a machine configuration, manual chunks, and complete case rubrics.</p></div><label className="button secondary file-button"><FileUp size={16}/>Import curriculum<input type="file" accept="application/json,.json" onChange={e => {const file = e.target.files?.[0]; if (!file) return; if (file.size > 1_000_000) {setError('Curriculum pack must be under 1 MB.'); return;} action(async () => {const value = JSON.parse(await file.text()); await api('/instructor/curriculum', value);}, 'Curriculum imported. Review each source before approving generation.'); e.target.value = '';}}/></label></div><div className="source-grid">{sources.map(source => <SourceCard key={source.id} source={source} busy={busy} approve={() => action(() => api(`/instructor/sources/${source.id}/approve`, {content_hash: source.checksum, safety_reviewed: true, grounding_reviewed: true}), 'Source approved for generation.')}/>)}</div></section>}
    {tab === 'assessments' && <div className="review-queue">{reviews.length ? reviews.map(review => <ReasoningReview key={review.id} review={review} busy={busy} submit={(body) => action(() => api(`/instructor/attempts/${review.id}/review`, body), 'Reasoning review saved; the final score is now available to the trainee.')}/>) : <div className="empty-state"><CheckCircle2 size={32}/><h3>No reasoning reviews waiting.</h3><p>Intern and Expert explanations appear here after submission.</p></div>}</div>}
  </div>;
}

/** Show a complete source for review; approval requires an explicit checkbox and server hash check. */
function SourceCard({source, busy, approve}: {source: Source; busy: boolean; approve: () => void}) {
  const [checked, setChecked] = useState(false);
  return <article className="source-card panel"><span className="eyebrow">{source.kind} · {source.synthetic ? 'SYNTHETIC' : 'EQUIPMENT SOURCE'}</span><h3>{source.title}</h3><p>{source.locator}</p><span className={`status ${source.approved ? 'published' : 'draft'}`}>{source.approved ? 'Available for generation' : 'Requires review'}</span><details><summary>Read source and provenance</summary><pre>{JSON.stringify(source.content, null, 2)}</pre><p className="caption mono">SHA-256 {source.checksum}</p></details>{!source.approved && <><label className="check-row"><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)}/><span>I reviewed scope, safety, source rights and correctness.</span></label><button className="button secondary" disabled={!checked || busy} onClick={approve}>Approve source</button></>}</article>;
}

/** Collect two rubric scores and feedback; the server prevents self-review and duplicate grading. */
function ReasoningReview({review, busy, submit}: {review: Review; busy: boolean; submit: (body: unknown) => void}) {
  const [evidence, setEvidence] = useState(0);
  const [alternatives, setAlternatives] = useState(0);
  const [feedback, setFeedback] = useState('');
  return <form className="panel reasoning-card" onSubmit={e => {e.preventDefault(); submit({evidence_reasoning: evidence, alternative_reasoning: alternatives, feedback});}}><div className="section-heading"><h2>{review.learner}</h2><span className="pill">{review.snapshot.difficulty}</span></div><h3>{review.snapshot.title}</h3><blockquote>{review.submission.rationale}</blockquote><p><strong>Reference:</strong> {review.reference.explanation}</p><p className="caption">Recorded investigation replay: {review.replay.verified ? 'verified' : 'not verified'} · Automatic score: {review.snapshot.result?.automatic_score}/80</p><div className="form-columns"><label>Evidence reasoning · 0–10<input type="number" min={0} max={10} required value={evidence} onChange={e => setEvidence(Number(e.target.value))}/><small>{review.reference.rationale_rubric[0]}</small></label><label>Alternative reasoning · 0–10<input type="number" min={0} max={10} required value={alternatives} onChange={e => setAlternatives(Number(e.target.value))}/><small>{review.reference.rationale_rubric[1]}</small></label></div><label>Explain the feedback<textarea required minLength={20} maxLength={1000} value={feedback} onChange={e => setFeedback(e.target.value)}/></label><button className="button primary" disabled={busy}>Save review<ArrowRight size={16}/></button></form>;
}
