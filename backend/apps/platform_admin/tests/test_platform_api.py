from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.testing import api_client, login_client, make_school, make_user
from apps.tenants.models import School, SchoolStatus

BASE = "/api/v1/platform"
LIST_URLS = [f"{BASE}/dashboard/", f"{BASE}/schools/", f"{BASE}/audit-logs/", f"{BASE}/audit-logs/actions/"]


class PlatformAccessTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.teacher = make_user(self.school, Role.TEACHER)
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.detail = f"{BASE}/schools/{self.school.id}/"

    def test_anonymous_gets_401(self):
        client = api_client()
        for url in [*LIST_URLS, self.detail, f"{self.detail}users/", f"{self.detail}activity/"]:
            self.assertEqual(client.get(url).status_code, 401, url)
        self.assertEqual(client.post(f"{self.detail}suspend/", {"reason": "x" * 5, "confirm": True}).status_code, 401)

    def test_school_users_get_403_on_every_platform_endpoint(self):
        for user in (self.admin, self.teacher):
            client = login_client(user)
            for url in [*LIST_URLS, self.detail, f"{self.detail}users/", f"{self.detail}activity/"]:
                self.assertEqual(client.get(url).status_code, 403, (user.role, url))
            for action in ("suspend", "deactivate", "reactivate"):
                response = client.post(f"{self.detail}{action}/", {"reason": "nope nope", "confirm": True})
                self.assertEqual(response.status_code, 403, action)
        self.school.refresh_from_db()
        self.assertEqual(self.school.status, SchoolStatus.ACTIVE)

    def test_super_admin_gets_200(self):
        client = login_client(self.root)
        for url in [*LIST_URLS, self.detail, f"{self.detail}users/", f"{self.detail}activity/"]:
            self.assertEqual(client.get(url).status_code, 200, url)


class PlatformDashboardTests(TestCase):
    def test_dashboard_reports_real_counts(self):
        a, b, c = make_school("A"), make_school("B"), make_school("C")
        School.objects.filter(pk=b.pk).update(status=SchoolStatus.SUSPENDED)
        School.objects.filter(pk=c.pk).update(status=SchoolStatus.INACTIVE)
        make_user(a, Role.SCHOOL_ADMIN)
        make_user(a, Role.TEACHER)
        make_user(b, Role.SCHOOL_ADMIN)
        root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")

        data = login_client(root).get(f"{BASE}/dashboard/").json()["data"]
        self.assertEqual(data["schools"]["total"], 3)
        self.assertEqual(data["schools"]["by_status"], {"ACTIVE": 1, "SUSPENDED": 1, "INACTIVE": 1})
        self.assertEqual(data["users"]["total"], 3)  # the Super Admin is not a school user
        self.assertEqual(data["users"]["by_role"]["SCHOOL_ADMIN"], 2)
        self.assertEqual(data["users"]["by_role"]["TEACHER"], 1)
        self.assertEqual(data["registrations"]["last_30_days"], 3)
        self.assertEqual(len(data["registrations"]["daily"]), 30)
        self.assertEqual(data["registrations"]["daily"][-1]["date"], timezone.now().date().isoformat())
        self.assertEqual(data["registrations"]["daily"][-1]["count"], 3)
        self.assertEqual(len(data["recent_schools"]), 3)

    def test_old_schools_fall_outside_the_30_day_window(self):
        old = make_school("Old")
        School.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=45))
        root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        data = login_client(root).get(f"{BASE}/dashboard/").json()["data"]
        self.assertEqual(data["schools"]["total"], 1)
        self.assertEqual(data["registrations"]["last_30_days"], 0)

    def test_empty_platform_has_zeroes_not_errors(self):
        root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        data = login_client(root).get(f"{BASE}/dashboard/").json()["data"]
        self.assertEqual(data["schools"]["total"], 0)
        self.assertEqual(data["recent_schools"], [])


