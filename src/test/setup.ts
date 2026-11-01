import '@testing-library/jest-dom/vitest';

// Safe mock for window.fetch in Node/JSDOM for relative API calls
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  if (typeof input === 'string' && input.startsWith('/')) {
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  return nativeFetch(input, init);
};
