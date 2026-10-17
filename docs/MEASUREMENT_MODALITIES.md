# Native command-effect measurement contract

`Observation.visibility` preserves the source ray sensor's measured visibility. It must never be promoted to visible merely because a command finished. Clearance and release verification still require visible, fresh optical evidence.

Command outcomes are different measurements:

- `inspected`: visible actor-owned ray sample is mandatory.
- `obstruction_moved`: exact native command receipt, positive actuator contact count and measured displacement meeting the exact command target. Optical clearance is not inferred.
- `arrived`: exact native command receipt plus ten consecutive measured chassis poses, current tick, configured timestep, target error <0.05m, max speed <=0.01m/s and drift <=0.01m.
- `delivered`: arrived stability plus current observed parcel ID/pose agreeing with the same native measured delivery postcondition. Current parcel return, zone geometry and height must validate. Optical corridor clearance remains independent.

For an insufficient optical ray sample, outcome admission must validate the entire applicable native measurement contract, including exact command ID and canonical receipt hash, rather than waive visibility globally. Existing optical/S0 observations with insufficient visibility remain invalid. All records remain command- and episode-bound, immutable, retained, and CAS-checked. No field supplied through the operator HTTP interface can provide physical evidence.

This is a synthetic simulation evidence boundary, not hardware certification or protection against malicious code running inside the trusted simulator process.
