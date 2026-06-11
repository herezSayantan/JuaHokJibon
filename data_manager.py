import pandas as pd
import os
import hashlib

USERS_FILE = "users.csv"
MATCHES_FILE = "matches.csv"
PREDICTIONS_FILE = "predictions.csv"

def init_data():
    """Initializes the pseudo-Excel sheets if they don't exist."""
    if not os.path.exists(USERS_FILE):
        admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
        df = pd.DataFrame([{
            "user_id": 1, "username": "admin", "password": admin_pw, "role": "admin", "status": "active"
        }])
        df.to_csv(USERS_FILE, index=False)

    if not os.path.exists(MATCHES_FILE):
        df = pd.DataFrame(columns=["match_id", "tournament", "team_A", "team_B", "actual_score_A", "actual_score_B", "status"])
        df.to_csv(MATCHES_FILE, index=False)

    if not os.path.exists(PREDICTIONS_FILE):
        df = pd.DataFrame(columns=["user_id", "match_id", "pred_score_A", "pred_score_B", "points_earned"])
        df.to_csv(PREDICTIONS_FILE, index=False)

def load_table(file_path):
    return pd.read_csv(file_path)

def save_table(df, file_path):
    df.to_csv(file_path, index=False)

def calculate_points(pred_A, pred_B, act_A, act_B):
    if pred_A == act_A and pred_B == act_B:
        return 10.0  # Exact match (100%)
    
    pred_outcome = 1 if pred_A > pred_B else (-1 if pred_A < pred_B else 0)
    act_outcome = 1 if act_A > act_B else (-1 if act_A < act_B else 0)
    
    if pred_outcome == act_outcome:
        if (pred_A - pred_B) == (act_A - act_B):
            return 7.0  # Correct Goal Difference (70%)
        return 5.0  # Correct Winner/Outcome Only (50%)
    return 0.0

def update_match_and_scores(match_id, act_A, act_B):
    matches_df = load_table(MATCHES_FILE)
    predictions_df = load_table(PREDICTIONS_FILE)
    
    matches_df.loc[matches_df['match_id'] == match_id, ['actual_score_A', 'actual_score_B', 'status']] = [act_A, act_B, 'Finished']
    save_table(matches_df, MATCHES_FILE)
    
    for idx, row in predictions_df[predictions_df['match_id'] == match_id].iterrows():
        pts = calculate_points(row['pred_score_A'], row['pred_score_B'], act_A, act_B)
        predictions_df.at[idx, 'points_earned'] = pts
        
    save_table(predictions_df, PREDICTIONS_FILE)

def update_match_teams(match_id, new_team_A, new_team_B):
    """Updates placeholder names to actual qualified teams."""
    matches_df = load_table(MATCHES_FILE)
    matches_df.loc[matches_df['match_id'] == match_id, ['team_A', 'team_B']] = [new_team_A, new_team_B]
    save_table(matches_df, MATCHES_FILE)

def delete_tournament(tournament_name):
    """Deletes all matches and associated predictions for a specific tournament."""
    m_df = load_table(MATCHES_FILE)
    p_df = load_table(PREDICTIONS_FILE)
    
    # Identify which match IDs belong to this tournament
    matches_to_remove = m_df[m_df['tournament'] == tournament_name]['match_id'].tolist()
    
    # Filter out the tournament from matches
    m_df = m_df[m_df['tournament'] != tournament_name]
    save_table(m_df, MATCHES_FILE)
    
    # Filter out any predictions tied to those match IDs
    p_df = p_df[~p_df['match_id'].isin(matches_to_remove)]
    save_table(p_df, PREDICTIONS_FILE)import pandas as pd
import hashlib
from supabase import create_client, Client
import streamlit as st

# Initialize Supabase Client using Streamlit Secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Table names in Supabase
USERS_FILE = "users"
MATCHES_FILE = "matches"
PREDICTIONS_FILE = "predictions"

def init_data():
    """Initializes the database and creates the default admin if users table is empty."""
    users_df = load_table(USERS_FILE)
    if users_df.empty:
        admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
        admin_data = [{
            "username": "admin", 
            "password": admin_pw, 
            "role": "admin", 
            "status": "active"
        }]
        supabase.table(USERS_FILE).insert(admin_data).execute()

