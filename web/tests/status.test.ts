import { describe, expect, it } from 'vitest';
import { decisionStateTone } from '../src/state';

describe('command outcome distinctions', () => {
  it('does not render unknown verification as success', () => {
    expect(decisionStateTone('OUTCOME_VERIFIED_UNKNOWN')).toBe('unresolved');
  });

  it.each(['UNVERIFIED', 'NOT_VERIFIED', 'NOT VERIFIED', 'VERIFIED_PENDING', 'UNVERIFIED_OUTCOME', 'verified-ish'])('never grants a verified tone to %s', (status) => {
    expect(decisionStateTone(status)).not.toBe('verified');
  });

  it('keeps controller completion separate from verified outcome', () => {
    expect(decisionStateTone('CONTROLLER_DONE')).toBe('in-progress');
    expect(decisionStateTone('OUTCOME_VERIFIED')).toBe('verified');
  });
});
