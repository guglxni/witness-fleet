import {useState} from 'react';
import {
  calculateValue,
  EMPTY_INPUTS,
  ILLUSTRATIVE_INPUTS,
  validateInputs,
  VALUE_LIMITS,
  type InputKey,
  type WorksheetInputs,
} from './valueModel';
import './value-worksheet.css';

const FIELD_META: Array<{
  key: InputKey;
  label: string;
  unit: string;
  helper: string;
  min: number;
  max: number;
  step: number | 'any';
}> = [
  {key: 'monthlyExceptions', label: 'Monthly exception count', unit: 'incidents / month', helper: 'How many exceptions require manual review or coordination in a typical month?', min: 0, max: VALUE_LIMITS.monthlyExceptions, step: 'any'},
  {key: 'minutesPerIncident', label: 'Minutes per incident', unit: 'minutes / incident', helper: 'Average operator time spent on each exception, using your own estimate.', min: 0, max: VALUE_LIMITS.minutesPerIncident, step: 'any'},
  {key: 'loadedHourlyCost', label: 'Loaded labor cost', unit: 'USD / hour', helper: 'Your estimated loaded hourly labor cost in US dollars.', min: 0, max: VALUE_LIMITS.loadedHourlyCost, step: 'any'},
  {key: 'operatingMonths', label: 'Operating months per year', unit: 'months / year', helper: 'Choose a whole number from 1 to 12.', min: 1, max: 12, step: 1},
];

const FORMULA = 'Monthly exceptions × minutes per incident × operating months ÷ 60';
const DISCLAIMER = 'This worksheet estimates manual handling labor burden from user-entered assumptions only. It is not savings, ROI, or a product performance claim.';
const EXCLUSIONS = 'Excludes software and integration costs, downtime, process impacts, safety costs, and any assumed reduction in incidents or handling time.';
const numberFormat = new Intl.NumberFormat('en-US', {maximumFractionDigits: 2});
const currencyFormat = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', maximumFractionDigits: 2});

function createWorksheetJson(inputs: WorksheetInputs) {
  const result = calculateValue(inputs);
  if (!result) return null;
  return {
    title: 'Witness Fleet — Manual Exception-Handling Burden Worksheet',
    worksheetType: 'user-assumption scenario estimate',
    assumptions: {
      monthlyExceptions: Number(inputs.monthlyExceptions),
      minutesPerIncident: Number(inputs.minutesPerIncident),
      loadedHourlyCostUsd: Number(inputs.loadedHourlyCost),
      operatingMonths: Number(inputs.operatingMonths),
    },
    formula: `${FORMULA}; annual labor burden = annual operator-hours × loaded hourly labor cost`,
    results: {annualOperatorHours: result.annualOperatorHours, annualManualHandlingLaborBurdenUsd: result.annualLaborBurden},
    exclusions: EXCLUSIONS,
    disclaimer: DISCLAIMER,
  };
}

