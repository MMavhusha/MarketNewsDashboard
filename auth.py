"""Simple password gate backed by Streamlit Secrets (key: APP_PASSWORD).

If no APP_PASSWORD secret is configured (e.g. local development), access is
allowed with a visible warning so the app is never silently unprotected in
production by accident.
"""
import hmac
import streamlit as st


def check_password() -> bool:
    try:
        expected = st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        st.session_state["_auth_ok"] = True
        st.session_state["_auth_warn"] = True
        return True

    if st.session_state.get("_auth_ok"):
        return True

    # On-brand login per RisCura Brand Spec v1.4 (web palette + Lato):
    # Anthracite #003B71 grounds, RisCura Orange #FF671D is the warm accent,
    # Ice #B7DCE1 softens the backdrop. Wordmark set as a single Anthracite
    # word with an orange accent rule (not split into two colours — the spec
    # forbids recreating the wordmark; this is a styled placeholder until the
    # official vector wordmark asset is added).
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap');
        .rc-login-wrap { max-width: 400px; margin: 9vh auto 0 auto; }
        .rc-card {
            background: #FFFFFF;
            border: 1px solid #E6ECEF;
            border-top: 4px solid #FF671D;
            border-radius: 12px;
            padding: 34px 34px 30px 34px;
            box-shadow: 0 10px 30px rgba(0,59,113,0.08);
            text-align: center;
        }
        .rc-mark {
            font-family: 'Lato', -apple-system, 'Segoe UI', Roboto, sans-serif;
            font-weight: 900; font-size: 30px; letter-spacing: 0.5px;
            color: #003B71; line-height: 1;
        }
        .rc-rule {
            width: 46px; height: 3px; background: #FF671D;
            margin: 12px auto 14px auto; border-radius: 2px;
        }
        .rc-sub {
            font-family: 'Lato', -apple-system, 'Segoe UI', Roboto, sans-serif;
            font-weight: 700; font-size: 11px; letter-spacing: 2px;
            text-transform: uppercase; color: #909288; margin-bottom: 4px;
        }
        .rc-tag {
            font-family: 'Lato', -apple-system, 'Segoe UI', Roboto, sans-serif;
            font-weight: 400; font-size: 13px; color: #212322;
            margin-top: 14px; margin-bottom: 2px;
        }
        </style>
        <div class="rc-login-wrap">
          <div class="rc-card">
            <div class="rc-mark">RisCura</div>
            <div class="rc-rule"></div>
            <div class="rc-sub">Market News Dashboard</div>
            <div class="rc-tag">Sign in to continue</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        pw = st.text_input("Access password", type="password", key="_pw_input",
                           placeholder="Access password",
                           label_visibility="collapsed")
        if pw:
            if hmac.compare_digest(pw, expected):
                st.session_state["_auth_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.markdown(
            "<div style=\"text-align:center;font-family:'Lato',sans-serif;"
            "font-size:11px;color:#909288;margin-top:16px;\">"
            "Invest with Care</div>",
            unsafe_allow_html=True)
    return False
