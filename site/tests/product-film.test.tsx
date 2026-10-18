import {expect,it} from 'vitest';
import {render,screen} from '@testing-library/react';
import {ProductFilmTheater} from '../src/ProductFilmTheater';
it('presents one user-initiated film and states the illustrative-scope boundary',()=>{
 const {container}=render(<ProductFilmTheater/>);
 expect(container.querySelectorAll('iframe')).toHaveLength(1);
 expect(container.querySelectorAll('video')).toHaveLength(0);
 expect(container.querySelector('iframe')).toHaveAttribute('src',expect.stringContaining('autoplay=0'));
 expect(container.querySelector('iframe')?.getAttribute('src')).not.toMatch(/[?&]autoplay=1(?:&|$)/);
 expect(screen.queryByRole('button',{name:/choose|original|film ii|revised film/i})).not.toBeInTheDocument();
 expect(screen.getByText(/AI concept scenes are illustrative/i)).toBeVisible();
 expect(screen.getByText(/No physical deployment or certification is claimed/i)).toBeVisible();
});
