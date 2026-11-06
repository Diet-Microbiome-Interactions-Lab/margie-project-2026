"""A sign-in from a browser MARGIE does not know asks for a code emailed to the account's Purdue
address (sent by the cluster, as run emails are); a confirmed browser may be remembered for 7, 15, 20
or 30 days, the browser the account was made in is remembered, and each new browser that signs in is
told to the same address (api/browser_check.py)."""

import re
from unittest.mock import patch

import pytest

from bioinformatics_tools.api import access, browser_check
from tests.test_access import _ssh
from tests.test_api import client, test_rsa_key  # noqa: F401 (fixtures)

pytestmark = pytest.mark.browser_check

AUTH = "bioinformatics_tools.api.routers.auth"
REG = {"username": "u1", "password": "S3cur3P@ss!", "cluster_username": "bob", "cluster_host": "login01.cluster.purdue.edu"}


@pytest.fixture(autouse=True)
def _fresh_limits():
    for g in (access.SIGNIN_BY_NAME, access.SIGNIN_BY_ADDRESS, access.SIGNUP_BY_ADDRESS, browser_check.CODES_BY_NAME):
        g.reset()
    yield


class Mail:
    """The cluster's mail command: what was sent, and whether it takes the message."""

    def __init__(self, works=True):
        self.sent, self.works = [], works

    def __call__(self, connection, to, subject, body):
        if self.works:
            self.sent.append((to, subject, body))
        return self.works

    def code(self):
        return re.search(r"enter this code: (\d{6})", self.sent[-1][2]).group(1)


def _sign_up(client, test_rsa_key):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), patch(f"{AUTH}.ensure_remote_dane_wf"):
        r = client.post("/v1/auth/register", json={**REG, "private_key": test_rsa_key})
    assert r.status_code == 201, r.text
    return r.json()


def _sign_in(client, browser=None, mail=None):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), \
         patch("bioinformatics_tools.api.browser_check.run_mail.send", side_effect=mail or Mail()):
        return client.post("/v1/auth/login", json={"username": "u1", "password": REG["password"], **({"browser": browser} if browser else {})},
                           headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Chrome/130.0 Safari/537.36"})


def _verify(client, challenge, code, days=0, mail=None):  # noqa: F811
    with patch(f"{AUTH}.make_user_connection", return_value=_ssh()), \
         patch("bioinformatics_tools.api.browser_check.run_mail.send", side_effect=mail or Mail()), _run_now():
        return client.post("/v1/auth/login/verify", json={"challenge": challenge, "code": code, "remember_days": days})


class _run_now:
    """Runs the new-browser notice at once, so a test sees its email."""

    def __enter__(self):
        class T:
            def __init__(self, target, daemon=True):
                self.target = target

            def start(self):
                self.target()
        self.p = patch("bioinformatics_tools.api.browser_check.threading.Thread", T)
        self.p.start()

    def __exit__(self, *a):
        self.p.stop()


def test_the_browser_an_account_is_made_in_is_remembered(client, test_rsa_key):  # noqa: F811
    made = _sign_up(client, test_rsa_key)
    assert made["browser"]
    r = _sign_in(client, browser=made["browser"])
    assert r.status_code == 200 and r.json()["access_token"] and not r.json()["verify"]


def test_a_new_browser_gets_a_code_at_the_purdue_address_and_may_be_remembered(client, test_rsa_key):  # noqa: F811
    _sign_up(client, test_rsa_key)
    mail = Mail()
    r = _sign_in(client, mail=mail)
    d = r.json()
    assert r.status_code == 200 and d["verify"] and not d["access_token"] and d["sent_to"] == "b…b@purdue.edu"
    to, subject, body = mail.sent[-1]
    assert to == ["bob@purdue.edu"] and "Chrome on macOS" in body and mail.code() in subject
    # A wrong code says how many tries are left; the right one signs in and remembers the browser.
    wrong = _verify(client, d["challenge"], "000000" if mail.code() != "000000" else "111111")
    assert wrong.status_code == 401 and "4 tries left" in wrong.json()["detail"]
    notice = Mail()
    ok = _verify(client, d["challenge"], mail.code(), days=15, mail=notice)
    assert ok.status_code == 200 and ok.json()["access_token"] and ok.json()["browser"]
    assert notice.sent and notice.sent[-1][1] == "MARGIE: a new browser signed in" and "remembered for 15 days" in notice.sent[-1][2]
    # The code works once; the browser is now known.
    assert _verify(client, d["challenge"], mail.code()).status_code == 401
    again = _sign_in(client, browser=ok.json()["browser"])
    assert again.json()["access_token"] and not again.json()["verify"]


def test_not_remembered_or_forgotten_browsers_are_asked_again(client, test_rsa_key):  # noqa: F811
    _sign_up(client, test_rsa_key)
    mail = Mail()
    d = _sign_in(client, mail=mail).json()
    ok = _verify(client, d["challenge"], mail.code(), days=3)  # not one of the choices: not remembered
    assert ok.status_code == 200 and ok.json()["browser"] == ""
    mail = Mail()
    d = _sign_in(client, mail=mail).json()
    kept = _verify(client, d["challenge"], mail.code(), days=30).json()
    headers = {"Authorization": f"Bearer {kept['access_token']}"}
    listed = client.get("/v1/auth/browsers", headers=headers).json()["browsers"]
    assert any("Chrome on macOS" in b["label"] for b in listed)
    assert client.delete("/v1/auth/browsers", headers=headers).json()["forgotten"] >= 1
    assert _sign_in(client, browser=kept["browser"]).json()["verify"]


def test_too_many_wrong_codes_end_the_code(client, test_rsa_key):  # noqa: F811
    _sign_up(client, test_rsa_key)
    mail = Mail()
    d = _sign_in(client, mail=mail).json()
    bad = "000000" if mail.code() != "000000" else "111111"
    for _ in range(browser_check.CODE_TRIES):
        _verify(client, d["challenge"], bad)
    r = _verify(client, d["challenge"], mail.code())
    assert r.status_code == 401 and "Sign in again" in r.json()["detail"]


def test_no_code_no_sign_in_when_the_cluster_cannot_send_it(client, test_rsa_key):  # noqa: F811
    _sign_up(client, test_rsa_key)
    r = _sign_in(client, mail=Mail(works=False))
    assert r.status_code == 503 and "could not send" in r.json()["detail"] and "access_token" not in r.json()


def test_codes_are_limited_per_username(client, test_rsa_key):  # noqa: F811
    _sign_up(client, test_rsa_key)
    for _ in range(5):
        assert _sign_in(client).json()["verify"]
    assert _sign_in(client).status_code == 429


def test_the_label_and_the_mask():
    class R:
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit Chrome/130 Safari/537 Edg/130", "x-real-ip": "203.0.113.5"}
        client = None
    assert browser_check.label(R()) == "Edge on Windows, from 203.0.113.5"
    assert browser_check.masked("jdoe@purdue.edu") == "j…e@purdue.edu"
