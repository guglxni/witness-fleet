import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LaunchSite } from '../src/LaunchSite';

describe('FalkorDB implementation story', () => {
  it('shows the official FalkorDB badge and a judge-focused execution-path section', () => {
    render(<LaunchSite />);
    expect(screen.getByRole('img', { name: /FalkorDB/i })).toHaveAttribute('src', '/media/falkordb/falkordb-logo-color.svg');
    expect(screen.getByRole('heading', { name: /why FalkorDB is in the execution path/i })).toBeInTheDocument();
  });

  it('switches a local explanation with keyboard-operable capability choices', () => {
    render(<LaunchSite />);
    const selector = screen.getByRole('group', { name: /FalkorDB capabilities/i });
    const choices = within(selector).getAllByRole('button');
    expect(choices).toHaveLength(4);
    expect(choices[0]).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(choices[2]!);
    expect(choices[2]).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(/version-fenced/i)).toBeInTheDocument();
    expect(screen.getByText(/explanatory view only/i)).toBeInTheDocument();
  });

  it('links each displayed reservation query to its exact source range', () => {
    render(<LaunchSite />);
    fireEvent.click(screen.getByRole('button', { name: /Shared fleet context/i }));
    expect(screen.getByRole('link', { name: /read_resource_claims/i })).toHaveAttribute('href', expect.stringContaining('store.py#L558-L563'));
  });

  it('renders branching, source-backed graph relationships and a sourced read-only Cypher excerpt', () => {
    render(<LaunchSite />);
    const section = document.getElementById('falkordb');
    expect(section).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Cypher reads/i }));
    expect(within(section as HTMLElement).getAllByText(/SUPPORTED_BY/i).length).toBeGreaterThan(0);
    expect(within(section as HTMLElement).getAllByText(/REVISION_OF/i).length).toBeGreaterThan(0);
    expect(within(section as HTMLElement).getByText(/Explanatory view only\. Read excerpts use FalkorDB ro_query/i)).toBeInTheDocument();
    expect(within(section as HTMLElement).getByRole('link', { name: /read_task_claims/i })).toHaveAttribute('href', expect.stringContaining('github.com/guglxni/witness-fleet/blob/51e789daf75fff7f8bb29b84523679813449aa7d/src/witness_fleet/graph/store.py#L551-L556'));
    expect(within(section as HTMLElement).getByText(/GraphRAG-SDK adapter is an isolated synthetic corpus lane/i)).toBeInTheDocument();
  });
});
