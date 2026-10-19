import {fireEvent, render, screen, within} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {LaunchSite} from '../src/LaunchSite';

describe('site navigation workbench',()=>{
 it('opens a keyboard-accessible section finder and filters real destinations',()=>{
  render(<LaunchSite/>);
  fireEvent.click(screen.getByRole('button',{name:'Find a section'}));
  const dialog=screen.getByRole('dialog',{name:'Explore Witness Fleet'});
  const search=within(dialog).getByRole('searchbox',{name:'Search sections'});
  fireEvent.change(search,{target:{value:'evidence'}});
  expect(within(dialog).getByRole('link',{name:/Recorded evidence/})).toHaveAttribute('href','#recorded-evidence');
  expect(within(dialog).queryByRole('link',{name:/Applications/})).not.toBeInTheDocument();
  fireEvent.change(search,{target:{value:'zz-no-results'}});
  expect(within(dialog).getByText('No matching section. Try graph, evidence, or film.')).toBeInTheDocument();
 });
 it('restores trigger focus when the shortcut closes a focused result',()=>{
  render(<LaunchSite/>);
  const trigger=screen.getByRole('button',{name:'Find a section'});
  fireEvent.click(trigger);
  screen.getByRole('link',{name:/Recorded evidence/}).focus();
  fireEvent.keyDown(document,{key:'k',ctrlKey:true});
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
 });
 it('provides a keyboard shortcut without intercepting input editing',()=>{
  render(<LaunchSite/>);
  fireEvent.keyDown(document,{key:'k',ctrlKey:true});
  expect(screen.getByRole('dialog',{name:'Explore Witness Fleet'})).toBeInTheDocument();
  fireEvent.keyDown(document,{key:'Escape'});
  expect(screen.queryByRole('dialog',{name:'Explore Witness Fleet'})).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Find a section'})).toHaveFocus();
 });
});
