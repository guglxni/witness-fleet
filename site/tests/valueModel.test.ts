import {describe, expect, it} from 'vitest';
import {calculateValue, validateInputs, type WorksheetInputs} from '../src/valueModel';

const validInputs: WorksheetInputs = {
  monthlyExceptions: '120',
  minutesPerIncident: '15',
  loadedHourlyCost: '60',
  operatingMonths: '12',
};

describe('value worksheet model', () => {
  it('calculates annual operator-hours and manual handling labor burden from inputs', () => {
    expect(calculateValue(validInputs)).toEqual({annualOperatorHours: 360, annualLaborBurden: 21600});
  });

  it('accepts zero as a real input without inventing a positive estimate', () => {
    expect(calculateValue({...validInputs, monthlyExceptions: '0'})).toEqual({annualOperatorHours: 0, annualLaborBurden: 0});
  });

  it('rejects blank, NaN, and positive or negative infinity inputs', () => {
    for (const bad of ['', '   ', 'NaN', 'Infinity', '-Infinity']) {
      expect(calculateValue({...validInputs, monthlyExceptions: bad})).toBeNull();
      expect(validateInputs({...validInputs, monthlyExceptions: bad}).monthlyExceptions).toBeTruthy();
    }
  });

  it('rejects negative, over-limit, and exponent-overflow values', () => {
    for (const bad of ['-1', '1000001', '1e309']) {
      expect(calculateValue({...validInputs, loadedHourlyCost: bad})).toBeNull();
      expect(validateInputs({...validInputs, loadedHourlyCost: bad}).loadedHourlyCost).toBeTruthy();
    }
  });

  it('rejects non-decimal number syntax and bounded months outside 1–12', () => {
    expect(calculateValue({...validInputs, monthlyExceptions: '0x10'})).toBeNull();
    for (const months of ['0', '13', '1.5', '1e1', '']) {
      expect(calculateValue({...validInputs, operatingMonths: months})).toBeNull();
      expect(validateInputs({...validInputs, operatingMonths: months}).operatingMonths).toBeTruthy();
    }
  });

  it('accepts valid decimal and fractional assumptions', () => {
    expect(calculateValue({...validInputs, monthlyExceptions: '0.5', minutesPerIncident: '1.5', operatingMonths: '6'})).toEqual({
      annualOperatorHours: 0.075,
      annualLaborBurden: 4.5,
    });
  });
});
