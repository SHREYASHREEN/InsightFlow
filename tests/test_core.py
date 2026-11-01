import io
import sqlite3
import unittest
import pandas as pd
from datetime import datetime

from tests.helpers import memory_db, req, request
from insightflow import (auth, config, db, docs_service, exports, imports, kpis, seed, sla, timeutil,
                         traceability, requirements_service as rs)


class TestDatabase(unittest.TestCase):
    def test_init_creates_all_tables_and_is_repeatable(self):
        conn = memory_db()
        db.init_db(conn)  # second call must not fail
        names = db.table_names(conn)
        for t in ["users", "requirements", "objectives", "stakeholders", "user_stories", "acceptance_criteria",
                  "uat_tests", "requests", "status_history", "requirement_history", "settings"]:
            self.assertIn(t, names)

    def test_foreign_keys_enforced(self):
        conn = memory_db()
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO user_stories(story_id,requirement_id,as_a,i_want,so_that) VALUES ('US-1',999,'a','b','c')")


class TestAuth(unittest.TestCase):
    def test_hash_is_not_plaintext_and_verifies(self):
        h = auth.hash_password("Secret123")
        self.assertNotIn("Secret123", h)
        self.assertTrue(auth.verify_password("Secret123", h))
        self.assertFalse(auth.verify_password("secret123", h))
        self.assertNotEqual(h, auth.hash_password("Secret123"))  # unique salt

    def test_verify_handles_garbage(self):
        self.assertFalse(auth.verify_password("x", "not-a-hash"))

    def test_registration_validation(self):
        conn = memory_db()
        _, e = auth.create_user(conn, "a", "", "short", "Viewer")
        self.assertEqual(len(e), 3)
        _, e = auth.create_user(conn, "validuser", "Valid", "onlyletters", "Viewer")
        self.assertTrue(any("digit" in x for x in e))
        uid, e = auth.create_user(conn, "validuser", "Valid", "Passw0rdOK", "Viewer")
        self.assertEqual(e, [])
        _, e = auth.create_user(conn, "VALIDUSER", "Dup", "Passw0rdOK", "Viewer")
        self.assertIn("already taken", e[0])
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotIn("Passw0rdOK", stored)

    def test_authenticate(self):
        conn = memory_db()
        auth.create_user(conn, "alice", "Alice", "Passw0rd1", "Business Analyst")
        user, _ = auth.authenticate(conn, "alice", "Passw0rd1")
        self.assertEqual(user["role"], "Business Analyst")
        self.assertIsNone(auth.authenticate(conn, "alice", "wrong")[0])
        self.assertIsNone(auth.authenticate(conn, "nobody", "x")[0])
        self.assertEqual(auth.authenticate(conn, "alice", "wrong")[1], auth.authenticate(conn, "nobody", "x")[1])
        self.assertIsNone(auth.authenticate(conn, "", "")[0])
        auth.set_user_active(conn, user["id"], False)
        self.assertIn("disabled", auth.authenticate(conn, "alice", "Passw0rd1")[1])

    def test_permissions(self):
        self.assertTrue(auth.has_permission("Admin", "user.manage"))
        self.assertFalse(auth.has_permission("Business Analyst", "user.manage"))
        self.assertTrue(auth.has_permission("Business Analyst", "requirement.write"))
        self.assertFalse(auth.has_permission("Business Analyst", "requirement.delete"))
        self.assertTrue(auth.has_permission("Viewer", "view"))
        self.assertFalse(auth.has_permission("Viewer", "requirement.write"))
        self.assertFalse(auth.has_permission("Nonexistent", "view"))


