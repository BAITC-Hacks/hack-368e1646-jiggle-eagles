import { useState } from 'react';
import type { FormEvent } from 'react';
import { echoText } from './api';

export function App() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      setResult(await echoText(text));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-12">
      <header className="mb-8">
        <p className="mb-3 text-sm font-semibold tracking-widest text-teal-700">HACKALEM</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Connectivity test</h1>
        <p className="mt-4 leading-relaxed text-slate-600">
          Send a message to the Express API and see it echoed here.
        </p>
      </header>
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-label="Echo test">
        <form onSubmit={submit} aria-busy={loading}>
          <label htmlFor="message" className="block text-sm font-semibold text-slate-800">Message</label>
          <p id="message-help" className="mt-1 text-sm text-slate-500">1–1,000 characters. Surrounding whitespace is trimmed.</p>
          <input
            id="message"
            name="message"
            type="text"
            required
            maxLength={1000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-describedby="message-help"
            placeholder="Hello, HackAlem!"
            className="mt-4 w-full rounded-lg border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
          />
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="mt-4 rounded-lg bg-teal-700 px-5 py-3 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Sending…' : 'Send to API'}
          </button>
        </form>
        <div aria-live="polite" aria-atomic="true">
          {loading && <p className="mt-5 text-sm text-slate-600" role="status">Waiting for the API…</p>}
          {result !== null && (
            <div className="mt-6 rounded-lg border border-teal-200 bg-teal-50 p-4" role="status">
              <h2 className="text-sm font-semibold text-teal-900">API response</h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-slate-800">{result}</p>
            </div>
          )}
        </div>
        {error && <p role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      </section>
      <p className="mt-6 text-sm leading-relaxed text-slate-500">Connectivity only. No data is stored.</p>
    </main>
  );
}
