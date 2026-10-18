import {expect,it} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {ProductFilmTheater} from '../src/ProductFilmTheater';
it('keeps FalkorDB production credits and transcript/caption access with the single film',()=>{
 const {container}=render(<ProductFilmTheater/>);
 expect(container.querySelectorAll('iframe')).toHaveLength(1);
 expect(container.querySelectorAll('video')).toHaveLength(0);
 expect(container.querySelector('iframe')).toHaveAttribute('title','Witness Fleet × FalkorDB — YouTube video player');
 expect(screen.getByRole('link',{name:/Production credits/})).toHaveAttribute('href','/media/campaign/CREDITS-FALKORDB.md');
 fireEvent.click(screen.getByText(/Transcript & captions/i));
 expect(screen.getByText(/Imagine a parts tray/)).toBeInTheDocument();
 expect(screen.getByRole('link',{name:/English captions/})).toHaveAttribute('href','/media/campaign/product-ad-falkordb.vtt');
 expect(screen.getByRole('link',{name:/English captions/})).toHaveAttribute('download');
});
