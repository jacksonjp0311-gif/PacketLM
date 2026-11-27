"""Mutation run: break one engine mechanism at a time and confirm a check fails.

Copies the repo to a temp dir, applies one textual mutation to engine.py (or the named module),
runs `python -m packetlm.g44_test` there, and records which checks failed.
A mutation that no check notices is reported as SURVIVED.
"""

from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUTATIONS = {
    "judge_none_contradicts": ('    if pred is None:\n        return "undetermined"', '    if pred is None:\n        return "contradicted"'),
    "blocking_ignored": ('        status = "provisional" if blocking else "qualified"\n        record["candidate"]', '        status = "qualified"\n        record["candidate"]'),
    "review_noop": ('            if h["status"] == "contradicted":\n                events += self._set_status(name, ver["v"], "suspended"',
                    '            if False:\n                events += self._set_status(name, ver["v"], "suspended"'),
    "superseded_not_pinned": ('PINNED_OK = EXEC_OK + ("superseded",)', 'PINNED_OK = EXEC_OK'),
    "cycle_offered": ('                    continue  # would create a cycle', '                    pass'),
    "first_proof_only": ('        for p in paths:\n            self.tell(', '        for p in paths[:1]:\n            self.tell('),
    "tms_all_or_nothing": ('                    if not keep:\n                        removed.add', '                    if True:\n                        removed.add'),
    "expression_borrows": ('meaning = (cap or {}).get("express") or rel',
                           'meaning = (cap or {}).get("express") or next((c["meaning"] for c in self.state["library"] if c.get("kind", "svo") == "svo"), rel)'),
    "no_dangling_check": ('_need(p in ids, f"dangling premise', '_need(True or p in ids, f"dangling premise'),
    "no_backup_fallback": ('for label, p in (("primary", path), ("backup", bak)):', 'for label, p in (("primary", path),):'),
    "ambiguity_off": ('            found = sorted(found)\n        if not found:\n            return {"status": "unknown", "value": None}\n        if len(found) > 1:\n            return {"status": "ambiguous"', '            found = sorted(found)\n        if not found:\n            return {"status": "unknown", "value": None}\n        if False:\n            return {"status": "ambiguous"'),
    'g54_lean_ambiguity_off': ('found.append(got)\n        found = sorted(found)\n        if not found:\n            return {"status": "unknown", "value": None}\n        if len(found) > 1:\n            return {"status": "ambiguous", "value": None, "candidates": found}\n        return {"status": "known", "value": found[0]}\n\n    def _ask_indexed', 'found.append(got)\n        found = sorted(found)\n        if not found:\n            return {"status": "unknown", "value": None}\n        if False:\n            return {"status": "ambiguous", "value": None, "candidates": found}\n        return {"status": "known", "value": found[0]}\n\n    def _ask_indexed'),  # re-anchored for G57 (the block also ends _ask_indexed)
    "library_off": ('        if self.use_library:\n            for n in sorted', '        if False:\n            for n in sorted'),
    "zero_support_dropped": ('                else:\n                    out.append(h)', '                elif h["support"]:\n                    out.append(h)'),
    "unanswered_lost": ('        if prior.get("unanswered"):', '        if False:'),
    "activation_overprunes": ('                if not nxt:\n                    pruned +=', '                if not nxt or p == prims[0]:\n                    pruned +='),
    "open_world_off": ('                        if conflict or (support >= 1', '                        if (support >= 1'),
    "prune_on_evidence_only": ('else [{e} for e in D]), ())], {()}', 'else [{e} if e in dict(obs) else set() for e in D]), ())], {()}'),
    "domain_too_narrow": ('            if v is None and e not in dom:\n                continue', '            if e not in dom:\n                continue'),
    "dedupe_by_last_step": ('                    key = bseq + tuple(pb)', '                    key = tuple(pb)'),
    "binding_trusted_on_load": ('        if v2:\n            pkt = bind(', '        if False:\n            pkt = bind('),
    "v3_accepts_packets": ('            _need("bits" not in f and "count" not in f,', '            _need(True,'),
    "migration_silent": ('                report["migrated"] = f"', '                _silent = f"'),
    "packet_roles_swapped": ('[bits_for(f["s"], 0) ^ bits_for(f["r"], 1) ^ bits_for(f["o"], 2)', '[bits_for(f["o"], 0) ^ bits_for(f["r"], 1) ^ bits_for(f["s"], 2)'),
    "primary_trusted_on_save": ('                if hashlib.sha256(cur).hexdigest() != self._known_bytes:  # bytes this process did not validate\n                    validate(*_read_doc(cur))', '                if False:\n                    validate(*_read_doc(cur))'),
    "g54_lean_primary_trusted_on_save": ('                if hashlib.sha256(cur).hexdigest() != self._known_bytes:  # bytes this process did not validate\n                    validate_lean(*_read_doc(cur))', '                if False:\n                    validate_lean(*_read_doc(cur))'),
    "restore_off": ('                {self._archived_tok[t] for t in toks if t in self._archived_tok}', '                set()'),
    "gate_ignores_recent": ('        if n < MIN_AGE or any(c > call - GUARD for r in recs for c in r[1:]):', '        if n < MIN_AGE:', "retention.py"),
    "archive_deleted_on_restore": ('    state["facts"].extend(comp["facts"])', '    f.unlink()\n    state["facts"].extend(comp["facts"])', "retention.py"),
    "prog_union_clauses": ('        if cur:\n            out = frozenset(cur)\n            break', '        if cur:\n            out = out | frozenset(cur)', "programs.py"),
    "prog_not_inverted": ('                cur = {y for y in cur if not ctx.has(y, q, t)}', '                cur = {y for y in cur if ctx.has(y, q, t)}', "programs.py"),
    "prog_no_recursion": ('                if depth + 1 <= MAX_DEPTH:\n                    for y in cur:', '                if depth + 1 <= 1:\n                    for y in cur:', "programs.py"),
    "prog_deps_hidden": ('            out += progs.deps(s)  # capabilities used inside', '            pass  # capabilities used inside'),
    "prog_investigate_defined_only": ('                if not known or len(set(allp)) < 2:', '                if len(set(known)) < 2:'),
    "prog_scan_ignored": ('        status = "qualified" if complete and not blockers and not gap else "provisional"', '        status = "qualified"'),
    "prog_order_dependent_ties": ('        return sorted(e for e in self.entities() if e in comp)', '        return [e for e in self.entities() if e in comp]'),
    "prog_investigate_outside_component": ('        return sorted(e for e in self.entities() if e in comp)', '        return sorted(self.entities())'),
    "prog_scan_short_horizon": ('        horizon = progs.MAX_SIZE\n', '        horizon = progs.size(cand)\n'),
    "px_none_undetermined": ('        return "supported" if not out else "contradicted"\n    if ans == SEVERAL:\n        return "supported" if len(out) >= 2 else ("contradicted"', '        return "supported" if not out else "undetermined"\n    if ans == SEVERAL:\n        return "supported" if len(out) >= 2 else ("contradicted"'),
    "px_scan_skips_negative_subjects": ('        D = [e for e, v in mine.items() if v is not None or e in neg]', '        D = [e for e, v in mine.items() if v is not None]'),
    "px_statement_as_answer_entity": ('        if v.startswith("!"):\n            continue', '        if False:\n            continue', "programs.py"),
    # The PX investigate has two redundant parts (outcome-class predictions; class scoring that treats
    # "no value" as a class). Each alone asks the one-sided question, so a mutation of one part survives
    # (found 2026-11-26); the mutation removes the mode, and the check shows the question is not asked.
    "px_investigate_defined_only": ('        self.answers = answers\n', '        self.answers = False\n'),
    "static_ignores_archive": ('        if ret and retention == "static" and ret["archived"]:', '        if False:'),
    "no_requalify": ('        out["review"] = retired + self.review() + self._requalify_retired()\n        return out\n\n    def correct_example', '        out["review"] = retired + self.review()\n        return out\n\n    def correct_example'),
    "p1_statement_alone_adopts": ('        if obs0 and not any(v not in (NONE, SEVERAL) for _, v in obs0):', '        if False:'),
    "l3_statement_as_operator_answer": ('if v not in (NONE, SEVERAL)}  # L3 of e944840', '}  # L3 of e944840'),
    "fc_judge_open": ('        return judge_closed(out, v) if s in self.state.get("complete", {}) else judge_set(out, v)', '        return judge_set(out, v)'),
    "fc_base_scan_open": ('        jf = lambda i, o, v: judge_closed(o, v) if i in closed_at else judge_set(o, v)', '        jf = lambda i, o, v: judge_set(o, v)'),
    "fc_programs_open": ('        return judge_closed(out, v) if s in self.closed else judge_set(out, v)', '        return judge_set(out, v)', "programs.py"),
    "fc_exact_open": ('self.U[i] in self.ind.closed) for i, v in self.obs]', 'False) for i, v in self.obs]', "programs.py"),
    "fc_new_fact_ignored": ('            self._fc_violated(s, f"new fact {s} {r} {o}")', '            pass'),
    "fc_removed_fact_ignored": ('                    self._fc_violated(f["s"], f"removed fact {i}")', '                    pass'),
    "fc_no_requalify": ('                    continue\n                self.acquire(n)', '                    continue'),
    "fc_allowed_with_retention": ('        if self.retention == "adaptive":\n            return "complete is not supported', '        if False:\n            return "complete is not supported'),
    "exact_no_recursion": ('        for _ in range(MAX_DEPTH):\n            cur = [r1[x]', '        for _ in range(0):\n            cur = [r1[x]', "programs.py"),
    "exact_counts_once": ('                    if e is None:\n                        nxt[key] = [rep + (ti,), cnt]\n                    else:\n                        e[1] += cnt', '                    if e is None:\n                        nxt[key] = [rep + (ti,), cnt]\n                    else:\n                        e[1] += 0', "programs.py"),
    "exact_rep_not_canonical": ('                        if rep + (ti,) < e[0]:', '                        if rep + (ti,) > e[0]:', "programs.py"),
    "exact_self_body_any_length": ('                for bl in range(1, MAX_CLAUSE):', '                for bl in range(1, 2):', "programs.py"),
    "g50_tiebreak_off_values": ('                if score > best_score or (score == best_score and score and tie(e) < tie(best)):', '                if score > best_score:'),
    "g50_tiebreak_off_answers": ('                if score > best_score or (tie and score == best_score and score and tie(e) < tie(best)):', '                if score > best_score:'),
    "g50_closure_size_ignored": ('                sizes[x] = len(seen)', '                sizes[x] = 1'),
    "g51_qualified_library_ignored": ('                if self.qualified_library and ver["status"] != "qualified":', '                if False:'),
    "h1_guard_space_data_dependent": ('        if any(s_ in self._closed() for s_, _ in obs):\n            allp', '        if False:\n            allp'),
    "h1_gap_ignored": ('status = "qualified" if complete and not blockers and not gap else "provisional"', 'status = "qualified" if complete and not blockers else "provisional"'),
    "h1_no_identity_guard": ('            allp.append(nil)\n', '            pass\n'),
    "m1_no_review_on_complete": ('                if h and h["status"] == "contradicted":\n                    self._set_status(n, ver["v"], "suspended", "contradicted by its observations (complete)")', '                if False:\n                    pass'),
    "m2_scope_ignored": ('outside = ver["status"] == "qualified" and "domain" in ver', 'outside = False and "domain" in ver'),
    "g53_memo_key_ignores_primitive": ('                        k = (base, x)', '                        k = x'),
    "g53_index_drops_primitives": ('i for r in here for i in by_first.get(r, ()))]', 'i for r in here for i in by_first.get(r, ())[:1])]'),
    "g53_sparse_conflict_ignored": ('conflict = any(len(f) == 1 and next(iter(f)) != want[i] for i, f in nf.items())', 'conflict = False'),
    "g53_skip_ignores_basis": ('                        and ver.get("evidence", {}).get("basis") == self._basis(n)):', '                        ):'),
    "s1_growth_ignored": ('        if getattr(self, "_grown", None) and not line.strip().lower().startswith("fact "):\n            self._flush_growth()', '        pass'),
    's1_region_is_domain_only': ('                hit = bool(grown & self._component(seeds))', '                hit = bool(grown & {s_ for s_, _ in obs})'),  # re-anchored for G57 (non-indexed path; same intent)
    "l1_dependency_status_ignored": ('        if status == "qualified" and self._deps_unqualified(h["seq"]):', '        if False:'),
    "l1_no_demotion_propagation": ('            elif status == "provisional" and dep["status"] == "qualified":', '            elif False:'),
    "g54_lean_checksum_accepts_any": ('            ok = hashlib.sha256(raw[m.end():-1]).hexdigest() == doc["checksum"]', '            ok = True'),
    "g54_lean_no_backup": ('                    os.link(self.path, tmpb)\n                    os.replace(tmpb, bak)', '                    pass'),
    "g54_lean_save_unvalidated": ('        validate_lean({"schema": SCHEMA, "checksum": chk, "state": self.state}, checksum_ok=True)', '        pass'),
    "g54_fast_validate_skips_premises": ('                if q not in ids:\n                    return False', '                pass'),
    "g54_fast_validate_skips_cycles": ('                visit(f"cap:{name}@{ver[\'v\']}", set())\n    except StateError:', '                pass\n    except StateError:'),
    "g54_lean_decode_wrong_role": ('            idx["decode"] = {pack(bits_for(t, 2)).bits: t for t in idx["names"]}', '            idx["decode"] = {pack(bits_for(t, 1)).bits: t for t in idx["names"]}'),
    "n1_no_candidate_keeps_qualified": ('            if cur and cur["status"] == "qualified":\n                self._set_status(name, cur["v"], "provisional",\n                                 "several supported programs" if reps else', '            if cur and cur["status"] == "qualified" and reps:\n                self._set_status(name, cur["v"], "provisional",\n                                 "several supported programs" if reps else'),
    "g55_budget_ignored": ('            if gap and len(allp) <= self.closed_guards:', '            if gap and len(allp) <= progs.MAX_GUARDS:'),
    # verify-3e2783c: M1 (lean keeps insertion order), N1b (base cap), Low 1 (one JSON value after the prefix)
    "m1_lean_sorted_keys": ('        text = json.dumps(self.state).encode()', '        text = json.dumps(self.state, sort_keys=True).encode()'),
    "n1b_base_no_candidate_keeps_qualified": ('            if cur and cur["status"] == "qualified":\n                self._set_status(name, cur["v"], "provisional",\n                                 "several supported programs" if supported else', '            if cur and cur["status"] == "qualified" and supported:\n                self._set_status(name, cur["v"], "provisional",\n                                 "several supported programs" if supported else'),
    "low1_trailing_text_accepted": ('        if end == len(text) - 1:', '        if end > 0:'),
    # G56: the long-lived protocol (packetlm/serve.py)
    "g56_serve_no_journal_record": ('        o.jfh.write((json.dumps({"flags": list(flags), "lines": list(lines), "replies_sha256": _rhash(replies)})\n                     + "\\n").encode())', '        pass', "serve.py"),
    'g56_serve_replay_unverified': ('            _need(_rhash(got) == rec["replies_sha256"], f"journal replay diverged at record {k}")', '            pass', 'serve.py'),  # re-anchored (replay moved to Server._replay)
    "g56_serve_new_path_reuses_state": ('        if o is None or o.path != path or o.flags != list(flags):', '        if o is None:', "serve.py"),
    "g56_serve_memory_unvalidated": ('        validate_lean({"schema": SCHEMA, "checksum": None, "state": eng.state}, checksum_ok=True)', '        pass', "serve.py"),
    "g56_serve_journal_base_ignored": ('            if head["base"] == have:', '            if True:', "serve.py"),
    "g56_serve_no_snapshot_on_close": ('        if o.since or not o.path.exists():\n            self._snapshot(o)', '        if False:\n            self._snapshot(o)', "serve.py"),
    "scan_short_horizon": ('        horizon = self.deepen if (max_len is None and self.deepen) else searched', '        horizon = searched'),
    "deepen_past_ambiguity": ('                if any(h["status"] == "supported" for h in live):', '                if sum(h["status"] == "supported" for h in live) == 1:'),
    "compose_skips_bit": ('            acc |= b_rows[low.bit_length() - 1]\n            row ^= low', '            acc |= b_rows[low.bit_length() - 1]\n            row ^= low\n            row &= row - 1', "geom.py"),
    "compose_keeps_source": ('            return g.compose([row], self._rows(token))[0]', '            return row | g.compose([row], self._rows(token))[0]'),
    # G57: --indexed (memoized recall, relation-grouped rows, component classes, gated re-asks)
    'g57_gate_ignores_stamps': ('        stamps = tuple(self.memo.stamp.get(r, 0) for r in base) if base is not None else None', '        stamps = None', 'engine.py'),
    'g57_gate_ignores_capabilities': ('        return (target, tuple(sorted((n, self._cap_hash(n)) for n in caps)), rels, stamps,', '        return (target, (), rels, stamps,', 'engine.py'),
    'g57_gate_ignores_dependencies': ('                for d in _deps_of(ver["seq"]):\n                    todo.append(_split_cap(d)[0])', '                pass', 'engine.py'),
    'g57_gate_ignores_known_entity': ('                s in self._idx()["pos"], self._cap_fp["lib"])', '                True, self._cap_fp["lib"])', 'engine.py'),
    'g57_memo_keeps_removed': ('            for t, c in removed.items():\n                if t in ent:', '            for t, c in ():\n                if t in ent:', 'engine.py'),
    'g57_memo_ignores_added': ('            for t, c in added.items():\n                if self.passes(qi, self.packet_of(t)):', '            for t, c in ():\n                if self.passes(qi, self.packet_of(t)):', 'engine.py'),
    'g57_memo_stamp_missed': ('        for t in list(added) + list(removed):\n            self.stamp[t[1]] = self.tick', '        for t in list(added):\n            self.stamp[t[1]] = self.tick', 'engine.py'),
    'g57_readonly_any_line': ('        ro = bool(o.memo is not None and lines and all(readonly_line(x) for x in lines))', '        ro = bool(o.memo is not None and lines and any(readonly_line(x) for x in lines))', 'serve.py'),
    'g57_gate_outside_readonly': ('        return self.readonly_call and self.memo is not None and self.geometry and not self.programs \\', '        return self.memo is not None and self.geometry and not self.programs \\', 'engine.py'),
    'g57_by_rel_wrong_relation': ('                sel = idx["by_rel"].get(rel, [])', '                sel = idx["by_rel"].get(rel, [])[1:]', 'engine.py'),
    'g57_gate_ignores_library': ('                s in self._idx()["pos"], self._cap_fp["lib"])', '                s in self._idx()["pos"], "")', 'engine.py'),
    'g57_uf_keeps_removed_edges': ('                self.uf = None  # an edge may be gone: rebuild the classes on next use', '                pass', 'engine.py'),
    'g57_uf_ignores_added_edges': ('                for t in added:\n                    if not t[1].startswith("cap:"):\n                        self._union(t[0], t[2])', '                pass', 'engine.py'),
    'g57_region_ignores_seeds': ('        return any(g in seeds or (g in self.uf and self._find(g) in roots) for g in grown)', '        return any((g in self.uf and self._find(g) in roots) for g in grown)', 'engine.py'),
    'g57_packets_stale_after_rebuild': ('            self.pkl = [(p, p.bit_count()) for p in map(self.packet_of, triples)]\n', '', 'engine.py'),
    'g57_append_path_skips_one': ('            new = triples[len(last):]', '            new = triples[len(last) + 1:]', 'engine.py'),
    'g57_readonly_unchecked': ('                _need(_state_digest(eng.state) == before, "read-only call changed the state")', '                pass', 'serve.py'),
    # verify-d6cbcf3: first-snapshot recovery (S1), stale journals (Low 1), per-process refusal (Low 2), finish (Info)
    'd6_no_empty_snapshot_for_new_path': ('            self._snapshot(o)  # a new path: an empty snapshot first, so every journal names a base', '            self._journal_start(o, None)', 'serve.py'),
    'd6_contained_journal_unverified': ('                _need(hashlib.sha256(json.dumps(got).encode()).hexdigest() == have,', '                _need(True,', 'serve.py'),
    'd6_engine_reads_past_unclosed_journal': ('    if jp.exists() and len(jp.read_bytes().splitlines()) > 1:', '    if False:', 'engine.py'),
    'd6_serve_call_skips_finish': ('        replies = [eng.turn(x) for x in lines]\n        eng.finish()\n        if ro:', '        replies = [eng.turn(x) for x in lines]\n        if ro:', 'serve.py'),
    'g57_indexed_ambiguity_off': ('found.append(got)\n        found = sorted(found)\n        if not found:\n            return {"status": "unknown", "value": None}\n        if len(found) > 1:\n            return {"status": "ambiguous", "value": None, "candidates": found}\n        return {"status": "known", "value": found[0]}\n\n    def _decode', 'found.append(got)\n        found = sorted(found)\n        if not found:\n            return {"status": "unknown", "value": None}\n        if False:\n            return {"status": "ambiguous", "value": None, "candidates": found}\n        return {"status": "known", "value": found[0]}\n\n    def _decode'),
    'g57_region_seeds_only': ('                hit = self.memo.region_hits(seeds, grown)', '                hit = bool(grown & seeds)'),
    # G57b (docs/G57b.md): the persistent index, candidate filter, sparse tables and scoped validation
    "g57b_append_skips_by_sr": ('        ix["by_sr"].setdefault((t[0], t[1]), []).append(f)\n', '        ix["by_sr"].setdefault((t[0], t[1]), []).append(f) if len(ix["by_sr"]) < 3 else None\n'),
    "g57b_append_skips_ref": ('        ix["ref"].setdefault(t[1], {}).setdefault(t[0], set()).add(t[2])\n        ix["byid"]', '        ix["byid"]'),
    "g57b_append_skips_memo": ('        ix["n_facts"], ix["epoch"] = len(state["facts"]), state.get("fact_epoch", 0)\n        self._added(t)', '        ix["n_facts"], ix["epoch"] = len(state["facts"]), state.get("fact_epoch", 0)'),
    "g57b_support_skips_told_rel": ('            self.ix["told_rel"][f["r"]] += 1', '            pass'),
    "g57b_valid_ignores_identity": ('        return ix is not None and state["facts"] is ix["facts_ref"] and len(state["facts"]) == ix["n_facts"] \\\n            and state.get("fact_epoch", 0) == ix["epoch"]', '        return ix is not None'),
    "g57b_candidates_need_3_bits": ('            if c >= 2:\n                cand.update', '            if c >= 3:\n                cand.update'),
    "g57b_no_small_packets": ('        if self.packet_of(t).bit_count() < SMALL_PACKET:\n            ix["small"].append(t)', '        pass'),
    "g57b_differs_skips_domain": ('            items = [(e, preds.get(e)) for e in sorted(set(preds) | {e for e in dom if e in pos}, key=pos.__getitem__)]', '            items = list(preds.items())'),
    "g57b_sparse_drops_negatives": ('        mine = self._predictions(cand_seq, also=neg) if sparse', '        mine = self._predictions(cand_seq, also=set()) if sparse'),
    "g57b_was_known_always": ('            was_known = s in self.memo.ix["pos"]', '            was_known = True'),
    "g57b_drop_keeps_ents_untracked": ('            if self._ents_tracked and getattr(self, "_ents", None) is None:', '            if False:'),
    "g57b_touched_not_recorded": ('        if self.incremental and self.memo.scope is not None:\n            self.memo.scope["touched"].append(fact)\n        if kind == "told"', '        if kind == "told"'),
    "g57b_scoped_skips_premises": ('    for f in touched:\n        for sp in f["supports"]:\n            for q in sp["premises"]:\n                if q not in byid:\n                    return False', '    pass'),
    "g57b_ix_check_noop": ('_need(same and +ix["told_rel"] == told, "incremental', '_need(True, "incremental'),
    "g57b_no_period_guard": ('        if sc is not None and sc["ok"] and o.since_full < self.full_every', '        if sc is not None and sc["ok"]', "serve.py"),
    "v35_dom_cache_by_id": ('        if c.get("key") != key or c.get("domain") != ver["domain"]:', '        if c.get("key") != key:'),
    "g57b_drop_keeps_scope": ('            if self.memo.scope is not None:\n                self.memo.scope["ok"] = False  # supports and facts may change anywhere', '            pass'),
    # G58 (`--routed`, docs/G58.md): one mechanism of exact capability routing at a time
    "g58_pin_gen_not_bumped": ('            if (old_status in PINNED_OK) != (status in PINNED_OK):\n                self.memo.pin_gen += 1', '            pass'),
    "g58_status_not_dirty": ('            self.memo.rv_dirty.add((name, v))', '            pass'),
    "g58_new_version_not_dirty": ('            self.memo.lib_gen += 1  # G58\n            self.memo.rv_dirty.add((name, None))', '            self.memo.lib_gen += 1  # G58'),
    "g58_new_version_lib_gen_kept": ('            self.memo.lib_gen += 1  # G58\n            self.memo.rv_dirty.add((name, None))', '            self.memo.rv_dirty.add((name, None))'),
    "g58_status_lib_gen_kept": ('            self.memo.lib_gen += 1  # G58: what `primitives` offers may change', '            pass'),
    "g58_observe_not_recorded": ('    def observe(self, name, subject, value) -> list[str]:\n        obs = self.state["observations"].setdefault(name, [])\n        if self.memo is not None:\n            self.memo.rv_obs.add(name)  # G58', '    def observe(self, name, subject, value) -> list[str]:\n        obs = self.state["observations"].setdefault(name, [])\n        if self.memo is not None:\n            pass'),
    "g58_closed_delta_ignored": ('            for x in X["closed"] ^ closed:', '            for x in ():'),
    "g58_entity_delta_ignored": ('            for x in new:\n                fast |= X["subj"].get(x, set())\n            X["pos"]', '            for x in ():\n                fast |= X["subj"].get(x, set())\n            X["pos"]'),
    "g58_changed_stamps_ignored": ('                if t > X["tick"]:', '                if False:'),
    "g58_dependents_not_followed": ('                fast |= X["dep"].get((dn, dv), set()) if dv is not None else X["depn"].get(dn, set())', '                pass'),
    "g58_pruned_count_wrong": ('                pruned += (P - len(ii)) * P ** (n - len(prefix) - 1)', '                pruned += (P - len(ii))'),
    "g58_reach_ignores_told": ('                        if z not in seen and any(sp["kind"] == "told" for sp in f["supports"]):', '                        if z not in seen:'),
    "g58_fp_ignores_closed": ('tuple((s_, v_, s_ in pos, s_ in closed) for s_, v_ in obs))', 'tuple((s_, v_, s_ in pos, False) for s_, v_ in obs))'),
    "g58_fp_ignores_stamps": ('                tuple(stamp.get(r, 0) for r in base) if base is not None else None,', '                None,'),
    "g58_base_cache_ignores_status": ('                if b is not None and all((self.version(dn, dv) or {}).get("status") in PINNED_OK\n                                         for dn, dv in self._closure_cached(name, ver)):', '                if b is not None:'),
    "g58_scoped_validation_skips_caps": ('*((sc.get("caps", set()),', '*((set(),', "serve.py"),
}


