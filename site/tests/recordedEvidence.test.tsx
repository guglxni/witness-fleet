import {fireEvent,render,screen} from '@testing-library/react';
import {describe,expect,it} from 'vitest';
import {RecordedEvidence} from '../src/RecordedEvidence';

describe('recorded evidence inspector',()=>{
  it('switches between the actual retained courier-delivery snapshot and completed snapshot',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByRole('heading',{name:/recorded run evidence/i})).toBeInTheDocument();
    expect(screen.getByText(/courier delivery · recorded snapshot/i)).toBeInTheDocument();
    expect(screen.getByText('fleet-demo-2e2d1556ca374d6ba2073375c8481a2e-task-courier-approach')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:/show final complete snapshot/i}));
    expect(screen.getByText(/complete · final recorded snapshot/i)).toBeInTheDocument();
    expect(screen.getByText('command-974485c2a0fa45909dac06e726f59722')).toBeInTheDocument();
  });

  it('distinguishes explicit zero from an unavailable unauthorized aggregate',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByText('0',{selector:'.recorded-metric-value'})).toBeInTheDocument();
    expect(screen.getByText(/not recorded in retained evidence/i)).toBeInTheDocument();
  });

  it('labels command completion ticks separately from snapshot observation ticks',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByText(/snapshot observed at world tick/i)).toHaveTextContent('1747');
    fireEvent.click(screen.getByRole('button',{name:/show final complete snapshot/i}));
    expect(screen.getAllByText(/command completion tick/i).length).toBeGreaterThan(0);
    expect(screen.getByText('4855')).toBeInTheDocument();
  });

  it('links the pinned test contract to its valid commit',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByRole('link',{name:'pinned test contract'})).toHaveAttribute(
      'href',
      'https://github.com/guglxni/witness-fleet/blob/51e789daf75fff7f8bb29b84523679813449aa7d/tests/e2e/test_hosted_simulation.py',
    );
  });

  it('provides a sanitized downloadable receipt and honest evidence boundary',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByRole('link',{name:/download sanitized evidence json/i})).toHaveAttribute('href','/media/recorded-evidence.json');
    expect(screen.getByText(/pre-release behavior was separately verified by the pinned test contract/i)).toBeInTheDocument();
    expect(screen.getByText(/recorded evidence only.*no live database reads or actions/i)).toBeInTheDocument();
    expect(screen.getByText(/tests and ci are contract evidence, not current live evidence/i)).toBeInTheDocument();
  });
});
