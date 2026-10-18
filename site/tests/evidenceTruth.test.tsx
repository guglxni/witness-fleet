import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StorySequence } from '../src/StorySequence';
import { ProductFilmTheater } from '../src/ProductFilmTheater';

describe('recorded evidence identity and film scope', () => {
  it('distinguishes scout verification from courier verification', () => {
    render(<StorySequence phase="sensing" onPhase={() => {}} paused />);
    expect(screen.getByText(/scout verification at tick 1747.*courier verification at tick 3240/i)).toBeInTheDocument();
  });
  it('describes OUTCOME_VERIFIED as a command outcome, not a task state', () => {
    const { rerender } = render(<StorySequence phase="recovery" onPhase={() => {}} paused />);
    expect(screen.getByText(/recover command marked OUTCOME_VERIFIED at world tick 1403/i)).toBeInTheDocument();
    rerender(<StorySequence phase="delivery" onPhase={() => {}} paused />);
    expect(screen.getByText(/deliver command marked OUTCOME_VERIFIED at world tick 4855/i)).toBeInTheDocument();
  });
  it('identifies films as product context with a direct working-demo path', () => {
    render(<ProductFilmTheater />);
    expect(screen.getByRole('link', { name: /run the working simulation/i })).toHaveAttribute('href', 'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo');
    expect(screen.getByText(/no physical deployment or certification is claimed/i)).toBeInTheDocument();
  });
  it('keeps the single film tied to its production credits without old-cut controls', () => {
    const {container}=render(<ProductFilmTheater />);
    expect(container.querySelectorAll('iframe')).toHaveLength(1);
    expect(screen.getByRole('link', { name: /production credits/i })).toHaveAttribute('href', '/media/campaign/CREDITS-FALKORDB.md');
    expect(screen.queryByRole('button', { name: /original|film ii|revised film/i })).not.toBeInTheDocument();
  });
});
