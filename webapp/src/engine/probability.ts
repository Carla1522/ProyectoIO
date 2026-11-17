// ─── Probability Calculations (CLT-based PERT) ──────────────────────────────
// Normal CDF / inverse CDF without external dependencies, plus project
// probability-of-completion helpers.

import type { CPMResult, ProbabilityResult } from '../types';

// ─── Normal CDF via error-function approximation ─────────────────────────────

/**
 * Approximation of the error function erf(x).
 * Uses Abramowitz & Stegun formula 7.1.26 (max error ≈ 1.5 × 10⁻⁷).
 */
function erf(x: number): number {
  const sign = x >= 0 ? 1 : -1;
  const t = 1 / (1 + 0.3275911 * Math.abs(x));
  const poly =
    t *
    (0.254829592 +
      t *
        (-0.284496736 +
          t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
  return sign * (1 - poly * Math.exp(-x * x));
}

/**
 * Standard normal cumulative distribution function Φ(z).
 * P(Z ≤ z) for Z ~ N(0,1).
 */
export function normalCDF(z: number): number {
  return 0.5 * (1 + erf(z / Math.SQRT2));
}

// ─── Inverse normal CDF (Acklam's approximation) ────────────────────────────

/**
 * Returns z such that Φ(z) = p for 0 < p < 1.
 * Uses Peter Acklam's rational approximation (max |ε| ≈ 1.15 × 10⁻⁹).
 */
export function inverseCDF(p: number): number {
  if (p <= 0) return -Infinity;
  if (p >= 1) return Infinity;
  if (p === 0.5) return 0;

  // Coefficients
  const a1 = -3.969683028665376e1;
  const a2 = 2.209460984245205e2;
  const a3 = -2.759285104469687e2;
  const a4 = 1.383577518672690e2;
  const a5 = -3.066479806614716e1;
  const a6 = 2.506628277459239e0;

  const b1 = -5.447609879822406e1;
  const b2 = 1.615858368580409e2;
  const b3 = -1.556989798598866e2;
  const b4 = 6.680131188771972e1;
  const b5 = -1.328068155288572e1;

  const c1 = -7.784894002430293e-3;
  const c2 = -3.223964580411365e-1;
  const c3 = -2.400758277161838e0;
  const c4 = -2.549732539343734e0;
  const c5 = 4.374664141464968e0;
  const c6 = 2.938163982698783e0;

  const d1 = 7.784695709041462e-3;
  const d2 = 3.224671290700398e-1;
  const d3 = 2.445134137142996e0;
  const d4 = 3.754408661907416e0;

  const pLow = 0.02425;
  const pHigh = 1 - pLow;

  let q: number;
  let r: number;
  let z: number;

  if (p < pLow) {
    // Rational approximation for lower region
    q = Math.sqrt(-2 * Math.log(p));
    z =
      (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) /
      ((((d1 * q + d2) * q + d3) * q + d4) * q + 1);
  } else if (p <= pHigh) {
    // Rational approximation for central region
    q = p - 0.5;
    r = q * q;
    z =
      ((((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6) * q) /
      (((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1);
  } else {
    // Rational approximation for upper region
    q = Math.sqrt(-2 * Math.log(1 - p));
    z =
      -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) /
      ((((d1 * q + d2) * q + d3) * q + d4) * q + 1);
  }

  return z;
}

// ─── Project probability helpers ─────────────────────────────────────────────

/**
 * Probability that the project finishes by the given deadline.
 * Uses CLT: Z = (deadline − μ) / σ, then Φ(Z).
 */
export function probabilityOfSuccess(
  cpm: CPMResult,
  deadline: number,
): ProbabilityResult {
  const mu = cpm.duration;
  const sigma = cpm.sigma;

  // Edge case: zero variance → deterministic project
  if (sigma === 0) {
    return {
      z: deadline >= mu ? Infinity : -Infinity,
      probability: deadline >= mu ? 1 : 0,
      deadline,
      expectedDuration: mu,
      sigma: 0,
      slackVsDeadline: deadline - mu,
    };
  }

  const z = (deadline - mu) / sigma;
  const probability = normalCDF(z);

  return {
    z,
    probability,
    deadline,
    expectedDuration: mu,
    sigma,
    slackVsDeadline: deadline - mu,
  };
}

/**
 * What deadline is needed to achieve a target probability of on-time completion?
 * Inverse of probabilityOfSuccess: deadline = μ + z · σ
 */
export function deadlineForProbability(
  cpm: CPMResult,
  targetProb: number,
): number {
  const mu = cpm.duration;
  const sigma = cpm.sigma;

  // Edge case: zero variance → always the expected duration
  if (sigma === 0) return mu;

  const z = inverseCDF(targetProb);
  return mu + z * sigma;
}