# verify-050bebd: the verifier's mutations of the restated G45 t5 (retention). They are run against
# packetlm.g45_test; killed only if a `t5_retention` check fails (docs/verification/tools_050bebd).
_SAY = 'return text + (" [provisional]" if got.get("provisional") else "")'
_FLUSH = ('                self.stats["grown_requalified"] = self.stats.get("grown_requalified", 0) + 1\n'
          '                self.acquire(n)')
G45_MUTATIONS = {
    "t5_value_changed_when_provisional": (_SAY, 'return (text.replace(str(got["value"]), str(got["value"])[::-1]) + " [provisional]") if got.get("provisional") else text'),
    "t5_value_lost_when_provisional": (_SAY, 'return "unknown" if got.get("provisional") else text'),
    "t5_demoted_without_rescan": (_FLUSH, '                self.stats["grown_requalified"] = self.stats.get("grown_requalified", 0) + 1\n'
                                          '                self._set_status(n, ver["v"], "provisional", "requalified")'),
    "t5_rescan_adopts_blocker": (_FLUSH, _FLUSH + '\n                _b = self.state["hypotheses"].get(n, {}).get("blocking") or []\n'
                                         '                if _b:\n                    self.version(n)["seq"] = list(_b[-1])'),
    "t5_value_changed_qualified": (_SAY, 'return text.replace(str(got["value"]), str(got["value"])[::-1]) if (not got.get("provisional") and self.state["turn"] > 590) else text + (" [provisional]" if got.get("provisional") else "")'),
}


