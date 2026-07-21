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

    # Simple, on-brand login matching the dashboard's restrained theme:
    # Anthracite wordmark, one small orange accent rule, minimal text. No card
    # chrome or shadow — the internal app favours simplicity over decoration.
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap');
        .rc-login { max-width: 340px; margin: 14vh auto 0 auto; text-align: center;
            font-family: 'Lato', -apple-system, 'Segoe UI', Roboto, sans-serif; }
        .rc-mark { font-weight: 900; font-size: 30px; letter-spacing: 0.5px;
            color: #003B71; line-height: 1; }
        .rc-rule { width: 40px; height: 3px; background: #FF671D;
            margin: 12px auto 16px auto; }
        .rc-sub { font-weight: 700; font-size: 11px; letter-spacing: 2px;
            text-transform: uppercase; color: #909288; }
        </style>
        <div class="rc-login">
          <div class="rc-mark">RisCura</div>
          <div class="rc-rule"></div>
          <div class="rc-sub">Market News Dashboard</div>
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
    return False
