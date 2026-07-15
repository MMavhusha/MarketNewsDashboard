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

    st.markdown(
        """
        <div style="max-width:380px;margin:12vh auto 0 auto;text-align:center;">
          <div style="font-size:26px;font-weight:800;color:#10192E;">
            Ris<span style="color:#5B8DEF;">Cura</span>
          </div>
          <div style="font-size:12px;color:#667085;letter-spacing:1.5px;
                      text-transform:uppercase;margin-bottom:18px;">
            Market News Dashboard
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        pw = st.text_input("Access password", type="password", key="_pw_input")
        if pw:
            if hmac.compare_digest(pw, expected):
                st.session_state["_auth_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False