def _run_g45_mutation(old, new) -> dict:
    with tempfile.TemporaryDirectory() as d:
        dst = Path(d) / "repo"
        shutil.copytree(ROOT / "packetlm", dst / "packetlm", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "data", dst / "data")
        eng = dst / "packetlm" / "engine.py"
        src = eng.read_text()
        if src.count(old) != 1:
            return {"error": "mutation site not found exactly once"}
        eng.write_text(src.replace(old, new))
        p = subprocess.run([sys.executable, "-m", "packetlm.g45_test"], cwd=dst, capture_output=True, text=True, timeout=900)
        rec = dst / "artifacts" / "g45_receipt.json"
        failed = json.loads(rec.read_text())["failed"] if rec.exists() else []
        t5 = [f for f in failed if f.endswith("t5_retention")]
        return {"exit": p.returncode, "failed": failed, "verdict": "KILLED" if t5 else "SURVIVED",
                "crash": p.stderr.strip().splitlines()[-1][:200] if p.returncode and not failed else None}


def _baseline() -> list:
    """Unmutated run first: a check that already fails at baseline cannot kill a mutation
    (found 2026-11-26: a check failing at baseline made a mutation look killed)."""
    with tempfile.TemporaryDirectory() as d:
        dst = Path(d) / "repo"
        shutil.copytree(ROOT / "packetlm", dst / "packetlm", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "data", dst / "data")
        p = subprocess.run([sys.executable, "-m", "packetlm.g44_test"], cwd=dst, capture_output=True, text=True, timeout=600)
        rec = dst / "artifacts" / "g44_receipt.json"
        return json.loads(rec.read_text())["failed"] if rec.exists() else ["baseline did not run"]