class PlatformSchoolListTests(TestCase):
    def setUp(self):
        self.alpha = make_school("Alpha Academy", city="Lahore")
        self.beta = make_school("Beta School", city="Karachi")
        self.gamma = make_school("Gamma College", city="Islamabad")
        School.objects.filter(pk=self.beta.pk).update(status=SchoolStatus.SUSPENDED)
        self.alpha_admin = make_user(self.alpha, Role.SCHOOL_ADMIN, email="admin@alpha.test")
        make_user(self.alpha, Role.TEACHER)
        make_user(self.alpha, Role.TEACHER, is_active=False)
        make_user(self.beta, Role.SCHOOL_ADMIN, email="admin@beta.test")
        self.client = login_client(make_user(role=Role.SUPER_ADMIN, email="root@platform.test"))

    def rows(self, query=""):
        response = self.client.get(f"{BASE}/schools/{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["results"]

    def test_counts_and_admin_email_are_annotated(self):
        by_name = {row["name"]: row for row in self.rows()}
        self.assertEqual(by_name["Alpha Academy"]["user_count"], 3)
        self.assertEqual(by_name["Alpha Academy"]["admin_email"], "admin@alpha.test")
        self.assertEqual(by_name["Gamma College"]["user_count"], 0)
        self.assertIsNone(by_name["Gamma College"]["admin_email"])

    def test_filter_by_status(self):
        self.assertEqual([r["name"] for r in self.rows("?status=SUSPENDED")], ["Beta School"])
        self.assertEqual(len(self.rows("?status=ACTIVE")), 2)

    def test_invalid_status_is_400(self):
        self.assertEqual(self.client.get(f"{BASE}/schools/?status=BOGUS").status_code, 400)

    def test_search_matches_name_city_and_email(self):
        self.assertEqual([r["name"] for r in self.rows("?search=alpha")], ["Alpha Academy"])
        self.assertEqual([r["name"] for r in self.rows("?search=karachi")], ["Beta School"])

    def test_ordering_whitelist(self):
        self.assertEqual(self.rows("?ordering=name")[0]["name"], "Alpha Academy")
        self.assertEqual(self.rows("?ordering=-user_count")[0]["name"], "Alpha Academy")
        self.assertEqual(len(self.rows("?ordering=password")), 3)  # unknown field falls back, never errors

    def test_pagination(self):
        data = self.client.get(f"{BASE}/schools/?page_size=2").json()["data"]
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["pagination"]["total"], 3)
        self.assertEqual(data["pagination"]["total_pages"], 2)

    def test_detail_includes_admin_and_counts(self):
        data = self.client.get(f"{BASE}/schools/{self.alpha.id}/").json()["data"]
        self.assertEqual(data["user_count"], 3)
        self.assertEqual(data["active_user_count"], 2)
        self.assertEqual(data["admin"]["email"], "admin@alpha.test")
        self.assertEqual(data["status"], SchoolStatus.ACTIVE)

    def test_unknown_and_malformed_ids_are_404(self):
        self.assertEqual(self.client.get(f"{BASE}/schools/00000000-0000-0000-0000-000000000000/").status_code, 404)
        self.assertEqual(self.client.get(f"{BASE}/schools/not-a-uuid/").status_code, 404)


