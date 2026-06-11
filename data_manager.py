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
    
    matches_to_remove = m_df[m_df['tournament'] == tournament_name]['match_id'].tolist()
    m_df = m_df[m_df['tournament'] != tournament_name]
    save_table(m_df, MATCHES_FILE)
    
    p_df = p_df[~p_df['match_id'].isin(matches_to_remove)]
    save_table(p_df, PREDICTIONS_FILE)