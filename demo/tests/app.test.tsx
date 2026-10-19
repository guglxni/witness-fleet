import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkbenchApp } from '../src/App';
import { activeState, sceneFixture } from './fixtures';

function fakeFetch() {
  const calls: string[] = [];
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input); calls.push(url);
    if (url.endsWith('/sessions')) return new Response(JSON.stringify({ session: { status: 'active' }, state: activeState }), { status: 200 });
    if (url.endsWith('/scene')) return new Response(JSON.stringify(sceneFixture), { status: 200 });
    return new Response(JSON.stringify({}), { status: 401 });
  });
  return { fetcher, calls };
}

describe('Workbench application surface', () => {
  it('dispatches the top-camera action from the enabled Top control', async () => {
    const { fetcher } = fakeFetch();
    const top = vi.fn();
    window.addEventListener('scene-top', top);
    try {
      render(<WorkbenchApp fetcher={fetcher as typeof fetch} />);
      fireEvent.click(screen.getByRole('button', { name: 'Top view', exact: true }));
      expect(top).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener('scene-top', top);
    }
  });
  it('reattaches by read only and never bootstraps or creates on page load', async () => {
    const { fetcher, calls } = fakeFetch();
    render(<WorkbenchApp fetcher={fetcher as typeof fetch} />);
    await screen.findByText(/read-only session/i);
    expect(calls).toEqual(['/demo/v1/sessions', '/demo/v1/scene']);
    expect(calls.some((url) => url.endsWith('/bootstrap'))).toBe(false);
    expect(calls.some((url) => url.endsWith('/run'))).toBe(false);
  });

  it('shows the explicit Start control when no session exists and creates only after a click', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/sessions')) return new Response('{}', { status: 401 });
      if (url.endsWith('/bootstrap')) return new Response(JSON.stringify({ csrf_token: 'bootstrap' }), { status: 200 });
      if (url.endsWith('/scene')) return new Response(JSON.stringify(sceneFixture), { status: 200 });
      return new Response(JSON.stringify({ csrf_token: 'session-csrf', state: activeState }), { status: 201 });
    });
    render(<WorkbenchApp fetcher={fetcher as typeof fetch} />);
    await screen.findByRole('button', { name: 'Start isolated session' });
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/bootstrap'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Start isolated session' }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/sessions') && fetcher.mock.calls.length > 1)).toBe(true));
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/bootstrap'))).toHaveLength(1);
  });
});
