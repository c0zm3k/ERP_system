#!/usr/bin/env python
"""Check database tables and verify Broadcast table exists."""
from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
    tables = [row[0] for row in result]
    
    print("=" * 60)
    print("DATABASE TABLE REPORT")
    print("=" * 60)
    print("\nTables in database:")
    for table in tables:
        status = "✓" if table == "broadcast" else " "
        print(f"  [{status}] {table}")
    
    print(f"\nTotal tables: {len(tables)}")
    
    if "broadcast" in tables:
        print("\n✓ SUCCESS: Broadcast table EXISTS in database!")
        
        # Show table columns
        result = db.session.execute(text("PRAGMA table_info(broadcast)"))
        columns = result.fetchall()
        print("\nBroadcast table columns:")
        for col in columns:
            col_id, col_name, col_type, notnull, default, pk = col
            print(f"  - {col_name}: {col_type}")
    else:
        print("\n✗ ERROR: Broadcast table NOT found in database!")
        print("\nThis means the new Broadcast model was not properly registered.")
    
    print("\n" + "=" * 60)
