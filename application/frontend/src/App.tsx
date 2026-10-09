import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Activity, ArrowRight, BookOpen, Boxes, ChevronRight, CircleHelp, FlaskConical, LayoutDashboard, LogOut, ShieldCheck, Sparkles } from 'lucide-react';
import { api, setCsrf } from './api';
import type { User } from './types';
import Dashboard from './Dashboard';
import Studio from './Studio';
import TrainingSession from './TrainingSession';

/** Render sign-in and the authenticated workspace; session failures return the user to sign-in. */
export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [route, setRoute] = useState(location.hash.slice(1) || 'dashboard');
  const [error, setError] = useState('');
  useEffect(() => {
    const abort = new AbortController();
    api<User>('/auth/me', undefined, abort.signal).then(u => {setUser(u); setCsrf(u.csrf);}).catch(() => {}).finally(() => setLoading(false));
    const onHash = () => setRoute(location.hash.slice(1) || 'dashboard');
    const expired = () => {setUser(null); setCsrf('');};
    window.addEventListener('hashchange', onHash);
    window.addEventListener('ff-session-expired', expired);
    return () => {abort.abort(); window.removeEventListener('hashchange', onHash); window.removeEventListener('ff-session-expired', expired);};
  }, []);
  const signedIn = (u: User) => {setCsrf(u.csrf); setUser(u);};
  const navigate = (value: string) => {location.hash = value; setRoute(value); setError('');};
  if (loading) return <div className="boot"><span className="brand-mark">F<span>F</span></span><p>Opening your workspace…</p></div>;
  if (!user) return <Login onLogin={signedIn}/>;
  const sessionId = route.startsWith('session/') ? route.slice(8) : null;
  const pageName = sessionId ? 'Training session' : route === 'studio' ? 'Instructor studio' : route === 'library' ? 'Training library' : route === 'sessions' ? 'My sessions' : 'Overview';
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#dashboard" aria-label="Fault Forge home"><span className="brand-mark">F<span>F</span></span><span>fault<span className="brand-light">forge</span><small>MAINTENANCE INTELLIGENCE</small></span></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <nav aria-label="Main navigation">
        {[['dashboard', 'Overview', LayoutDashboard], ['library', 'Training library', Boxes], ['sessions', 'My sessions', Activity]].map(([id, label, Icon]) => {
          const Glyph = Icon as typeof Activity;
          return <button key={id as string} className={route === id ? 'nav-item active' : 'nav-item'} onClick={() => navigate(id as string)}><Glyph size={19}/>{label as string}{route === id && <span className="nav-dot"/>}</button>;
        })}
        {user.role === 'instructor' && <><div className="workspace-label second">INSTRUCTOR TOOLS</div><button className={route === 'studio' ? 'nav-item active' : 'nav-item'} onClick={() => navigate('studio')}><FlaskConical size={19}/>Instructor studio</button></>}
      </nav>
      <div className="sidebar-bottom"><div className="safety-note"><ShieldCheck size={22}/><strong>Practice with purpose.</strong><p>Learn the diagnosis. Respect the safety process.</p></div>
        <div className="profile"><span className="avatar">{user.name.split(' ').map(x => x[0]).slice(0, 2).join('')}</span><div><strong>{user.name}</strong><small>{user.role === 'instructor' ? 'Training instructor' : 'Maintenance trainee'}</small></div><button className="icon-button" aria-label="Sign out" onClick={async () => {try {await api('/auth/logout', {}); setUser(null); setCsrf('');} catch(e) {setError((e as Error).message);}}}><LogOut size={17}/></button></div>
      </div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/><strong>{pageName}</strong></div><div className="topbar-right"><span className="environment"><span/>{user.demo_mode ? 'Synthetic training environment' : 'Training environment'}</span><button className="icon-button" aria-label="Show training guidance" onClick={() => setError('Training only. Review approved site procedures and obtain supervised practical assessment before working on real equipment.')}><CircleHelp size={19}/></button></div></header>
      <main>{error && <div className="notice" role="status">{error}<button onClick={() => setError('')} aria-label="Dismiss message">×</button></div>}
        {sessionId ? <TrainingSession key={sessionId} id={sessionId} onBack={() => navigate('library')}/> : route === 'studio' && user.role === 'instructor' ? <Studio/> : <Dashboard view={route} user={user} navigate={navigate}/>}
      </main>
      <footer><span>FAULT FORGE <span className="footer-divider">/</span> Evidence before assumptions.</span><span>Educational simulation · v0.1</span></footer>
    </div>
  </div>;
}

/** Sign in with entered credentials; display safe API errors and never persist the password. */
function Login({onLogin}: {onLogin: (user: User) => void}) {
  const [email, setEmail] = useState('trainee@faultforge.local');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try {onLogin(await api<User>('/auth/login', {email, password}));} catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  };
  return <div className="login-page"><div className="login-story"><a className="brand" href="#"><span className="brand-mark">F<span>F</span></span><span>fault<span className="brand-light">forge</span></span></a><div><span className="eyebrow light">THE NEXT SHIFT STARTS HERE</span><h1>Real reasoning.<br/>Safer practice.<br/><em>Stronger instincts.</em></h1><p>An evidence-led training workspace for the people who keep industry moving.</p><div className="login-features"><span><Boxes size={18}/>3 machine environments</span><span><ShieldCheck size={18}/>Safety at every step</span><span><BookOpen size={18}/>Source-grounded learning</span></div></div><span className="login-foot">CNC MACHINES <b> / </b> HYDRAULIC PRESSES <b> / </b> CONVEYOR BELTS</span></div>
    <div className="login-form-panel"><form onSubmit={submit}><span className="pill"><Sparkles size={13}/> A better way to build expertise</span><h2>Welcome to your workshop.</h2><p className="muted">Sign in to investigate, diagnose, and learn.</p><label>Email address<input autoComplete="username" type="email" required value={email} onChange={e => setEmail(e.target.value)}/></label><label>Password<input autoComplete="current-password" type="password" required minLength={12} value={password} onChange={e => setPassword(e.target.value)}/></label>{error && <div className="error" role="alert">{error}</div>}<button className="button primary wide" disabled={busy}>{busy ? 'Signing in…' : 'Enter workspace'}<ArrowRight size={18}/></button><p className="login-help">For a local setup, your generated credentials are in <strong>local-access.txt</strong> in the application folder.</p><div className="login-switch"><button type="button" onClick={() => setEmail('trainee@faultforge.local')}>Trainee account</button><span>·</span><button type="button" onClick={() => setEmail('instructor@faultforge.local')}>Instructor account</button></div></form></div></div>;
}
