## database.py
# Conexion a Supabase usando cliente oficial
# SmartFlow GDL 2026 - Compatible con Python 3.13

import os
from supabase import create_client, Client

# Sin valores por defecto: las credenciales de Supabase deben venir
# siempre de variables de entorno (configuradas en Railway), nunca
# hardcodeadas en el código. Si faltan, falla explícitamente en vez
# de conectarse en silencio a un proyecto viejo/incorrecto.
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase() -> Client:
    return supabase