## database.py
# Conexion a Supabase usando cliente oficial
# SmartFlow GDL 2026 - Compatible con Python 3.13

import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "https://ipcunenaytijdproskxf.supabase.co"
)
SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    "sb_publishable_tUdmn3h_fIx9zERQweNTyA_HYqThsb4"
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase() -> Client:
    return supabase