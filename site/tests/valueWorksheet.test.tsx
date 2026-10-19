import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {ValueWorksheet} from '../src/ValueWorksheet';

const readBlob = (blob: Blob) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result));
  reader.onerror = () => reject(reader.error);
  reader.readAsText(blob);
});

afterEach(() => vi.restoreAllMocks());

describe('ValueWorksheet', () => {
  it('starts blank except for 12 operating months and explains what it measures', () => {
    render(<ValueWorksheet />);
    expect(screen.getByRole('spinbutton', {name: /monthly exception count/i})).toHaveValue(null);
    expect(screen.getByRole('spinbutton', {name: /minutes per incident/i})).toHaveValue(null);
    expect(screen.getByRole('spinbutton', {name: /loaded labor cost/i})).toHaveValue(null);
    expect(screen.getByRole('spinbutton', {name: /operating months per year/i})).toHaveValue(12);
    expect(screen.getAllByText(/manual handling labor burden/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/not savings, roi/i)).toBeInTheDocument();
    expect(screen.getByRole('button', {name: /download assumptions worksheet/i})).toBeDisabled();
  });

  it('loads only clearly hypothetical inputs and reports the arithmetic as baseline burden', () => {
    render(<ValueWorksheet />);
    fireEvent.click(screen.getByRole('button', {name: /load illustrative inputs/i}));
    expect(screen.getByRole('spinbutton', {name: /monthly exception count/i})).toHaveValue(120);
    expect(screen.getByRole('spinbutton', {name: /minutes per incident/i})).toHaveValue(15);
    expect(screen.getByRole('spinbutton', {name: /loaded labor cost/i})).toHaveValue(60);
    expect(screen.getByText('360')).toBeInTheDocument();
    expect(screen.getByText('$21,600.00')).toBeInTheDocument();
    expect(screen.getAllByText('$21,600.00')).toHaveLength(1);
    expect(screen.getByRole('status')).toHaveTextContent(/scenario estimate from your inputs/i);
  });

  it('keeps invalid values visible, explains errors, and withholds the result', () => {
    render(<ValueWorksheet />);
    fireEvent.change(screen.getByRole('spinbutton', {name: /monthly exception count/i}), {target: {value: '-1'}});
    fireEvent.change(screen.getByRole('spinbutton', {name: /minutes per incident/i}), {target: {value: '10'}});
    fireEvent.change(screen.getByRole('spinbutton', {name: /loaded labor cost/i}), {target: {value: '50'}});
    fireEvent.blur(screen.getByRole('spinbutton', {name: /monthly exception count/i}));
    expect(screen.getByRole('spinbutton', {name: /monthly exception count/i})).toHaveValue(-1);
    expect(screen.getByText(/zero or a positive number/i)).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/result withheld/i);
    expect(screen.getByRole('button', {name: /download assumptions worksheet/i})).toBeDisabled();
  });

  it('resets assumptions and results to the blank starting state', () => {
    render(<ValueWorksheet />);
    fireEvent.click(screen.getByRole('button', {name: /load illustrative inputs/i}));
    fireEvent.click(screen.getByRole('button', {name: /reset worksheet/i}));
    expect(screen.getByRole('spinbutton', {name: /monthly exception count/i})).toHaveValue(null);
    expect(screen.getByRole('spinbutton', {name: /minutes per incident/i})).toHaveValue(null);
    expect(screen.getByRole('spinbutton', {name: /loaded labor cost/i})).toHaveValue(null);
    expect(screen.getByRole('spinbutton', {name: /operating months per year/i})).toHaveValue(12);
    expect(screen.getByText(/enter all four assumptions/i)).toBeInTheDocument();
  });

  it('downloads a local JSON worksheet with assumptions, formula and caveat', async () => {
    let downloadedBlob: Blob | undefined;
    vi.spyOn(URL, 'createObjectURL').mockImplementation((object) => {
      downloadedBlob = object as Blob;
      return 'blob:worksheet-test';
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<ValueWorksheet />);
    fireEvent.click(screen.getByRole('button', {name: /load illustrative inputs/i}));
    fireEvent.click(screen.getByRole('button', {name: /download assumptions worksheet/i}));

    await waitFor(() => expect(downloadedBlob).toBeDefined());
    const payload = JSON.parse(await readBlob(downloadedBlob as Blob));
    expect(payload.assumptions).toEqual({monthlyExceptions: 120, minutesPerIncident: 15, loadedHourlyCostUsd: 60, operatingMonths: 12});
    expect(payload.results).toEqual({annualOperatorHours: 360, annualManualHandlingLaborBurdenUsd: 21600});
    expect(payload.formula).toMatch(/Monthly exceptions × minutes per incident × operating months ÷ 60/);
    expect(payload.disclaimer).toMatch(/not savings, ROI, or a product performance claim/i);
    expect(URL.createObjectURL).toHaveBeenCalledOnce();
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce();
  });
});
