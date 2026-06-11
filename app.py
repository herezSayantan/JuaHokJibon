import streamlit as st
import pandas as pd
import hashlib
from data_manager import (
    init_data, load_table, save_table, update_match_and_scores, 
    update_match_teams, delete_tournament, USERS_FILE, MATCHES_FILE, PREDICTIONS_FILE
)

# --- CONFIGURATION ---
init_data()
st.set_page_config(page_title="🏆 World Cup Predictor", layout="wide")
st.title("🏆 FIFA WCUP 26 - JUAAaaa")

# --- CDN FLAG HELPER ---
def get_flag_html(team_name):
    """Returns an HTML img tag pointing to the official FlagCDN API."""
    clean_name = str(team_name).replace("MX ", "").replace("ZA ", "").replace("KR ", "").strip()
    slug = clean_name.lower().replace(" ", "-")
    url = f"https://flagcdn.com/w40/{slug}.png"
    return f'<img src="{url}" width="30">'

# --- SESSION STATE INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": None, "user_id": None, "role": None})

def check_login(user, pwd):
    df = load_table(USERS_FILE)
    hpw = hashlib.sha256(pwd.encode()).hexdigest()
    match = df[(df['username'] == user) & (df['password'] == hpw) & (df['status'] == 'active')]
    if not match.empty:
        st.session_state.update({"logged_in": True, "username": user, "user_id": int(match.iloc[0]['user_id']), "role": match.iloc[0]['role']})
        st.rerun()
    else:
        st.error("Invalid credentials or deactivated account.")

# --- LOGIN / SIGN UP SCREENS ---
if not st.session_state.logged_in:
    t1, t2 = st.tabs(["🔑 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Log In"): check_login(u, p)
    with t2:
        su_u = st.text_input("New Username")
        su_p = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            df = load_table(USERS_FILE)
            if su_u in df['username'].values:
                st.error("Username taken.")
            elif su_u and su_p:
                new_id = df['user_id'].max() + 1 if not df.empty else 1
                hpw = hashlib.sha256(su_p.encode()).hexdigest()
                df = pd.concat([df, pd.DataFrame([{"user_id": new_id, "username": su_u, "password": hpw, "role": "user", "status": "active"}])], ignore_index=True)
                save_table(df, USERS_FILE)
                st.success("Registered! Go to Login tab.")
    st.stop()

# --- SIDEBAR NAVIGATION ---
st.sidebar.write(f"Logged in as: **{st.session_state.username}** ({st.session_state.role})")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

menu = ["📊 Leaderboard", "⚽ Predictions", "🛠️ Admin"] if st.session_state.role == "admin" else ["📊 Leaderboard", "⚽ Predictions"]
choice = st.sidebar.radio("Menu", menu)

# --- 1. LEADERBOARD ---
if choice == "📊 Leaderboard":
    st.header("🏆 Live Standings")
    u_df = load_table(USERS_FILE)
    p_df = load_table(PREDICTIONS_FILE)
    active_users = u_df[(u_df['status'] == 'active') & (u_df['role'] != 'admin')]
    scores = p_df.groupby("user_id")["points_earned"].sum().reset_index()
    leaderboard = pd.merge(active_users, scores, on="user_id", how="left").fillna(0)
    leaderboard = leaderboard.sort_values(by="points_earned", ascending=False).reset_index(drop=True)
    
    for idx, row in leaderboard.iterrows():
        medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else "🏃"))
        st.subheader(f"{medal} Rank {idx+1}: {row['username']} — `{row['points_earned']} pts`")