def load_table(table_name):
    """Fetches a table from Supabase and returns it as a Pandas DataFrame."""
    response = supabase.table(table_name).select("*").execute()
    data = response.data
    
    # Enforce column structure if the table is empty to prevent Pandas KeyErrors
    if not data:
        if table_name == USERS_FILE:
            return pd.DataFrame(columns=["user_id", "username", "password", "role", "status"])
        elif table_name == MATCHES_FILE:
            return pd.DataFrame(columns=["match_id", "tournament", "team_A", "team_B", "actual_score_A", "actual_score_B", "status"])
        elif table_name == PREDICTIONS_FILE:
            return pd.DataFrame(columns=["prediction_id", "user_id", "match_id", "pred_score_A", "pred_score_B", "points_earned"])
            
    return pd.DataFrame(data)

def save_table(df, table_name):
    """
    Overwrites/Synchronizes the remote table with the provided DataFrame.
    Clears old records and inserts the current state.
    """
    # Clear existing records
    if table_name == USERS_FILE:
        supabase.table(table_name).delete().neq("user_id", -9999).execute()
    elif table_name == MATCHES_FILE:
        supabase.table(table_name).delete().neq("match_id", -9999).execute()
    elif table_name == PREDICTIONS_FILE:
        supabase.table(table_name).delete().neq("prediction_id", -9999).execute()
        
    # Insert new records (stripping out Pandas NaN values)
    if not df.empty:
        records = df.where(pd.notnull(df), None).to_dict(orient="records")
        # Ensure ID columns are omitted on manual updates if auto-incrementing
        for record in records:
            if "prediction_id" in record and (record["prediction_id"] is None or str(record["prediction_id"]).strip() == ""):
                del record["prediction_id"]
        supabase.table(table_name).insert(records).execute()

def calculate_points(pred_A, pred_B, act_A, act_B):
    if pred_A == act_A and pred_B == act_B:
        return 10.0  # Exact match (100%)
    
    pred_outcome = 1 if pred_A > pred_B else (-1 if pred_A < pred_B else 0)
    act_outcome = 1 if act_A > act_B else (-1 if act_A < act_B else 0)
    
    if pred_outcome == act_outcome:
        if (pred_A - pred_B) == (act_A - act_B):
            return 7.0  # Correct Goal Difference (70%)
        return 5.0  # Correct Winner/Outcome Only (50%)
    return 0.0

def update_match_and_scores(match_id, act_A, act_B):
    matches_df = load_table(MATCHES_FILE)
    predictions_df = load_table(PREDICTIONS_FILE)
    
    # Update score directly in Supabase DB
    supabase.table(MATCHES_FILE).update({
        "actual_score_A": str(act_A), 
        "actual_score_B": str(act_B), 
        "status": 'Finished'
    }).eq("match_id", int(match_id)).execute()
    
    # Process prediction scores locally or via updates
    for idx, row in predictions_df[predictions_df['match_id'] == int(match_id)].iterrows():
        pts = calculate_points(row['pred_score_A'], row['pred_score_B'], int(act_A), int(act_B))
        # Update points earned in DB
        supabase.table(PREDICTIONS_FILE).update({"points_earned": float(pts)}).eq("prediction_id", int(row['prediction_id'])).execute()

def update_match_teams(match_id, new_team_A, new_team_B):
    """Updates placeholder names to actual qualified teams."""
    supabase.table(MATCHES_FILE).update({
        "team_A": str(new_team_A), 
        "team_B": str(new_team_B)
    }).eq("match_id", int(match_id)).execute()

def delete_tournament(tournament_name):
    """Deletes all matches and associated predictions for a specific tournament."""
    m_df = load_table(MATCHES_FILE)
    p_df = load_table(PREDICTIONS_FILE)
    
    matches_to_remove = m_df[m_df['tournament'] == tournament_name]['match_id'].tolist()
    
    # Delete connected predictions
    for m_id in matches_to_remove:
        supabase.table(PREDICTIONS_FILE).delete().eq("match_id", int(m_id)).execute()
        
    # Delete tournament matches
    supabase.table(MATCHES_FILE).delete().eq("tournament", tournament_name).execute()