class TestRequirements(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()

    def test_create_and_get(self):
        pk, e = rs.create_requirement(self.conn, req())
        self.assertEqual(e, [])
        self.assertEqual(rs.get_requirement(self.conn, pk)["title"], "Test requirement")

    def test_validation_errors(self):
        _, e = rs.create_requirement(self.conn, req(req_id="bad", title="", priority="Urgent", status="Nope",
                                                     req_type="X", due_date="31/12/2026"))
        self.assertGreaterEqual(len(e), 6)

    def test_duplicate_id_prevented(self):
        rs.create_requirement(self.conn, req())
        _, e = rs.create_requirement(self.conn, req(title="Other"))
        self.assertTrue(any("already exists" in x for x in e))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0], 1)

    def test_dependency_validation(self):
        _, e = rs.create_requirement(self.conn, req(dependencies="REQ-999"))
        self.assertTrue(any("does not exist" in x for x in e))
        _, e = rs.create_requirement(self.conn, req(dependencies="REQ-001"))
        self.assertTrue(any("itself" in x for x in e))

    def test_update_records_history_and_blocks_duplicates(self):
        pk, _ = rs.create_requirement(self.conn, req())
        rs.create_requirement(self.conn, req(req_id="REQ-002"))
        self.assertEqual(rs.update_requirement(self.conn, pk, req(status="Approved", title="New title")), [])
        fields = {h["field"] for h in rs.requirement_history(self.conn, pk)}
        self.assertTrue({"status", "title", "created"} <= fields)
        e = rs.update_requirement(self.conn, pk, req(req_id="REQ-002"))
        self.assertTrue(e)
        self.assertEqual(rs.update_requirement(self.conn, 999, req()), ["Requirement not found."])

    def test_delete_cascades_to_children(self):
        pk, _ = rs.create_requirement(self.conn, req())
        sid, _ = docs_service.add_story(self.conn, "US-001", pk, "user", "x", "y")
        docs_service.add_criterion(self.conn, pk, description="works")
        docs_service.add_uat_test(self.conn, "UAT-001", "t", pk)
        self.assertTrue(rs.delete_requirement(self.conn, pk))
        for t in ("user_stories", "acceptance_criteria", "uat_tests"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], 0)
        self.assertFalse(rs.delete_requirement(self.conn, pk))

    def test_search_filter_sort(self):
        rs.create_requirement(self.conn, req(req_id="REQ-001", title="Alpha login", priority="Low", status="Draft"))
        rs.create_requirement(self.conn, req(req_id="REQ-002", title="Beta report", priority="Critical", status="Approved"))
        rs.create_requirement(self.conn, req(req_id="REQ-003", title="Gamma", priority="High", status="Approved"))
        self.assertEqual([r["req_id"] for r in rs.list_requirements(self.conn, search="login")], ["REQ-001"])
        self.assertEqual(len(rs.list_requirements(self.conn, status=["Approved"])), 2)
        self.assertEqual(len(rs.list_requirements(self.conn, priority=["Low", "High"])), 2)
        by_pri = [r["req_id"] for r in rs.list_requirements(self.conn, sort_by="priority")]
        self.assertEqual(by_pri, ["REQ-002", "REQ-003", "REQ-001"])
        self.assertEqual(rs.list_requirements(self.conn, sort_by="req_id", descending=True)[0]["req_id"], "REQ-003")
        # SQL-injection style input is treated as plain text
        self.assertEqual(rs.list_requirements(self.conn, search="'; DROP TABLE requirements;--"), [])
        self.assertEqual(len(rs.list_requirements(self.conn)), 3)
        self.assertEqual(len(rs.list_requirements(self.conn, sort_by="bogus; DROP")), 3)

    def test_date_filter(self):
        rs.create_requirement(self.conn, req(req_id="REQ-001"), created_at="2026-01-10 10:00:00")
        rs.create_requirement(self.conn, req(req_id="REQ-002"), created_at="2026-03-10 10:00:00")
        self.assertEqual([r["req_id"] for r in rs.list_requirements(self.conn, date_from="2026-02-01")], ["REQ-002"])
        self.assertEqual([r["req_id"] for r in rs.list_requirements(self.conn, date_to="2026-02-01")], ["REQ-001"])

    def test_next_req_id(self):
        self.assertEqual(rs.next_req_id(self.conn), "REQ-001")
        rs.create_requirement(self.conn, req(req_id="REQ-007"))
        self.assertEqual(rs.next_req_id(self.conn), "REQ-008")