export function ValueWorksheet() {
  const [inputs, setInputs] = useState<WorksheetInputs>(EMPTY_INPUTS);
  const [touched, setTouched] = useState<Partial<Record<InputKey, boolean>>>({});
  const errors = validateInputs(inputs);
  const result = calculateValue(inputs);
  const hasInteracted = Object.keys(touched).length > 0;
  const visibleErrors = Object.fromEntries(Object.entries(errors).filter(([key]) => touched[key as InputKey])) as typeof errors;

  const updateInput = (key: InputKey, value: string) => {
    setInputs((current) => ({...current, [key]: value}));
    setTouched((current) => ({...current, [key]: true}));
  };
  const resetWorksheet = () => {
    setInputs(EMPTY_INPUTS);
    setTouched({});
  };
  const downloadWorksheet = () => {
    const worksheet = createWorksheetJson(inputs);
    if (!worksheet) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(worksheet, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'witness-fleet-value-worksheet.json';
    link.click();
    URL.revokeObjectURL(url);
  };

  let statusMessage = 'Enter all four assumptions to see a scenario estimate.';
  if (hasInteracted && Object.keys(errors).length > 0) statusMessage = 'Result withheld: correct the highlighted inputs. No estimate is shown for incomplete or invalid assumptions.';
  else if (result) statusMessage = `Scenario estimate from your inputs: ${currencyFormat.format(result.annualLaborBurden)} annual manual handling labor burden and ${numberFormat.format(result.annualOperatorHours)} operator-hours per year. This is a baseline, not a prediction or savings claim.`;

  return (
    <section className="value-worksheet" aria-labelledby="value-worksheet-title">
      <div className="value-worksheet__eyebrow">LOCAL WORKSHEET <span>— YOUR ASSUMPTIONS ONLY</span></div>
      <div className="value-worksheet__intro">
        <div>
          <h2 id="value-worksheet-title">Put a number to the manual work.</h2>
          <p className="value-worksheet__dek">Estimate the annual operator time and labor burden associated with manually handling fleet exceptions. This is a baseline exposure worksheet—not a product benefit calculator.</p>
        </div>
        <p className="value-worksheet__disclaimer">{DISCLAIMER}</p>
        <p className="value-worksheet__claim-boundary">Manual handling burden only. Not ROI or savings.</p>
      </div>

      <div className="value-worksheet__workspace">
        <div className="value-worksheet__assumptions" aria-label="Worksheet assumptions">
          <div className="value-worksheet__section-heading"><span>01 / INPUTS</span><span>Use local estimates</span></div>
          {FIELD_META.map((field, index) => {
            const errorId = `value-worksheet-${field.key}-error`;
            const helperId = `value-worksheet-${field.key}-help`;
            const error = visibleErrors[field.key];
            return (
              <div className="value-worksheet__field" key={field.key}>
                <label htmlFor={`value-worksheet-${field.key}`}>
                  <span className="value-worksheet__field-index">0{index + 1}</span>
                  <span className="value-worksheet__field-copy"><span className="value-worksheet__field-name">{field.label}</span><span className="value-worksheet__field-unit">{field.unit}</span></span>
                </label>
                <input id={`value-worksheet-${field.key}`} type="number" inputMode="decimal" min={field.min} max={field.max} step={field.step} value={inputs[field.key]} aria-invalid={Boolean(error)} aria-describedby={`${helperId}${error ? ` ${errorId}` : ''}`} onChange={(event) => updateInput(field.key, event.currentTarget.value)} onBlur={() => setTouched((current) => ({...current, [field.key]: true}))} />
                <p className="value-worksheet__field-help" id={helperId}>{field.helper}</p>
                {error && <p className="value-worksheet__field-error" id={errorId}>{error}</p>}
              </div>
            );
          })}
          <div className="value-worksheet__actions">
            <button className="value-worksheet__button value-worksheet__button--primary" type="button" onClick={() => {setInputs(ILLUSTRATIVE_INPUTS); setTouched({});}}>Load illustrative inputs</button>
            <button className="value-worksheet__button value-worksheet__button--quiet" type="button" onClick={resetWorksheet}>Reset worksheet</button>
          </div>
          <p className="value-worksheet__hypothetical">Illustration only: 120 exceptions × 15 minutes × $60/hour. These values are hypothetical—not customer data or a forecast.</p>
        </div>

        <div className="value-worksheet__output" aria-label="Calculated manual handling burden">
          <div className="value-worksheet__section-heading"><span>02 / ANNUAL BASELINE</span><span>Derived from inputs</span></div>
          <div className="value-worksheet__result" aria-live="polite" aria-atomic="true" aria-label="Annual baseline result">
            {result ? <>
              <p className="value-worksheet__result-label">Manual handling labor burden</p>
              <p className="value-worksheet__result-cost">{currencyFormat.format(result.annualLaborBurden)}</p>
              <div className="value-worksheet__hours"><strong>{numberFormat.format(result.annualOperatorHours)}</strong><span>operator-hours / year</span></div>
              <p className="value-worksheet__result-note">Annualized using {inputs.operatingMonths} operating months. Not avoided cost or savings.</p>
            </> : <>
              <p className="value-worksheet__result-label">Manual handling labor burden</p>
              <p className="value-worksheet__result-cost value-worksheet__result-cost--empty">—</p>
              <div className="value-worksheet__hours value-worksheet__hours--empty"><strong>—</strong><span>operator-hours / year</span></div>
              <p className="value-worksheet__result-note">Complete valid assumptions; no values are inferred.</p>
            </>}
          </div>
          <p className="value-worksheet__live-message" aria-live="polite" role="status">{statusMessage}</p>
          <div className="value-worksheet__formula"><span>FORMULA</span><p>{FORMULA} = annual operator-hours</p><p>Annual operator-hours × loaded labor cost = annual manual handling labor burden</p></div>
          <div className="value-worksheet__exclusions"><span>OUT OF SCOPE</span><p>{EXCLUSIONS}</p></div>
          <button className="value-worksheet__button value-worksheet__button--download" type="button" onClick={downloadWorksheet} disabled={!result}>Download assumptions worksheet <span aria-hidden="true">↓</span></button>
          <p className="value-worksheet__privacy">The JSON file is created in this browser only. Inputs are not sent over a network or saved by this worksheet.</p>
        </div>
      </div>
    </section>
  );
}
