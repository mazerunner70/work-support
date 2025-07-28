#!/usr/bin/env python3
"""
Sync issue types from hardcoded configuration to database.

This script updates the issue_types table to match the authoritative
configuration in app/config/issue_types.py
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config.settings import ConfigManager
from app.config.issue_types import ISSUE_TYPES
from app.models.database import IssueType


def sync_issue_types():
    """Sync issue types from config to database."""
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Create database engine
    database_url = f"sqlite:///{config_manager.settings.database_path}"
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    with SessionLocal() as db:
        print("🔄 Starting issue types sync...")
        
        # Get current issue types from database
        existing_types = {it.id: it for it in db.query(IssueType).all()}
        print(f"📊 Found {len(existing_types)} existing issue types in database")
        
        # Get configured issue types
        print(f"📋 Found {len(ISSUE_TYPES)} configured issue types")
        
        # Track changes
        added_count = 0
        updated_count = 0
        
        # Sync each configured issue type
        for config_type in ISSUE_TYPES:
            if config_type.id in existing_types:
                # Update existing
                db_type = existing_types[config_type.id]
                if (db_type.name != config_type.name or 
                    db_type.url != config_type.url):
                    print(f"  ✏️  Updating issue type {config_type.id}: {config_type.name}")
                    db_type.name = config_type.name
                    db_type.url = config_type.url
                    updated_count += 1
            else:
                # Add new
                print(f"  ➕ Adding issue type {config_type.id}: {config_type.name}")
                new_type = IssueType(
                    id=config_type.id,
                    name=config_type.name,
                    url=config_type.url
                )
                db.add(new_type)
                added_count += 1
        
        # Commit changes
        db.commit()
        
        print(f"\n✅ Sync complete!")
        print(f"   📈 Added: {added_count} issue types")
        print(f"   📝 Updated: {updated_count} issue types")
        
        # Verify the problematic issue type
        aimp_type = db.query(IssueType).filter(IssueType.id == 11128).first()
        if aimp_type:
            print(f"\n🎯 Verified: Issue type 11128 '{aimp_type.name}' now exists in database")
        else:
            print(f"\n❌ Warning: Issue type 11128 still not found after sync")


if __name__ == "__main__":
    try:
        sync_issue_types()
    except Exception as e:
        print(f"❌ Error during sync: {e}")
        sys.exit(1) 