class TestDocs(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()
        self.pk, _ = rs.create_requirement(self.conn, req())

    def test_story_format_and_validation(self):
        self.assertEqual(docs_service.format_story("user", "to log in", "I can work"),
                         "As a user, I want to log in, so that I can work.")
        _, e = docs_service.add_story(self.conn, "bad", self.pk, "", "", "")
        self.assertEqual(len(e), 4)
        sid, e = docs_service.add_story(self.conn, "US-001", self.pk, "user", "x", "y")
        self.assertEqual(e, [])
        _, e = docs_service.add_story(self.conn, "US-001", self.pk, "user", "x", "y")
        self.assertTrue(any("already exists" in x for x in e))

    def test_criteria_formats(self):
        _, e = docs_service.add_criterion(self.conn, self.pk)
        self.assertTrue(e)
        _, e = docs_service.add_criterion(self.conn, self.pk, given="a", when="b")
        self.assertTrue(e)
        cid, e = docs_service.add_criterion(self.conn, self.pk, "a user", "they log in", "they see home")
        self.assertEqual(e, [])
        self.assertIn("Given a user, when they log in, then they see home", docs_service.list_criteria(self.conn)[0]["text"])

    def test_uat_validation_and_status(self):
        _, e = docs_service.add_uat_test(self.conn, "x", "", self.pk, status="Bad")
        self.assertEqual(len(e), 3)
        pk, e = docs_service.add_uat_test(self.conn, "UAT-001", "t", self.pk)
        docs_service.set_uat_status(self.conn, pk, "Passed")
        self.assertEqual(docs_service.list_uat_tests(self.conn)[0]["status"], "Passed")
        with self.assertRaises(ValueError):
            docs_service.set_uat_status(self.conn, pk, "Bad")

    def test_objectives_and_stakeholders_duplicates(self):
        self.assertEqual(docs_service.add_objective(self.conn, "OBJ-01", "t")[1], [])
        self.assertTrue(docs_service.add_objective(self.conn, "OBJ-01", "t")[1])
        self.assertEqual(docs_service.add_stakeholder(self.conn, "Sam")[1], [])
        self.assertTrue(docs_service.add_stakeholder(self.conn, "Sam")[1])
        self.assertTrue(docs_service.add_stakeholder(self.conn, "Pat", influence="Huge")[1])

    def test_doc_items(self):
        self.assertTrue(docs_service.add_doc_item(self.conn, "Nope", "t")[1])
        self.assertEqual(docs_service.add_doc_item(self.conn, "Risk", "R1", "text")[1], [])
        self.assertEqual(len(docs_service.list_doc_items(self.conn, "Risk")), 1)


class TestTraceability(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()
        self.o1, _ = docs_service.add_objective(self.conn, "OBJ-01", "Used")
        docs_service.add_objective(self.conn, "OBJ-02", "Unused")
        self.r1, _ = rs.create_requirement(self.conn, req(req_id="REQ-001", objective_id=self.o1, status="Approved"))
        self.r2, _ = rs.create_requirement(self.conn, req(req_id="REQ-002", status="Draft"))
        s, _ = docs_service.add_story(self.conn, "US-001", self.r1, "u", "w", "s")
        c, _ = docs_service.add_criterion(self.conn, self.r1, "g", "w", "t", story_id=s)
        docs_service.add_uat_test(self.conn, "UAT-001", "t", self.r1, criterion_id=c)

    def test_gaps(self):
        g = traceability.gap_report(self.conn)
        self.assertEqual([r["req_id"] for r in g["no_acceptance_criteria"]], ["REQ-002"])
        self.assertEqual([r["req_id"] for r in g["no_uat_tests"]], ["REQ-002"])
        self.assertEqual([r["code"] for r in g["objectives_without_requirements"]], ["OBJ-02"])
        self.assertEqual([r["req_id"] for r in g["unapproved_or_incomplete"]], ["REQ-002"])
        self.assertEqual([r["req_id"] for r in g["requirements_without_objective"]], ["REQ-002"])

    def test_matrix_chain_and_gaps_visible(self):
        m = {r["requirement"]: r for r in traceability.build_matrix(self.conn)}
        self.assertEqual((m["REQ-001"]["objective"], m["REQ-001"]["story"], m["REQ-001"]["uat_test"]),
                         ("OBJ-01", "US-001", "UAT-001"))
        self.assertIsNone(m["REQ-002"]["uat_test"])
        self.assertEqual(len(traceability.build_matrix(self.conn)), 2)

    def test_matrix_reflects_new_data(self):
        docs_service.add_uat_test(self.conn, "UAT-002", "t2", self.r2)
        self.assertEqual(traceability.gap_report(self.conn)["no_uat_tests"], [])

    def test_coverage(self):
        c = traceability.coverage_summary(self.conn)
        self.assertEqual(c["acceptance_criteria_coverage_pct"], 50.0)
        self.assertEqual(c["uat_coverage_pct"], 50.0)
        empty = traceability.coverage_summary(memory_db())
        self.assertIsNone(empty["uat_coverage_pct"])


class TestSLA(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()

    def make(self, created, priority="High", owner="Bob", **kw):
        pk, e = sla.create_request(self.conn, request(priority=priority, owner=owner, **kw), created_at=created)
        self.assertEqual(e, [])
        return pk

    def test_due_date_uses_priority_hours(self):
        pk = self.make("2026-01-05 09:00:00", "High")
        self.assertEqual(self.conn.execute("SELECT due_at FROM requests WHERE id=?", (pk,)).fetchone()[0], "2026-01-05 17:00:00")
        pk = self.make("2026-01-05 09:00:00", "Low", request_id="RQ-X")
        self.assertEqual(self.conn.execute("SELECT due_at FROM requests WHERE id=?", (pk,)).fetchone()[0], "2026-01-08 09:00:00")

    def test_validation(self):
        _, e = sla.create_request(self.conn, request(title="", category="Zzz", priority="Meh", requester=""))
        self.assertEqual(len(e), 4)

    def test_history_recorded_and_resolution(self):
        pk = self.make("2026-01-05 09:00:00")
        self.assertEqual(sla.change_status(self.conn, pk, "In Progress", at="2026-01-05 10:00:00"), [])
        self.assertEqual(sla.change_status(self.conn, pk, "Resolved", at="2026-01-05 15:00:00"), [])
        row = self.conn.execute("SELECT * FROM requests WHERE id=?", (pk,)).fetchone()
        self.assertEqual(row["resolved_at"], "2026-01-05 15:00:00")
        n = self.conn.execute("SELECT COUNT(*) FROM status_history WHERE request_pk=?", (pk,)).fetchone()[0]
        self.assertEqual(n, 4)  # New, Assigned, In Progress, Resolved

    def test_invalid_status_changes(self):
        pk = self.make("2026-01-05 09:00:00")
        self.assertTrue(sla.change_status(self.conn, pk, "Bogus"))
        self.assertTrue(sla.change_status(self.conn, pk, "Assigned"))  # same status
        self.assertTrue(sla.change_status(self.conn, 999, "Resolved"))
        sla.change_status(self.conn, pk, "In Progress", at="2026-01-05 10:00:00")
        self.assertTrue(sla.change_status(self.conn, pk, "Resolved", at="2026-01-05 08:00:00"))  # time travel

    def test_sla_compliance_and_average(self):
        a = self.make("2026-01-05 09:00:00", "High", request_id="RQ-A")   # due 17:00
        b = self.make("2026-01-05 09:00:00", "High", request_id="RQ-B")
        c = self.make("2026-01-05 09:00:00", "High", request_id="RQ-C")
        sla.change_status(self.conn, a, "Resolved", at="2026-01-05 15:00:00")   # 6h on time
        sla.change_status(self.conn, b, "Resolved", at="2026-01-05 19:00:00")   # 10h late
        now = datetime(2026, 1, 5, 12, 0, 0)
        s = sla.sla_summary(self.conn, now)
        self.assertEqual(s["completed_requests"], 2)
        self.assertEqual(s["resolved_on_time"], 1)
        self.assertEqual(s["sla_compliance_pct"], 50.0)
        self.assertEqual(s["avg_resolution_hours"], 8.0)
        self.assertEqual(s["open_requests"], 1)

    def test_resolved_exactly_at_deadline_counts_as_met(self):
        a = self.make("2026-01-05 09:00:00", "High")
        sla.change_status(self.conn, a, "Resolved", at="2026-01-05 17:00:00")
        self.assertEqual(sla.sla_summary(self.conn, datetime(2026, 1, 6))["sla_compliance_pct"], 100.0)

    def test_empty_database_metrics(self):
        s = sla.sla_summary(self.conn)
        self.assertIsNone(s["sla_compliance_pct"])
        self.assertIsNone(s["avg_resolution_hours"])
        self.assertEqual(s["total_requests"], 0)

    def test_overdue_and_approaching(self):
        self.make("2026-01-05 09:00:00", "High", request_id="RQ-A", owner="Bob")    # due 17:00
        self.make("2026-01-05 09:00:00", "Medium", request_id="RQ-B", owner="Cy")   # due next day 09:00
        self.make("2026-01-05 09:00:00", "Low", request_id="RQ-C", owner="Cy")      # due +72h
        now = datetime(2026, 1, 6, 2, 0, 0)  # A overdue (due 17:00); B due 09:00 = 7h away; C due in 3 days
        b = sla.request_buckets(self.conn, now)
        self.assertEqual([r["request_id"] for r in b["overdue"]], ["RQ-A"])
        self.assertEqual([r["request_id"] for r in b["approaching"]], ["RQ-B"])
        self.assertEqual([r["request_id"] for r in b["on_track"]], ["RQ-C"])
        s = sla.sla_summary(self.conn, now)
        self.assertEqual((s["open_requests"], s["overdue_requests"], s["approaching_deadline"]), (3, 1, 1))

    def test_overdue_by_owner(self):
        self.make("2026-01-01 09:00:00", "High", request_id="RQ-A", owner="Bob")
        self.make("2026-01-01 09:00:00", "High", request_id="RQ-B", owner="Bob")
        self.make("2026-01-01 09:00:00", "High", request_id="RQ-C", owner="")
        self.assertEqual(sla.overdue_by_owner(self.conn, datetime(2026, 1, 3)), {"Bob": 2, "Unassigned": 1})

    def test_stage_durations_from_history(self):
        pk = self.make("2026-01-05 09:00:00", "Critical")  # New 09:00, Assigned 09:00
        sla.change_status(self.conn, pk, "In Progress", at="2026-01-05 10:00:00")
        sla.change_status(self.conn, pk, "Pending Info", at="2026-01-05 12:00:00")
        sla.change_status(self.conn, pk, "In Progress", at="2026-01-05 18:00:00")
        sla.change_status(self.conn, pk, "Resolved", at="2026-01-05 19:00:00")
        bn = sla.bottleneck_analysis(self.conn, datetime(2026, 1, 6))
        stages = {r["stage"]: r for r in bn["stages"]}
        self.assertEqual(stages["Assigned"]["total_hours"], 1.0)
        self.assertEqual(stages["In Progress"]["total_hours"], 3.0)
        self.assertEqual(stages["In Progress"]["visits"], 2)
        self.assertEqual(stages["Pending Info"]["avg_hours"], 6.0)
        self.assertEqual(bn["bottleneck"], "Pending Info")

    def test_open_stage_counts_up_to_now(self):
        pk = self.make("2026-01-05 09:00:00")
        d = [x for x in sla.stage_durations(self.conn, datetime(2026, 1, 5, 21, 0, 0)) if x["stage"] == "Assigned"]
        self.assertEqual(d[0]["hours"], 12.0)

    def test_reopen_clears_resolution(self):
        pk = self.make("2026-01-05 09:00:00")
        sla.change_status(self.conn, pk, "Resolved", at="2026-01-05 12:00:00")
        sla.change_status(self.conn, pk, "In Progress", at="2026-01-05 13:00:00")
        self.assertIsNone(self.conn.execute("SELECT resolved_at FROM requests WHERE id=?", (pk,)).fetchone()[0])

    def test_trend(self):
        a = self.make("2026-01-05 09:00:00", request_id="RQ-A")
        b = self.make("2026-02-05 09:00:00", request_id="RQ-B")
        sla.change_status(self.conn, a, "Resolved", at="2026-01-05 12:00:00")
        sla.change_status(self.conn, b, "Resolved", at="2026-02-06 12:00:00")
        t = sla.compliance_trend(self.conn)
        self.assertEqual([(x["month"], x["compliance_pct"]) for x in t], [("2026-01", 100.0), ("2026-02", 0.0)])

    def test_settings_update(self):
        sla.update_setting(self.conn, "sla_hours_High", 2)
        self.assertEqual(sla.sla_hours_for(self.conn, "High"), 2)
        with self.assertRaises(ValueError):
            sla.update_setting(self.conn, "sla_hours_High", "abc")
        with self.assertRaises(ValueError):
            sla.update_setting(self.conn, "evil", 1)


class TestKpis(unittest.TestCase):
    def test_overview_matches_data(self):
        conn = memory_db()
        rs.create_requirement(conn, req(req_id="REQ-001", status="Approved"))
        rs.create_requirement(conn, req(req_id="REQ-002", status="Approved"))
        rs.create_requirement(conn, req(req_id="REQ-003", status="Draft"))
        pk = 1
        docs_service.add_criterion(conn, pk, description="x")
        k = kpis.overview(conn)
        self.assertEqual(k["total_requirements"], 3)
        self.assertEqual(k["by_status"], {"Approved": 2, "Draft": 1})
        self.assertEqual(k["missing_acceptance_criteria"], 2)
        self.assertEqual(k["missing_uat_tests"], 3)


class TestImportExport(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()

    def test_import_valid(self):
        csv = "req_id,title,req_type,priority,status\nREQ-001,A,Functional,High,Draft\nREQ-002,B,Business,Low,Approved\n"
        r = imports.import_requirements_csv(self.conn, csv.encode())
        self.assertEqual((r["imported"], r["duplicates"], r["invalid"]), (2, 0, 0))

    def test_import_missing_columns(self):
        r = imports.import_requirements_csv(self.conn, b"req_id,title\nREQ-001,A\n")
        self.assertEqual(r["imported"], 0)
        self.assertIn("Missing required column", r["errors"][0])

    def test_import_duplicates_and_invalid(self):
        rs.create_requirement(self.conn, req(req_id="REQ-001"))
        csv = ("req_id,title,req_type,priority,status,due_date\n"
               "REQ-001,Existing,Functional,High,Draft,\n"
               "REQ-002,Ok,Functional,High,Draft,\n"
               "REQ-002,Same file dup,Functional,High,Draft,\n"
               "REQ-003,,Functional,High,Draft,\n"
               "REQ-004,Bad prio,Functional,Urgent,Draft,\n"
               "REQ-005,Bad date,Functional,High,Draft,99/99/2026\n")
        r = imports.import_requirements_csv(self.conn, csv)
        self.assertEqual((r["imported"], r["duplicates"], r["invalid"]), (1, 2, 3))

    def test_import_dependencies_within_file(self):
        csv = "req_id,title,req_type,priority,status,dependencies\nREQ-001,A,Functional,High,Draft,\nREQ-002,B,Functional,High,Draft,REQ-001;\n"
        csv = csv.replace("REQ-001;", "REQ-001")
        r = imports.import_requirements_csv(self.conn, csv)
        self.assertEqual(r["imported"], 2)
        self.assertEqual(self.conn.execute("SELECT dependencies FROM requirements WHERE req_id='REQ-002'").fetchone()[0], "REQ-001")

    def test_import_garbage_bytes(self):
        r = imports.import_requirements_csv(self.conn, b"")
        self.assertEqual(r["imported"], 0)
        self.assertTrue(r["errors"])

    def test_formula_injection_sanitised(self):
        for bad in ["=1+1", "+cmd", "-2+3", "@SUM(A1)", "\t=x"]:
            self.assertTrue(exports.sanitize_cell(bad).startswith("'"))
        self.assertEqual(exports.sanitize_cell("normal"), "normal")
        self.assertEqual(exports.sanitize_cell(5), 5)

    def test_csv_export_content_and_sanitising(self):
        rs.create_requirement(self.conn, req(title="=HYPERLINK(\"x\")"))
        data = exports.df_to_csv_bytes(exports.requirements_df(self.conn)).decode()
        self.assertIn("REQ-001", data)
        self.assertIn("'=HYPERLINK", data)
        self.assertNotIn(",=HYPERLINK", data)

    def test_excel_export_roundtrip(self):
        rs.create_requirement(self.conn, req(title="@evil"))
        blob = exports.dfs_to_excel_bytes({"Requirements": exports.requirements_df(self.conn),
                                           "Empty": pd.DataFrame()})
        sheets = pd.read_excel(io.BytesIO(blob), sheet_name=None)
        self.assertEqual(set(sheets), {"Requirements", "Empty"})
        self.assertEqual(sheets["Requirements"].loc[0, "title"], "'@evil")
        self.assertEqual(sheets["Requirements"].loc[0, "req_id"], "REQ-001")

    def test_markdown_reports_have_real_data(self):
        seed.seed_users(self.conn)
        seed.seed_sample_data(self.conn, now=datetime(2026, 6, 1, 12))
        self.assertIn("REQ-001", exports.requirements_markdown(self.conn))
        self.assertIn("Total requirements: **8**", exports.requirements_markdown(self.conn))
        self.assertIn("UAT-004", exports.traceability_markdown(self.conn))
        self.assertIn("Bottleneck stage", exports.sla_markdown(self.conn))


class TestSeed(unittest.TestCase):
    def test_seed_is_idempotent_and_deterministic(self):
        now = datetime(2026, 6, 1, 12)
        a, b = memory_db(), memory_db()
        seed.seed_users(a); seed.seed_users(b)
        self.assertTrue(seed.seed_sample_data(a, now=now))
        self.assertFalse(seed.seed_sample_data(a, now=now))
        seed.seed_sample_data(b, now=now)
        self.assertEqual(sla.sla_summary(a, now), sla.sla_summary(b, now))
        self.assertEqual(a.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 40)
        self.assertEqual(len(auth.list_users(a)), 3)
        self.assertIsNotNone(auth.authenticate(a, "admin", "Admin@12345")[0])


if __name__ == "__main__":
    unittest.main()
