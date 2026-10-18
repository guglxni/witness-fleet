export const VALUE_LIMITS = {
  monthlyExceptions: 1_000_000,
  minutesPerIncident: 525_600,
  loadedHourlyCost: 1_000_000,
} as const;

export interface WorksheetInputs {
  monthlyExceptions: string;
  minutesPerIncident: string;
  loadedHourlyCost: string;
  operatingMonths: string;
}

export interface WorksheetValues {
  annualOperatorHours: number;
  annualLaborBurden: number;
}

export type InputKey = keyof WorksheetInputs;
export type ValidationErrors = Partial<Record<InputKey, string>>;

const INPUT_RULES: Record<Exclude<InputKey, 'operatingMonths'>, {max: number}> = {
  monthlyExceptions: {max: VALUE_LIMITS.monthlyExceptions},
  minutesPerIncident: {max: VALUE_LIMITS.minutesPerIncident},
  loadedHourlyCost: {max: VALUE_LIMITS.loadedHourlyCost},
};

export function validateInputs(inputs: WorksheetInputs): ValidationErrors {
  const errors: ValidationErrors = {};
  for (const [key, rule] of Object.entries(INPUT_RULES) as [Exclude<InputKey, 'operatingMonths'>, (typeof INPUT_RULES)[Exclude<InputKey, 'operatingMonths'>]][]) {
    const raw = inputs[key].trim();
    if (!raw) {
      errors[key] = 'Enter a value to calculate this estimate.';
      continue;
    }
    const value = Number(raw);
    if (!/^-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw)) {
      errors[key] = 'Enter a standard decimal number.';
    } else if (!Number.isFinite(value)) {
      errors[key] = 'Enter a finite number.';
    } else if (value === 0 && /[1-9]/.test(raw)) {
      errors[key] = 'Enter a value within supported numeric precision.';
    } else if (value < 0) {
      errors[key] = 'Enter zero or a positive number.';
    } else if (value > rule.max) {
      errors[key] = `Enter no more than ${rule.max.toLocaleString('en-US')}.`;
    }
  }

  const rawMonths = inputs.operatingMonths.trim();
  const months = Number(rawMonths);
  if (!rawMonths) {
    errors.operatingMonths = 'Enter the number of operating months.';
  } else if (!/^(?:\d+\.?\d*|\.\d+)$/.test(rawMonths)) {
    errors.operatingMonths = 'Enter a whole number from 1 to 12.';
  } else if (!Number.isFinite(months)) {
    errors.operatingMonths = 'Enter a finite number.';
  } else if (months === 0 && /[1-9]/.test(rawMonths)) {
    errors.operatingMonths = 'Enter a whole number from 1 to 12.';
  } else if (!Number.isInteger(months) || months < 1 || months > 12) {
    errors.operatingMonths = 'Enter a whole number from 1 to 12.';
  }
  return errors;
}

export function calculateValue(inputs: WorksheetInputs): WorksheetValues | null {
  if (Object.keys(validateInputs(inputs)).length > 0) return null;
  const annualOperatorHours = Number(inputs.monthlyExceptions) * Number(inputs.minutesPerIncident) * Number(inputs.operatingMonths) / 60;
  const annualLaborBurden = annualOperatorHours * Number(inputs.loadedHourlyCost);
  if (!Number.isFinite(annualOperatorHours) || !Number.isFinite(annualLaborBurden)) return null;
  return {annualOperatorHours, annualLaborBurden};
}

export const EMPTY_INPUTS: WorksheetInputs = {
  monthlyExceptions: '',
  minutesPerIncident: '',
  loadedHourlyCost: '',
  operatingMonths: '12',
};

export const ILLUSTRATIVE_INPUTS: WorksheetInputs = {
  monthlyExceptions: '120',
  minutesPerIncident: '15',
  loadedHourlyCost: '60',
  operatingMonths: '12',
};
