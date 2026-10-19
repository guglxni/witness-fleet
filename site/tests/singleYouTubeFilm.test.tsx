import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {ProductFilmTheater} from '../src/ProductFilmTheater';

describe('single FalkorDB YouTube film',()=>{
 it('replaces cut selection with the requested privacy-enhanced YouTube player',()=>{
  const {container}=render(<ProductFilmTheater/>);
  const player=screen.getByTitle('Witness Fleet × FalkorDB — YouTube video player');
  expect(container.querySelectorAll('iframe')).toHaveLength(1);
  expect(container.querySelectorAll('video')).toHaveLength(0);
  expect(screen.queryByRole('group',{name:'Choose a film'})).not.toBeInTheDocument();
  expect(player).toHaveAttribute('src','https://www.youtube-nocookie.com/embed/v7P9KVyTrWY?autoplay=0&controls=1&playsinline=1&rel=0');
  expect(player).toHaveAttribute('loading','lazy');
  expect(player).toHaveAttribute('referrerpolicy','strict-origin-when-cross-origin');
  expect(player).toHaveAttribute('allowfullscreen');
  expect(screen.getByRole('link',{name:/Watch on YouTube/})).toHaveAttribute('href','https://youtu.be/v7P9KVyTrWY');
 });
});
