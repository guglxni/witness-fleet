import type { FleetProjection, IncidentRequest } from '../api-contract';
import { isFleetProjection } from './state';

export type Health = { process: string; dispatch_ready: boolean; dependencies?: { status?: string } };
export type ApiFailure = { status: number; detail: string };

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === 'object' && 'detail' in body) {
        const value: unknown = body.detail;
        detail = value && typeof value === 'object' && 'code' in value
          ? String(value.code)
          : String(value);
      }
    } catch { /* the status remains useful when the body is not JSON */ }
    throw { status: response.status, detail: `HTTP ${response.status}: ${detail}` } satisfies ApiFailure;
  }
  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<Health> {
  return json<Health>('/api/health');
}

export async function getState(): Promise<FleetProjection | null> {
  try {
    const value: unknown = await json<unknown>('/api/state');
    return isFleetProjection(value) ? value : null;
  } catch (error) {
    if (error && typeof error === 'object' && 'status' in error && (error.status === 404 || error.status === 503)) return null;
    throw error;
  }
}

export async function postIncident(body: IncidentRequest): Promise<FleetProjection> {
  const result: unknown = await json<unknown>('/api/incidents', { method: 'POST', body: JSON.stringify(body) });
  if (!isFleetProjection(result)) throw new Error('The API returned an invalid fleet projection.');
  return result;
}

export async function postControl(path: string, body: Record<string, unknown>): Promise<FleetProjection> {
  const result: unknown = await json<unknown>(path, { method: 'POST', body: JSON.stringify(body) });
  if (!isFleetProjection(result)) throw new Error('The API returned an invalid fleet projection.');
  return result;
}
