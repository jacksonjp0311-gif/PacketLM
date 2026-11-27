# Learning-amortization export (declared before reading any G46 result)

**Instrument:** https://github.com/jacksonjp0311-gif/learning-amortization, pinned at
`70297af`. It is used unmodified. It is put on `PYTHONPATH` from a checkout at that commit
(`/workspace/vendor/learning-amortization`), and is neither vendored into nor edited by PacketLM.
Its metric, estimators and censoring rules are used as they are. If PacketLM looks bad under
it, that is the result.

## Mapping G46/G47 raw logs to its CSV (`arm,seed,task,component,resource,amount,censored`)

**Resource:** `cpu_s`, the engine process CPU reported by each CLI call. That figure covers
load, validation, turns and save. It is the only resource, so no price vector is needed. A second file
logs state bytes (`storage`, resource `bytes`) for reference only. It is not mixed into the
primary estimate.

**Task index:** tasks 1..36 in sequence order. Task 0 (setup) gets an explicit zero row for
every arm, since every arm starts from an empty state.

**Components, assigned by call type.** The engine frozen for G46 does not split CPU inside a
call, which is a stated limitation.

| call | component |
|---|---|
| teaching call: facts and examples; `correct example`; `investigate` / answer / `unanswered` calls | `acquisition` (qualification is part of these calls, so `verification` is logged as an explicit 0) |
| the task's sealed `what is` call | `execution` |
| family-end correction, transfer, retention calls (C-type arms only), charged to the family's last task | `maintenance`, only in the arm variant `<arm>+maint` |

Retrieval is inside every call's load and is not separable; it is logged as an explicit 0.

**Censoring:** a task is censored when the arm did not meet the declared accuracy target on
it. The target is that every sealed reply on that task is correct. A censored task's cost is
a lower bound, and the instrument's notes on direction apply: C censored means optimistic,
B censored means pessimistic.

**Reports:** each produced with `python -m amortization`.
- `C` vs `B`: the primary `A_36`, from task costs;
- `C+maint` vs `B`: conservative;
- `C` vs `P`: `A^reuse`.

**Limitation for G46:** the registered G46 run started before per-call costs were kept in
the result. Its task records hold only the task total, so G46 is exported with all task CPU
under `acquisition` and `execution` as an explicit 0. The total and `A_n` are unaffected;
only the component split is missing. From G47 onward, the harness records `eval_cpu_s`
(the task's sealed-evaluation call), and the exporter splits it out as `execution`.
