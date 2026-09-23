export async function echoText(text: string, baseUrl = ''): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/echo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    throw new Error('Could not reach the API. Check that the server is running and try again.');
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error('The API returned an unreadable response. Please try again.');
  }

  if (!response.ok) {
    const message = (data as { error?: { message?: unknown } } | null)?.error?.message;
    throw new Error(typeof message === 'string' ? message : 'The request failed. Please try again.');
  }
  const result = (data as { text?: unknown } | null)?.text;
  if (typeof result !== 'string') throw new Error('The API returned an unexpected response.');
  return result;
}
