#!/usr/bin/env python3
"""Regenerate embeddings with improved format"""
import asyncio
import json
from sqlalchemy import text
from database import AsyncSessionLocal
from semantic.embedding_service import embed_text, build_embedding_text

async def migrate():
    async with AsyncSessionLocal() as session:
        query = text("SELECT id, pattern_id, skill_sequence, goal_text FROM skill_patterns")
        result = await session.execute(query)
        rows = result.fetchall()
        print(f"Regenerating {len(rows)} patterns...", flush=True)
        
        for row in rows:
            pattern_id = row[0]
            p_id = row[1]
            skill_seq = row[2]
            
            if isinstance(skill_seq, list):
                skills = skill_seq
            else:
                try:
                    skills = json.loads(skill_seq) if skill_seq else []
                except:
                    skills = [skill_seq] if skill_seq else []
            
            # Build rich text
            skills_list = "\n".join([f"- {s}" for s in skills]) if skills else ""
            emb_text = f"""Goal: execution task
Description: multi-step pipeline for task completion
Execution plan:
{skills_list}
Intent: This task involves information retrieval, processing, and summarization."""
            
            embedding = embed_text(emb_text)
            
            if embedding:
                emb_json = json.dumps(embedding)
                emb_text_escaped = emb_text.replace("'", "''")
                
                sql = f"""
                    UPDATE skill_patterns 
                    SET embedding = '{emb_json}'::jsonb,
                        goal_text = '{emb_text_escaped}'
                    WHERE id = '{pattern_id}'
                """
                await session.execute(text(sql))
                print(f"  + {p_id[:40]}", flush=True)
        
        await session.commit()
        print("Done!", flush=True)

if __name__ == "__main__":
    asyncio.run(migrate())
