# T? · One-line question

**Status:** pre-registered on YYYY-MM-DD, before any run. Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** List anything you had already seen that could have shaped the hypotheses (smoke runs, earlier results). Write "none" if nothing.

## Background

Two or three sentences: what mechanism you think is at work and why the answer matters.

## Hypotheses

- **H1.** A statement that a number can prove wrong.
- **H2.** ...
- **H (control).** A case where you expect *no* effect.

## Protocol

| Factor | Levels |
|---|---|
| ... | ... |
| Fixed | everything held constant |
| Replications | 10 seeds (0–9), common random numbers across arms |

Metrics, how arms are compared (paired by seed), and the horizon.

**Pass bars.** For each hypothesis, the exact number that decides it.

Reproduce:

```bash
fleetsim bench ... --replications 10 --no-db --no-parquet --out results/T?
```

---

## Results

*Not yet run.*

### Verdicts against the pre-registered bars

### What this changes
