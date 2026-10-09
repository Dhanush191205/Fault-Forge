let csrfToken = '';
export const API_BASE = import.meta.env.VITE_API_URL || '/api';

/** Store the current session's anti-forgery token in memory; accepts a server-issued token. */
export function setCsrf(value: string) { csrfToken = value; }

/** Call the same-origin API and return typed JSON; throw only a safe public error message. */
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'include', signal,
    headers: { 'Content-Type': 'application/json', ...(body === undefined ? {} : {'X-CSRF-Token': csrfToken}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const value = await response.json().catch(() => null);
  if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event('ff-session-expired'));
  if (!response.ok) throw new Error(value?.error?.message || 'The service is unavailable. Please try again.');
  return value as T;
}

/** Produce a collision-resistant idempotency key for a single user operation. */
export function requestKey() { return crypto.randomUUID(); }