class PlatformTenantTabsTests(TestCase):
    def setUp(self):
        self.alpha, self.beta = make_school("Alpha"), make_school("Beta")
        make_user(self.alpha, Role.SCHOOL_ADMIN, email="a@alpha.test")
        make_user(self.beta, Role.SCHOOL_ADMIN, email="b@beta.test")
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)

    def test_users_tab_lists_only_that_school_and_is_audited(self):
        response = self.client.get(f"{BASE}/schools/{self.alpha.id}/users/")
        self.assertEqual(response.status_code, 200)
        emails = {u["email"] for u in response.json()["data"]["results"]}
        self.assertEqual(emails, {"a@alpha.test"})
        entry = AuditLog.objects.get(action=AuditAction.PLATFORM_VIEWED_SCHOOL_USERS)
        self.assertEqual((entry.actor_id, entry.school_id), (self.root.id, self.alpha.id))
        self.assertNotIn("password", response.content.decode())

    def test_activity_tab_only_contains_that_schools_events(self):
        AuditLog.objects.create(action=AuditAction.LOGIN, school=self.alpha, description="alpha event")
        AuditLog.objects.create(action=AuditAction.LOGIN, school=self.beta, description="beta event")
        rows = self.client.get(f"{BASE}/schools/{self.alpha.id}/activity/").json()["data"]["results"]
        self.assertEqual({r["description"] for r in rows}, {"alpha event"})
        self.assertTrue(all(r["school_id"] == str(self.alpha.id) for r in rows))


class SchoolLifecycleApiTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@alpha.test")
        self.teacher = make_user(self.school, Role.TEACHER)
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)
        self.admin_client = login_client(self.admin)
        self.url = f"{BASE}/schools/{self.school.id}"

    def act(self, action, **body):
        return self.client.post(f"{self.url}/{action}/", body)

    def status(self):
        self.school.refresh_from_db()
        return self.school.status

    def test_confirmation_and_reason_are_enforced_server_side(self):
        self.assertEqual(self.act("suspend", reason="Unpaid invoice").status_code, 400)  # no confirm
        self.assertEqual(self.act("suspend", reason="Unpaid invoice", confirm=False).status_code, 400)
        no_reason = self.act("suspend", confirm=True)
        self.assertEqual(no_reason.status_code, 400)
        self.assertIn("reason", no_reason.json()["errors"])
        self.assertEqual(self.act("deactivate", reason="  ", confirm=True).status_code, 400)
        self.assertEqual(self.status(), SchoolStatus.ACTIVE)

    def test_suspend_blocks_the_school_but_keeps_all_data(self):
        users_before = User.objects.filter(school=self.school).count()
        response = self.act("suspend", reason="Unpaid invoice", confirm=True)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["status"], SchoolStatus.SUSPENDED)
        self.assertEqual(data["status_reason"], "Unpaid invoice")
        self.assertEqual(data["status_changed_by_name"], self.root.full_name)
        self.assertEqual(User.objects.filter(school=self.school).count(), users_before)

        blocked = self.admin_client.get("/api/v1/school/users/")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "school_disabled")
        self.assertEqual(self.admin_client.get("/api/v1/auth/me/").json()["data"]["school"]["status"], SchoolStatus.SUSPENDED)

    def test_audit_entry_records_actor_school_and_reason(self):
        self.act("suspend", reason="Unpaid invoice", confirm=True)
        entry = AuditLog.objects.get(action=AuditAction.SCHOOL_SUSPENDED)
        self.assertEqual((entry.actor_id, entry.school_id, entry.actor_role), (self.root.id, self.school.id, Role.SUPER_ADMIN))
        self.assertIn("Unpaid invoice", entry.description)
        self.assertEqual(entry.metadata["to"], SchoolStatus.SUSPENDED)

    def test_full_cycle_suspend_deactivate_reactivate(self):
        self.assertEqual(self.act("suspend", reason="Review", confirm=True).status_code, 200)
        self.assertEqual(self.act("deactivate", reason="Closed", confirm=True).status_code, 200)
        self.assertEqual(self.status(), SchoolStatus.INACTIVE)
        self.assertEqual(self.admin_client.get("/api/v1/school/users/").status_code, 403)

        response = self.act("reactivate", confirm=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status_reason"], "")  # the old reason no longer applies
        self.assertEqual(self.status(), SchoolStatus.ACTIVE)
        self.assertEqual(self.admin_client.get("/api/v1/school/users/").status_code, 200)
        actions = set(AuditLog.objects.filter(school=self.school).values_list("action", flat=True))
        self.assertTrue({AuditAction.SCHOOL_SUSPENDED, AuditAction.SCHOOL_DEACTIVATED, AuditAction.SCHOOL_REACTIVATED} <= actions)

    def test_invalid_transitions_are_409_and_change_nothing(self):
        reactivate_active = self.act("reactivate", confirm=True)
        self.assertEqual(reactivate_active.status_code, 409)
        self.assertEqual(reactivate_active.json()["code"], "invalid_transition")

        self.act("suspend", reason="Review", confirm=True)
        again = self.act("suspend", reason="Review again", confirm=True)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(AuditLog.objects.filter(action=AuditAction.SCHOOL_SUSPENDED).count(), 1)

        self.act("deactivate", reason="Closed", confirm=True)
        self.assertEqual(self.act("suspend", reason="Review", confirm=True).status_code, 409)
        self.assertEqual(self.status(), SchoolStatus.INACTIVE)

    def test_status_never_changes_through_other_endpoints(self):
        self.admin_client.patch("/api/v1/school/profile/", {"status": "SUSPENDED", "name": "Renamed School"})
        self.assertEqual(self.status(), SchoolStatus.ACTIVE)
        self.assertIn(self.client.patch(f"{self.url}/", {"status": "SUSPENDED"}).status_code, (403, 405))
        self.assertEqual(self.status(), SchoolStatus.ACTIVE)

    def test_lifecycle_endpoints_reject_other_http_methods(self):
        self.assertIn(self.client.get(f"{self.url}/suspend/").status_code, (403, 405))
        self.assertIn(self.client.delete(f"{self.url}/").status_code, (403, 405))
        self.assertTrue(School.objects.filter(pk=self.school.pk).exists())


class PlatformAuditLogTests(TestCase):
    def setUp(self):
        self.alpha, self.beta = make_school("Alpha"), make_school("Beta")
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)
        AuditLog.objects.create(action=AuditAction.USER_CREATED, school=self.alpha, actor_role=Role.SCHOOL_ADMIN, description="created teacher Sana")
        AuditLog.objects.create(action=AuditAction.USER_CREATED, school=self.beta, actor_role=Role.SCHOOL_ADMIN, description="created teacher Omar")
        AuditLog.objects.create(action=AuditAction.SCHOOL_SUSPENDED, school=self.alpha, actor_role=Role.SUPER_ADMIN, description="School suspended")

    def rows(self, query):
        response = self.client.get(f"{BASE}/audit-logs/?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["results"]

    def test_filters(self):
        self.assertEqual(len(self.rows(f"action={AuditAction.USER_CREATED}")), 2)
        self.assertEqual(len(self.rows(f"school={self.alpha.id}&action={AuditAction.USER_CREATED}")), 1)
        self.assertEqual(len(self.rows(f"actor_role={Role.SUPER_ADMIN}")), 2)  # includes the root login
        self.assertEqual(len(self.rows("search=Omar")), 1)

    def test_date_filters(self):
        today = timezone.now().date()
        self.assertGreaterEqual(len(self.rows(f"date_from={today.isoformat()}")), 3)
        self.assertEqual(self.rows(f"date_to={(today - timedelta(days=1)).isoformat()}"), [])

    def test_invalid_filters_are_400(self):
        for query in ("school=not-a-uuid", "date_from=yesterday", "date_to=2026-13-45"):
            self.assertEqual(self.client.get(f"{BASE}/audit-logs/?{query}").status_code, 400, query)

    def test_newest_first_and_platform_fields_present(self):
        rows = self.rows("")
        stamps = [r["created_at"] for r in rows]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        self.assertIn("ip", rows[0])
        self.assertIn("metadata", rows[0])

    def test_action_catalogue(self):
        actions = self.client.get(f"{BASE}/audit-logs/actions/").json()["data"]
        self.assertIn(AuditAction.SCHOOL_SUSPENDED, actions)
        self.assertEqual(actions, sorted(actions))