# --- 2. PREDICTIONS ---
elif choice == "⚽ Predictions":
    st.header("Make Predictions")
    
    if st.session_state.role == "admin":
        st.warning("🔒 You are logged in as Admin. You can inspect match fixtures and group predictions, but you are not permitted to submit predictions.")

    m_df = load_table(MATCHES_FILE)
    p_df = load_table(PREDICTIONS_FILE)
    u_df = load_table(USERS_FILE)
    
    if m_df.empty:
        st.info("No matches available yet. Ask your Admin to upload the schedule!")
    else:
        tournaments = m_df['tournament'].unique()
        selected_t = st.selectbox("Filter by Tournament", tournaments)
        filtered_matches = m_df[m_df['tournament'] == selected_t]
        
        for _, match in filtered_matches.iterrows():
            st.write("---")
            col_teamA, col_inputA, col_inputB, col_teamB = st.columns([3,2,2,3])
            
            # Integrated FlagCDN Flags into the Team Headers with prefix clearing
            with col_teamA: 
                st.markdown(f"### {get_flag_html(match['team_A'])} {match['team_A'].replace('MX ','').replace('ZA ','').replace('KR ','')}", unsafe_allow_html=True)
            with col_teamB: 
                st.markdown(f"### {get_flag_html(match['team_B'])} {match['team_B'].replace('MX ','').replace('ZA ','').replace('KR ','')}", unsafe_allow_html=True)
            
            user_pred = p_df[(p_df['user_id'] == st.session_state.user_id) & (p_df['match_id'] == match['match_id'])]
            val_A = int(user_pred.iloc[0]['pred_score_A']) if not user_pred.empty else 0
            val_B = int(user_pred.iloc[0]['pred_score_B']) if not user_pred.empty else 0
            
            is_fin = match['status'] == 'Finished'
            is_admin = st.session_state.role == 'admin'
            lock_fields = is_fin or is_admin
            
            with col_inputA: p_A = st.number_input(f"Score {match['team_A'].replace('MX ','').replace('ZA ','').replace('KR ','')}", 0, 100, val_A, key=f"A_{match['match_id']}", disabled=lock_fields)
            with col_inputB: p_B = st.number_input(f"Score {match['team_B'].replace('MX ','').replace('ZA ','').replace('KR ','')}", 0, 100, val_B, key=f"B_{match['match_id']}", disabled=lock_fields)
            
            # Action Row
            btn_col1, btn_col2 = st.columns([1, 4])
            
            with btn_col1:
                if is_fin:
                    st.caption(f"🔒 Match Settled: {int(match['actual_score_A'])} - {int(match['actual_score_B'])}. Points: {user_pred.iloc[0]['points_earned'] if not user_pred.empty else 0}")
                elif is_admin:
                    st.caption("🚫 Admin Submission Disabled")
                else:
                    if st.button("Submit Prediction", key=f"btn_{match['match_id']}"):
                        p_df = load_table(PREDICTIONS_FILE)
                        p_df = p_df[~((p_df['user_id'] == st.session_state.user_id) & (p_df['match_id'] == match['match_id']))]
                        new_pred = pd.DataFrame([{"user_id": st.session_state.user_id, "match_id": match['match_id'], "pred_score_A": p_A, "pred_score_B": p_B, "points_earned": 0.0}])
                        p_df = pd.concat([p_df, new_pred], ignore_index=True)
                        save_table(p_df, PREDICTIONS_FILE)
                        st.success("Prediction Saved!")
                        st.rerun()
            
            with st.expander("🔍 See Group Predictions"):
                match_preds = p_df[p_df['match_id'] == match['match_id']]
                if match_preds.empty:
                    st.info("No members have submitted predictions for this match yet.")
                else:
                    display_df = pd.merge(match_preds, u_df, on="user_id", how="inner")
                    for _, p_row in display_df.iterrows():
                        is_current_user = " (You)" if p_row['user_id'] == st.session_state.user_id else ""
                        st.write(f"👤 **{p_row['username']}{is_current_user}** predicted: `{int(p_row['pred_score_A'])} - {int(p_row['pred_score_B'])}`")

