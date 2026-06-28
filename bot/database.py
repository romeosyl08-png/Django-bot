import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Connexion à PostgreSQL (Render exige SSL)."""
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ─────────────────────────────────────────
# 1️⃣ INITIALISATION (vous l'avez déjà)
# ─────────────────────────────────────────
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT,
            question TEXT NOT NULL,
            reponse TEXT NOT NULL,
            tokens INTEGER DEFAULT 0,
            cout REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Base de données initialisée")

# ─────────────────────────────────────────
# 2️⃣ SAUVEGARDER UN MESSAGE
# ─────────────────────────────────────────
def save_message(user_id, username, question, reponse, tokens=0, cout=0):
    """Enregistre un échange dans la base."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (user_id, username, question, reponse, tokens, cout)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, username, question, reponse, tokens, cout))
    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────
# 3️⃣ RÉCUPÉRER L'HISTORIQUE
# ─────────────────────────────────────────
def get_history(user_id, limit=5):
    """Récupère les derniers échanges d'un utilisateur (du + ancien au + récent)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT question, reponse FROM messages
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    # On inverse pour avoir l'ordre chronologique (ancien → récent)
    return list(reversed(rows))
