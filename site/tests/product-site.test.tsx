import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LaunchSite } from '../src/LaunchSite';

beforeEach(() => {
  import.meta.env.VITE_DEMO_URL = 'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo';
  import.meta.env.VITE_GITHUB_URL = 'https://github.com/guglxni/witness-fleet';
  window.matchMedia = vi.fn((query: string) => ({ matches: query.includes('max-width: 1180px') || query.includes('reduced-motion'), media: query, onchange: null, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(() => true) })) as unknown as typeof window.matchMedia;
});

describe('Witness Fleet product-site behaviors', () => {
  it('controls the real primary navigation and returns focus on Escape', () => {
    render(<LaunchSite />);
    const toggle = screen.getByRole('button', { name: /open navigation/i });
    const nav = document.querySelector('nav[aria-label="Primary navigation"]') as HTMLElement;
    expect(nav).toHaveAttribute('id', 'primary-links');
    expect(toggle).toHaveAttribute('aria-controls', nav.id);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('button', { name: /open navigation/i })).toHaveFocus();
    expect(document.querySelector('nav[aria-label="Primary navigation"]')).toHaveAttribute('hidden');
  });

  it('describes five evidence stages without implying a count of seven receipts', () => {
    render(<LaunchSite />);
    expect(screen.getByRole('heading', { name: /one inspectable chain/i })).toBeInTheDocument();
  });

  it('keeps a single interactive figure coupled to the evidence sequence', () => {
    render(<LaunchSite />);
    expect(screen.getAllByRole('group', { name: /interactive fleet-mechanism stage selector/i })).toHaveLength(1);
  });

  it('moves keyboard focus into the mobile menu when it opens', () => {
    render(<LaunchSite />);
    fireEvent.click(screen.getByRole('button', { name: /open navigation/i }));
    expect(screen.getByRole('link', { name: 'Start here' })).toHaveFocus();
  });

  it('pauses ambient motion without hiding the illustrated hero object', () => {
    render(<LaunchSite />);
    fireEvent.click(screen.getByRole('button', { name: /pause ambient motion/i }));
    expect(document.querySelector('.hero-art-plane img')).toBeVisible();
  });

  it('switches illustrative applications by keyboard without inventing deployment status', () => {
    render(<LaunchSite />);
    const chooser = screen.getByRole('group', { name: /illustrative application scenarios/i });
    const buttons = within(chooser).getAllByRole('button');
    expect(buttons).toHaveLength(3);
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(buttons[1]!);
    expect(buttons[1]).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('heading', { name: /warehouse exception recovery/i })).toBeInTheDocument();
    expect(screen.getByText(/integration gap/i)).toBeInTheDocument();
  });

  it('exposes a useful product model section, bounded pilot path, and no simulated contact form', () => {
    render(<LaunchSite />);
    expect(document.getElementById('value-model')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /scoped evaluation.*subscription/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /scoped evaluation.*subscription/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /request.*pilot/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name:/Opens an email draft/i })).toHaveAttribute('href', expect.stringMatching(/^mailto:/));
  });

  it('reveals FAQ answers with native keyboard-operable disclosure controls', () => {
    render(<LaunchSite />);
    const answer = screen.getByText(/configured release in this capture is scripted/i);
    const disclosure = answer.closest('details');
    expect(disclosure).not.toBeNull();
    expect(disclosure).not.toHaveAttribute('open');
    fireEvent.click(within(disclosure as HTMLElement).getByText(/was a person approving each action/i));
    expect(disclosure).toHaveAttribute('open');
    expect(answer).toBeVisible();
  });
});
