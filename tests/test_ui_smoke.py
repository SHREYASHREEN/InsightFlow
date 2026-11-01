"""UI smoke test using STUB streamlit/plotly modules.
It executes every page function for every role against seeded data to catch typos, wrong function names and
unhandled exceptions. It does NOT render anything and cannot judge layout - always check the real app visually."""
import sys
import types
import unittest
from datetime import date, datetime

from tests.helpers import memory_db


class Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, name): return getattr(STUB, name)


class Stub:
    def __init__(self):
        self.session_state = {}
        self.sidebar = Ctx()

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [Ctx() for _ in range(n)]

    def tabs(self, labels): return [Ctx() for _ in labels]
    def expander(self, *a, **k): return Ctx()
    def form(self, *a, **k): return Ctx()
    def text_input(self, label, value="", **k): return value
    def text_area(self, label, value="", **k): return value
    def number_input(self, label, value=0, **k): return value
    def checkbox(self, label, value=False, **k): return value
    def selectbox(self, label, options, index=0, **k): return list(options)[index] if len(list(options)) else None
    def multiselect(self, *a, **k): return []
    def date_input(self, *a, **k): return date.today()
    def radio(self, label, options, **k): return list(options)[0]
    def button(self, *a, **k): return False
    def form_submit_button(self, *a, **k): return False
    def download_button(self, *a, **k): return False
    def file_uploader(self, *a, **k): return None
    def __getattr__(self, name):
        return lambda *a, **k: None


STUB = Stub()


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = types.ModuleType("streamlit")
        st.__dict__.update({n: getattr(STUB, n) for n in dir(Stub) if not n.startswith("__")})
        st.session_state, st.sidebar = STUB.session_state, STUB.sidebar
        st.__getattr__ = lambda name: (lambda *a, **k: None)
        px = types.ModuleType("plotly.express")
        px.__getattr__ = lambda name: (lambda *a, **k: types.SimpleNamespace(update_yaxes=lambda *a, **k: None))
        px.colors = types.SimpleNamespace(sequential=types.SimpleNamespace(Teal_r=["#000"]))
        pkg = types.ModuleType("plotly"); pkg.express = px
        cls._saved = {k: sys.modules.get(k) for k in ("streamlit", "plotly", "plotly.express")}
        sys.modules.update({"streamlit": st, "plotly": pkg, "plotly.express": px})
        for m in [m for m in sys.modules if m.startswith("insightflow.ui")]:
            del sys.modules[m]
        from insightflow import ui
        cls.ui = ui

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
        sys.modules.pop("insightflow.ui", None)

    def test_all_pages_all_roles(self):
        from insightflow import seed
        conn = memory_db()
        seed.seed_users(conn)
        seed.seed_sample_data(conn, now=datetime(2026, 6, 1, 12))
        pages = [self.ui.page_overview, self.ui.page_requirements, self.ui.page_documentation,
                 self.ui.page_traceability, self.ui.page_requests, self.ui.page_reports, self.ui.page_admin]
        for role in ("Admin", "Business Analyst", "Viewer"):
            user = {"id": 1, "username": "u", "full_name": "U", "role": role}
            for page in pages:
                page(conn, user)
        self.ui.login_page(conn)

    def test_empty_database_pages(self):
        conn = memory_db()
        user = {"id": 1, "username": "u", "full_name": "U", "role": "Admin"}
        for page in (self.ui.page_overview, self.ui.page_requirements, self.ui.page_documentation,
                     self.ui.page_traceability, self.ui.page_requests, self.ui.page_reports):
            page(conn, user)