# --- 3. ADMIN PANEL ---
elif choice == "🛠️ Admin" and st.session_state.role == "admin":
    st.header("Admin Dashboard")
    t1, t2, t3, t4, t5, t6 = st.tabs(["📁 Upload Schedule", "🎯 Settle Scores", "✏️ Edit Knockout Teams", "👁️ View All Predictions", "🗑️ Remove Tournament", "👥 Manage Users"])
    
    # Tab 1: Uploading Schedule CSV
    with t1:
        st.subheader("Upload Tournament CSV File")
        uploaded_file = st.file_uploader("Select your complete_world_cup_schedule.csv file", type=["csv"])
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                if {"tournament", "team_A", "team_B"}.issubset(uploaded_df.columns):
                    if st.button("Import Entire Schedule Now"):
                        m_df = load_table(MATCHES_FILE)
                        start_id = m_df['match_id'].max() + 1 if not m_df.empty else 1
                        uploaded_df['match_id'] = range(int(start_id), int(start_id + len(uploaded_df)))
                        uploaded_df['actual_score_A'] = ""
                        uploaded_df['actual_score_B'] = ""
                        uploaded_df['status'] = "Pending"
                        uploaded_df = uploaded_df[["match_id", "tournament", "team_A", "team_B", "actual_score_A", "actual_score_B", "status"]]
                        save_table(pd.concat([m_df, uploaded_df], ignore_index=True), MATCHES_FILE)
                        st.success("Entire schedule uploaded perfectly!")
                        st.rerun()
                else:
                    st.error("Missing headers. CSV needs exactly: tournament, team_A, team_B")
            except Exception as e:
                st.error(f"Error reading file: {e}")
                
    # Tab 2: Settle Scores
    with t2:
        m_df = load_table(MATCHES_FILE)
        p_matches = m_df[m_df['status'] == 'Pending']
        if p_matches.empty:
            st.info("No matches waiting to be settled.")
        else:
            for _, m in p_matches.iterrows():
                st.write(f"**Match ID {m['match_id']} | {m['tournament']}**: {get_flag_html(m['team_A'])} {m['team_A']} vs {get_flag_html(m['team_B'])} {m['team_B']}")
                col1, col2, col3 = st.columns(3)
                with col1: sA = st.number_input(f"{m['team_A']} Score", 0, 100, key=f"sA_{m['match_id']}")
                with col2: sB = st.number_input(f"{m['team_B']} Score", 0, 100, key=f"sB_{m['match_id']}")
                with col3: 
                    st.write("")
                    if st.button("Save & Process Points", key=f"set_{m['match_id']}"):
                        update_match_and_scores(m['match_id'], sA, sB)
                        st.success("Scores processed!")
                        st.rerun()

    # Tab 3: Overwrite Placeholders
    with t3:
        st.subheader("Swap Placeholders with Actual Qualified Teams")
        m_df = load_table(MATCHES_FILE)
        
        if m_df.empty:
            st.info("No schedule exists yet.")
        else:
            match_options = {f"ID {r['match_id']}: {r['team_A']} vs {r['team_B']}": r['match_id'] for _, r in m_df.iterrows()}
            selected_match_str = st.selectbox("Select Match to Modify", list(match_options.keys()))
            target_id = match_options[selected_match_str]
            current_match = m_df[m_df['match_id'] == target_id].iloc[0]
            
            col_edit1, col_edit2 = st.columns(2)
            with col_edit1:
                new_A = st.text_input("Update Team A", value=str(current_match['team_A']))
            with col_edit2:
                new_B = st.text_input("Update Team B", value=str(current_match['team_B']))
                
            if st.button("Save Team Adjustments"):
                update_match_teams(target_id, new_A, new_B)
                st.success("Teams updated successfully!")
                st.rerun()

    # Tab 4: Master View for Admin
    with t4:
        st.subheader("Master Prediction Viewer")
        st.caption("A bird's-eye view of all member predictions submitted so far.")
        
        p_df = load_table(PREDICTIONS_FILE)
        m_df = load_table(MATCHES_FILE)
        u_df = load_table(USERS_FILE)
        
        if p_df.empty:
            st.info("No predictions have been submitted by any users yet.")
        else:
            master_df = p_df.merge(u_df[['user_id', 'username']], on='user_id')
            master_df = master_df.merge(m_df[['match_id', 'tournament', 'team_A', 'team_B']], on='match_id')
            
            # Apply CDN flags to the master DataFrame view dynamically!
            master_df['Match'] = master_df['team_A'].apply(get_flag_html) + " " + master_df['team_A'] + " vs " + master_df['team_B'].apply(get_flag_html) + " " + master_df['team_B']
            master_df['Predicted Score'] = master_df['pred_score_A'].astype(int).astype(str) + " - " + master_df['pred_score_B'].astype(int).astype(str)
            
            display_cols = master_df[['tournament', 'Match', 'username', 'Predicted Score']]
            display_cols.columns = ['Tournament', 'Fixture', 'Player', 'Their Prediction']
            
            # REMOVED unsafe_allow_html=True from st.dataframe()
            st.dataframe(display_cols, use_container_width=True, hide_index=True)

    # Tab 5: Remove Tournament
    with t5:
        st.subheader("Danger Zone: Delete an Entire Tournament")
        m_df = load_table(MATCHES_FILE)
        
        if m_df.empty:
            st.info("No active tournaments available to delete.")
        else:
            tournaments = m_df['tournament'].unique()
            selected_del_t = st.selectbox("Select Tournament to Delete", tournaments)
            
            st.warning(f"⚠️ **Warning:** Deleting '{selected_del_t}' will permanently erase all of its matches and all user predictions connected to it. This action cannot be undone.")
            
            if st.button("Permanently Delete Tournament", type="primary"):
                delete_tournament(selected_del_t)
                st.success(f"Successfully deleted {selected_del_t}.")
                st.rerun()

    # Tab 6: Manage Users
    with t6:
        st.subheader("👥 Manage Users")
        
        # Add New User Expander Form
        with st.expander("➕ Add New User"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            if st.button("Create User"):
                u_df = load_table(USERS_FILE)
                if new_username in u_df['username'].values:
                    st.error("Username already exists!")
                else:
                    new_id = u_df['user_id'].max() + 1
                    hpw = hashlib.sha256(new_password.encode()).hexdigest()
                    new_user = pd.DataFrame([{"user_id": new_id, "username": new_username, "password": hpw, "role": "user", "status": "active"}])
                    save_table(pd.concat([u_df, new_user], ignore_index=True), USERS_FILE)
                    st.success(f"User '{new_username}' created!")
                    st.rerun()

        st.write("---")
        
        # List, Disable/Activate, and Delete Users
        u_df = load_table(USERS_FILE)
        for idx, row in u_df[u_df['role'] != 'admin'].iterrows():
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: 
                status_icon = "🟢" if row['status'] == 'active' else "🔴"
                st.write(f"{status_icon} **{row['username']}**")
            
            with c2:
                label = "Disable" if row['status'] == 'active' else "Activate"
                if st.button(label, key=f"tog_{row['user_id']}"):
                    u_df.at[idx, 'status'] = 'inactive' if row['status'] == 'active' else 'active'
                    save_table(u_df, USERS_FILE)
                    st.rerun()
            
            with c3:
                if st.button("Delete", key=f"del_{row['user_id']}"):
                    u_df = u_df.drop(idx)
                    save_table(u_df, USERS_FILE)
                    st.rerun()