def run() -> dict:
    results = {}
    base_failed = _baseline()
    for name, (old, new, *target) in MUTATIONS.items():
        if base_failed:
            results[name] = {"error": f"baseline fails: {base_failed[:3]}"}
            continue
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / "repo"
            shutil.copytree(ROOT / "packetlm", dst / "packetlm", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "data", dst / "data")
            eng = dst / "packetlm" / (target[0] if target else "engine.py")
            src = eng.read_text()
            if src.count(old) != 1:
                results[name] = {"error": "mutation site not found exactly once"}
                continue
            eng.write_text(src.replace(old, new))
            p = subprocess.run([sys.executable, "-m", "packetlm.g44_test"], cwd=dst, capture_output=True, text=True, timeout=600)
            rec = dst / "artifacts" / "g44_receipt.json"
            failed = json.loads(rec.read_text())["failed"] if rec.exists() and p.returncode else []
            results[name] = {"exit": p.returncode, "failed": failed,
                             "verdict": "KILLED" if p.returncode else "SURVIVED",
                             "crash": p.stderr.strip().splitlines()[-1][:200] if p.returncode and not failed else None}
    for name, (old, new) in G45_MUTATIONS.items():
        results["g45." + name] = _run_g45_mutation(old, new) if not base_failed else {"error": "baseline fails"}
    out = {"baseline_failed": base_failed, "mutations": results, "killed": sum(r.get("verdict") == "KILLED" for r in results.values()),
           "total": len(results)}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mutations_receipt.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    r = run()
    raise SystemExit(0 if r["killed"] == r["total"] else 1)
