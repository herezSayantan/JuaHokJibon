import pandas as pd
import numpy as np
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
            return pd.DataFrame(columns=["match_id", "tournament", "team_a", "team_b", "actual_score_a", "actual_score_b", "status"])
        elif table_name == PREDICTIONS_FILE:
            return pd.DataFrame(columns=["prediction_id", "user_id", "match_id", "pred_score_a", "pred_score_b", "points_earned"])
            
    return pd.DataFrame(data)

def save_table(df, table_name):
    """
    Synchronizes the remote table with the provided DataFrame using Upsert.
    Clearing the whole table on every prediction update is unsafe for relational integrity, 
    so we use upsert to insert or update rows seamlessly without serialization errors.
    """
    if df.empty:
        if table_name == USERS_FILE:
            supabase.table(table_name).delete().neq("user_id", -9999).execute()
        elif table_name == MATCHES_FILE:
            supabase.table(table_name).delete().neq("match_id", -9999).execute()
        elif table_name == PREDICTIONS_FILE:
            supabase.table(table_name).delete().neq("prediction_id", -9999).execute()
        return
        
    # Clean NaN/NA values safely for Supabase JSON payload
    df_clean = df.replace({np.nan: None})
    records = df_clean.to_dict(orient="records")
    
    upsert_records = []
    for record in records:
        cleaned_record = {}
        for k, v in record.items():
            if pd.isna(v):
                cleaned_record[k] = None
            else:
                cleaned_record[k] = v
        
        # If prediction_id is empty, null, or NaN/None, let Supabase auto-increment it
        if "prediction_id" in cleaned_record:
            if cleaned_record["prediction_id"] is None or str(cleaned_record["prediction_id"]).strip() in ["", "nan", "None"]:
                del cleaned_record["prediction_id"]
            else:
                cleaned_record["prediction_id"] = int(cleaned_record["prediction_id"])
        
        # Ensure proper types for numeric fields
        for key in ["user_id", "match_id", "pred_score_a", "pred_score_b"]:
            if key in cleaned_record and cleaned_record[key] is not None:
                cleaned_record[key] = int(cleaned_record[key])
        if "points_earned" in cleaned_record and cleaned_record["points_earned"] is not None:
            cleaned_record["points_earned"] = float(cleaned_record["points_earned"])
            
        upsert_records.append(cleaned_record)
        
    if upsert_records:
        supabase.table(table_name).upsert(upsert_records).execute()

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
    
    # Update score directly in Supabase DB with lowercase column names
    supabase.table(MATCHES_FILE).update({
        "actual_score_a": str(act_A), 
        "actual_score_b": str(act_B), 
        "status": 'Finished'
    }).eq("match_id", int(match_id)).execute()
    
    # Process prediction scores locally or via updates
    for idx, row in predictions_df[predictions_df['match_id'] == int(match_id)].iterrows():
        pts = calculate_points(row['pred_score_a'], row['pred_score_b'], int(act_A), int(act_B))
        # Update points earned in DB
        supabase.table(PREDICTIONS_FILE).update({"points_earned": float(pts)}).eq("prediction_id", int(row['prediction_id'])).execute()

def update_match_teams(match_id, new_team_A, new_team_B):
    """Updates placeholder names to actual qualified teams using lowercase column names."""
    supabase.table(MATCHES_FILE).update({
        "team_a": str(new_team_A), 
        "team_b": str(new_team_B)
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