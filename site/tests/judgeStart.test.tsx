import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { JudgeStart } from '../src/JudgeStart';

const demoUrl = 'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo';
const sourceUrl = 'https://github.com/guglxni/witness-fleet';
const runtimeCommit = '51e789daf75fff7f8bb29b84523679813449aa7d';

describe('JudgeStart proof-first entry point', () => {
  it('offers the bounded run, commit-pinned runtime source, and recorded artifacts', () => {
    render(<JudgeStart demoUrl={demoUrl} sourceUrl={sourceUrl} />);
    const section = screen.getByRole('region', { name: /start here/i });

    expect(within(section).getByRole('link', { name: /run bounded simulation/i })).toHaveAttribute('href', demoUrl);
    expect(within(section).getByRole('link', { name: /inspect source-pinned graph code/i })).toHaveAttribute(
      'href', `${sourceUrl}/blob/${runtimeCommit}/src/witness_fleet/graph/store.py`,
    );
    expect(within(section).getByRole('link', { name: /watch or download film/i })).toHaveAttribute('href', '/media/launch.mp4');
    expect(within(section).getByRole('link', { name: /inspect provenance.*sanitized capture/i })).toHaveAttribute('href', '/media/provenance.json');
  });

  it('explains the five static stages and honest control-path boundaries', () => {
    render(<JudgeStart demoUrl={demoUrl} sourceUrl={sourceUrl} />);
    const section = screen.getByRole('region', { name: /start here/i });
    const stages = within(section).getByRole('list', { name: /what changes the next move/i });

    expect(within(stages).getAllByRole('listitem').map(item => item.textContent)).toEqual([
      expect.stringMatching(/recovery/i),
      expect.stringMatching(/restriction.*still gates/i),
      expect.stringMatching(/scoped configured release.*fresh courier evidence.*both required/i),
      expect.stringMatching(/travel/i),
      expect.stringMatching(/measured delivery/i),
    ]);
    expect(within(section).getByText(/this explanatory sequence is not a live request/i)).toBeInTheDocument();
    expect(within(section).getAllByText(/deterministic mission/i)).toHaveLength(2);
    expect(within(section).getByText(/centrally coordinated roles/i)).toBeInTheDocument();
    expect(within(section).getByText(/no model inference is in the control path/i)).toBeInTheDocument();
    expect(within(section).getByText(/a scoped configured release.*not human authentication/i)).toBeInTheDocument();
  });

  it('keeps the inspection walk-through a native disclosure without fetching or mutating', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(<JudgeStart demoUrl={demoUrl} sourceUrl={sourceUrl} />);
    const walkthrough = screen.getByText(/what to look for/i);
    const disclosure = walkthrough.closest('details');
    expect(disclosure).not.toBeNull();

    fireEvent.click(within(disclosure as HTMLElement).getByText(/what to look for/i));

    expect(disclosure).toHaveAttribute('open');
    expect(within(disclosure as HTMLElement).getByText(/configured demo-owner release/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
