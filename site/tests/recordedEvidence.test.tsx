import {fireEvent,render,screen} from '@testing-library/react';
import {describe,expect,it,vi} from 'vitest';
import {RecordedEvidence} from '../src/RecordedEvidence';

describe('recorded evidence inspector',()=>{
  it('switches between the actual retained courier-delivery snapshot and completed snapshot',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByRole('heading',{name:/inspect the retained run/i})).toBeInTheDocument();
    expect(screen.getByText(/courier delivery · recorded snapshot/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:/final · complete/i}));
    expect(screen.getByText(/final recorded snapshot/i)).toBeInTheDocument();
    expect(screen.getAllByRole('button',{name:/copy (?:task|command) id/i}).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:/delivercourier · completed T\+4855OUTCOME_VERIFIED/i}));
    expect(screen.getAllByText('command-974485c2a0fa45909dac06e726f59722')).toHaveLength(2);
  });

  it('filters retained task and command receipts by search and robot without changing source data',()=>{
    render(<RecordedEvidence/>);
    const search=screen.getByRole('searchbox',{name:/search recorded receipts/i});
    fireEvent.change(search,{target:{value:'recovery'}});
    expect(screen.getByText('Recovery task',{selector:'.recorded-task-name'})).toBeInTheDocument();
    expect(screen.queryByText('Scout task',{selector:'.recorded-task-name'})).not.toBeInTheDocument();
    fireEvent.change(search,{target:{value:''}});
    fireEvent.click(screen.getByRole('button',{name:'Filter by courier'}));
    expect(screen.getAllByText('Courier task',{selector:'.recorded-task-name'}).length).toBeGreaterThan(0);
    expect(screen.queryByText('Scout task',{selector:'.recorded-task-name'})).not.toBeInTheDocument();
  });

  it('keeps visible copy control text in its accessible name',()=>{
    render(<RecordedEvidence/>);
    for(const button of Array.from(document.querySelectorAll<HTMLButtonElement>('.rw-copy'))){
      expect(button.textContent?.trim()).toBe('Copy ID');
      expect(button.getAttribute('aria-label')).toMatch(/^Copy ID, Copy (?:task|command|last command) ID$/);
    }
  });

  it('opens a full task ID and announces successful copying without altering the ID',async()=>{
    render(<RecordedEvidence/>);
    const search=screen.getByRole('searchbox',{name:/search recorded receipts/i});
    fireEvent.change(search,{target:{value:'courier'}});
    const row=document.querySelector('.rw-task')!;
    fireEvent.click(row.querySelector('summary')!);
    const id='fleet-demo-2e2d1556ca374d6ba2073375c8481a2e-task-courier-approach';
    expect(screen.getByText(id)).toBeInTheDocument();
    const writer=vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:writer}});
    fireEvent.click(screen.getAllByRole('button',{name:/copy task id/i})[0]!);
    expect(await screen.findByText('Copied full ID')).toBeInTheDocument();
    expect(writer).toHaveBeenCalledWith(id);
  });

  it('explains and disables comparison when the first snapshot has no previous receipt',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByRole('checkbox',{name:/compare previous snapshot/i})).toBeDisabled();
    expect(screen.getByText(/no earlier retained snapshot is available/i)).toBeInTheDocument();
    expect(screen.queryByRole('region',{name:/snapshot comparison/i})).not.toBeInTheDocument();
  });

  it('compares adjacent recorded snapshots with captured values only',()=>{
    render(<RecordedEvidence/>);
    fireEvent.click(screen.getByRole('button',{name:/final · complete/i}));
    fireEvent.click(screen.getByRole('checkbox',{name:/compare previous snapshot/i}));
    expect(screen.getByRole('region',{name:/snapshot comparison/i})).toHaveTextContent('1747→4864');
    expect(screen.getByRole('region',{name:/snapshot comparison/i})).toHaveTextContent('302→329');
    expect(screen.getByRole('region',{name:/snapshot comparison/i})).toHaveTextContent('7→7');
  });

  it('renders full related IDs with specifically labeled copy controls',()=>{
    render(<RecordedEvidence/>);
    const search=screen.getByRole('searchbox',{name:/search recorded receipts/i});
    fireEvent.change(search,{target:{value:'scout'}});
    const row=document.querySelector('.rw-task')!;
    fireEvent.click(row.querySelector('summary')!);
    const relatedCommandId='command-2a50c30e758d4732b182a85a695930ee';
    expect(screen.getAllByText(relatedCommandId)).toHaveLength(2);
    expect(screen.getAllByRole('button',{name:/copy last command id/i})).toHaveLength(3);

    fireEvent.change(search,{target:{value:''}});
    fireEvent.click(screen.getByRole('button',{name:/final · complete/i}));
    const relatedTaskId='fleet-demo-2e2d1556ca374d6ba2073375c8481a2e-task-scout-inspect';
    expect(screen.getAllByText(relatedTaskId)).toHaveLength(2);
    expect(screen.getAllByRole('button',{name:/copy task id/i}).length).toBeGreaterThan(0);
  });

  it('states from the retained release data that it was a configured demo-owner release, not human-authenticated',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByText(/recorded configured demo-owner release; not human-authenticated\./i)).toBeInTheDocument();
  });

  it('keeps all recorded workbench text at readable minimum sizes',()=>{
    render(<RecordedEvidence/>);
    const tracked=document.querySelectorAll('.recorded-evidence :not([aria-hidden="true"])');
    for(const element of tracked){
      const fontSize=parseFloat(getComputedStyle(element).fontSize);
      if(Number.isFinite(fontSize)){
        const px=fontSize<10?fontSize*16:fontSize;
        if(element.children.length===0&&element.textContent?.trim()) expect(px,element.textContent).toBeGreaterThanOrEqual(12);
      }
    }
  });

  it('distinguishes explicit zero from an unavailable unauthorized aggregate',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByText('0',{selector:'.rw-outcomes strong'})).toBeInTheDocument();
    expect(screen.getByText(/unknown · null in retained evidence/i)).toBeInTheDocument();
  });

  it('labels command completion ticks separately from snapshot observation ticks',()=>{
    render(<RecordedEvidence/>);
    expect(screen.getByText(/observed at world tick/i)).toHaveTextContent('1747');
    expect(screen.getAllByText(/completed T\+1/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:/final · complete/i}));
    expect(screen.getByText(/completed T\+4855/i)).toBeInTheDocument();
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
    expect(screen.getByRole('link',{name:/download receipt/i})).toHaveAttribute('href','/media/recorded-evidence.json');
    expect(screen.getByText(/pre-release behavior was separately verified by the pinned test contract/i)).toBeInTheDocument();
    expect(screen.getByText(/recorded evidence only.*no live database reads or actions/i)).toBeInTheDocument();
    expect(screen.getByText(/tests and ci are contract evidence, not current live evidence/i)).toBeInTheDocument();
  });
});
