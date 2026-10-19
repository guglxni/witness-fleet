import { fireEvent, render, screen, within } from '@testing-library/react';
import {describe,expect,it,vi} from 'vitest';
import {LaunchSite} from '../src/LaunchSite';
import {FalkorDBSection} from '../src/FalkorDBSection';

describe('FalkorDB implementation story', () => {
  it('shows the official FalkorDB badge and a judge-focused execution-path section', () => {
    render(<LaunchSite />);
    expect(screen.getByRole('img', { name: /FalkorDB/i })).toHaveAttribute('src', '/media/falkordb/falkordb-logo-color.svg');
    expect(screen.getByRole('heading', { name: /why FalkorDB is in the execution path/i })).toBeInTheDocument();
  });

  it('selects semantic schema relationships and exposes exact edge direction and meaning',()=>{
    render(<FalkorDBSection/>);
    const edge=screen.getByRole('button',{name:/SUPPORTED_BY relationship/i});
    fireEvent.click(edge);
    expect(screen.getByRole('complementary',{name:/selected schema detail/i})).toHaveTextContent('Decision');
    expect(screen.getByRole('complementary',{name:/selected schema detail/i})).toHaveTextContent('EvidenceSpan');
    expect(screen.getByRole('complementary',{name:/selected schema detail/i})).toHaveTextContent('Decision → EvidenceSpan');
  });

  it('selects every semantic schema node and relationship by keyboard',()=>{
    render(<FalkorDBSection/>);
    const release=screen.getByRole('button',{name:/RELEASE EVENTRelease/});
    release.focus();
    expect(release).toHaveFocus();
    fireEvent.click(release);
    expect(release).toHaveAttribute('aria-pressed','true');
    expect(screen.getByRole('complementary',{name:/selected schema detail/i})).toHaveTextContent('A release event that lifts a restriction');
    const approved=screen.getByRole('button',{name:/APPROVED_BY relationship Release to Owner/i});
    approved.focus();
    expect(approved).toHaveFocus();
    fireEvent.click(approved);
    expect(approved).toHaveAttribute('aria-pressed','true');
    const detail=screen.getByRole('complementary',{name:/selected schema detail/i});
    expect(detail).toHaveTextContent('Release → Owner');
    expect(detail).toHaveTextContent('The release identifies the approving owner.');
    expect(within(detail).getByRole('link',{name:/view pinned schema source/i})).toHaveAttribute('href',expect.stringContaining('store.py#L48-L96'));
    expect(screen.getByRole('button',{name:/IMPOSES relationship Decision to Restriction/i})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/APPLIES_TO relationship Restriction to Corridor/i})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/OWNED_BY relationship Decision to Owner/i})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/SUPPORTED_BY relationship Decision to EvidenceSpan/i})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/IN_REVISION relationship EvidenceSpan to Revision/i})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/REVISION_OF relationship Revision to Source/i})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/LIFTS relationship Release to Restriction/i})).toBeInTheDocument();
  });

  it('copies the source-pinned schema excerpt and toggles wrapped code without network access',async()=>{
    render(<FalkorDBSection/>);
    const writer=vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:writer}});
    fireEvent.click(screen.getByRole('button',{name:/copy excerpt/i}));
    expect(await screen.findByText(/copied schema excerpt/i)).toBeInTheDocument();
    expect(writer).toHaveBeenCalledWith(expect.stringContaining('Decision -[:IMPOSES]-> Restriction'));
    const wrap=screen.getByRole('button',{name:/wrap lines/i});
    fireEvent.click(wrap);
    expect(screen.getByRole('button',{name:/disable wrap/i})).toHaveAttribute('aria-pressed','true');
    expect(document.querySelector('.fdb-code-window')).toHaveClass('is-wrapped');
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
