import { createElement } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SceneFallback } from '../src/SceneView';
import { sceneFixture } from './fixtures';

describe('SVG scene fallback', () => {
  it('zooms in and out and resets its 2D viewBox', () => {
    render(createElement(SceneFallback, { scene: sceneFixture, selectedId: null, onSelect: vi.fn(), showFacility: true, showSites: true, wireframe: false }));
    const svg = screen.getByRole('img', { name: /2d top projection/i });
    expect(svg).toHaveAttribute('viewBox', '0 0 700 420');
    fireEvent(window, new CustomEvent('scene-zoom', { detail: 1 }));
    expect(svg.getAttribute('viewBox')).not.toBe('0 0 700 420');
    fireEvent(window, new CustomEvent('scene-zoom', { detail: -1 }));
    expect(svg).toHaveAttribute('viewBox', '0 0 700 420');
    fireEvent(window, new Event('scene-zoom'));
    expect(svg).toHaveAttribute('viewBox', '0 0 700 420');
    fireEvent(window, new CustomEvent('scene-zoom', { detail: 1 }));
    fireEvent(window, new Event('scene-reset'));
    expect(svg).toHaveAttribute('viewBox', '0 0 700 420');
  });

  it('describes 2D top-view footprints and does not claim wireframe rendering', () => {
    const { container } = render(createElement(SceneFallback, { scene: sceneFixture, selectedId: null, onSelect: vi.fn(), showFacility: true, showSites: true, wireframe: true }));
    expect(container.querySelector('[data-object-id="scout_chassis"] title')?.textContent).toMatch(/top-view footprint approximation/i);
    expect(container.querySelector('[data-object-id="corridor_south_wall"] title')?.textContent).not.toMatch(/wireframe/i);
  });
});
